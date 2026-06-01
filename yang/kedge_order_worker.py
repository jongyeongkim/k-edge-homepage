# -*- coding: utf-8 -*-
"""
K-EDGE V9.5.8 ORDER WORKER - CROSS + FOREIGN-FILL AMOUNT SYNC
- Reads order_queue.jsonl written by the 4 scanner bots.
- Performs member lookup, duplicate ACTIVE lock, final recheck, foreign short first, Bithumb buy second.
- Scanner bots must be scanner-only and must not place orders.
- V9.5.7: Before every foreign short entry, force/check symbol-level CROSS margin.
  If CROSS cannot be set/verified, cancel entry before foreign short and before Bithumb buy.
- V9.5.8: After foreign short order succeeds, sync Bithumb buy KRW to actual foreign filled notional KRW when available.
"""
import os
import sys
import json
import time
import glob
import importlib.util
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, Set, Tuple, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ORDER_QUEUE_PATH = os.path.join(BASE_DIR, "order_queue.jsonl")
ORDER_QUEUE_OFFSET_PATH = os.path.join(BASE_DIR, "order_queue.offset")
ORDER_WORKER_PROCESSED_PATH = os.path.join(BASE_DIR, "order_worker_processed.json")
ORDER_WORKER_POLL_SEC = float(os.getenv("ORDER_WORKER_POLL_SEC", "0.2"))
QUEUE_ITEM_MAX_AGE_SEC = int(os.getenv("QUEUE_ITEM_MAX_AGE_SEC", "30"))
ORDER_WORKER_MAX_PARALLEL = int(os.getenv("ORDER_WORKER_MAX_PARALLEL", "10"))

_PRINT_LOCK = threading.Lock()

def log(msg: str) -> None:
    """Thread-safe print for parallel order logs."""
    with _PRINT_LOCK:
        print(msg, flush=True)

ORDER_MEMBER_CACHE_TTL_SEC = int(os.getenv("ORDER_MEMBER_CACHE_TTL_SEC", "120"))
_ORDER_MEMBER_CACHE = {"ts": 0.0, "members": None}

def get_approved_members_cached():
    """ORDER WORKER 전용 승인회원 캐시.
    V9.5.2b: 자기 자신을 다시 호출하던 재귀 버그 수정.
    실제 조회는 core.supabase_get_approved_members(force_refresh=True)를 사용한다.
    """
    now = time.time()
    if _ORDER_MEMBER_CACHE.get("members") is not None and now - float(_ORDER_MEMBER_CACHE.get("ts") or 0) < ORDER_MEMBER_CACHE_TTL_SEC:
        return _ORDER_MEMBER_CACHE["members"]

    try:
        if hasattr(core, "supabase_get_approved_members"):
            members = core.supabase_get_approved_members(force_refresh=True)
        elif hasattr(core, "supabase_get_approved_members_uncached"):
            members = core.supabase_get_approved_members_uncached()
        else:
            print("[ORDER MEMBER CACHE] core 승인회원 조회 함수 없음")
            members = []
    except Exception as e:
        print(f"[ORDER MEMBER CACHE] 승인회원 조회 실패: {e}")
        members = []

    _ORDER_MEMBER_CACHE["members"] = members
    _ORDER_MEMBER_CACHE["ts"] = now
    return members



def load_core():
    candidates = sorted(glob.glob(os.path.join(BASE_DIR, "kedge_v9_5_2_SCAN_QUEUE_MEXC.py")))
    if not candidates:
        candidates = sorted(glob.glob(os.path.join(BASE_DIR, "kedge*_MEXC*.py")))
    if not candidates:
        print("[FATAL] MEXC core file not found")
        sys.exit(1)
    target = candidates[-1]
    spec = importlib.util.spec_from_file_location("kedge_core_order", target)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    print(f"[ORDER WORKER] core loaded: {os.path.basename(target)}")
    return module


core = load_core()

# Workers, unlike scanner files, must have full futures objects for recheck/order.
# Scanner files keep ENABLE_CALLBACK_POLLER=False, but workers need MEXC/GATE/BITGET/BINGX loaded.
try:
    core.ENABLE_CALLBACK_POLLER = True
    _, future_exs = core.init_ccxt_all()
    core.GLOBAL_FUTURE_EXS = core.init_callback_future_exs(future_exs)
    print(f"[ORDER WORKER] GLOBAL_FUTURE_EXS={sorted(core.GLOBAL_FUTURE_EXS.keys())}")
except Exception as e:
    print(f"[ORDER WORKER] futures init warning: {e}")


def read_json(path: str, default: Any) -> Any:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def write_json(path: str, data: Any) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _norm_exchange(v: Any) -> str:
    return str(v or "").strip().upper()


def _norm_coin(v: Any) -> str:
    return str(v or "").strip().upper().replace("_KRW", "").replace("/USDT:USDT", "").replace("/USDT", "")


# ---------------------------------------------------------------------
# V9.5.7 CROSS MARGIN GUARD
# ---------------------------------------------------------------------
# 적용 범위:
# - ORDER WORKER 안에서만, 실제 자동진입 직전만 검사한다.
# - SCAN / CLOSE / 현재엣지 / TP-SL / 중복 LOCK 로직은 건드리지 않는다.
# - 해외숏 주문 전에 심볼별 Cross 전환을 먼저 시도한다.
# - Cross 전환 실패 시 해외숏 주문과 빗썸 매수를 모두 금지한다.

CROSS_GUARD_ENABLED = os.getenv("ORDER_CROSS_GUARD_ENABLED", "true").lower() == "true"
CROSS_GUARD_VERIFY_AFTER_SET = os.getenv("ORDER_CROSS_GUARD_VERIFY_AFTER_SET", "true").lower() == "true"
_CROSS_OK_CACHE_TTL_SEC = float(os.getenv("ORDER_CROSS_GUARD_CACHE_TTL_SEC", "60"))
_CROSS_OK_CACHE: Dict[str, float] = {}
_CROSS_LOCKS: Dict[str, threading.Lock] = {}
_CROSS_LOCKS_GUARD = threading.Lock()


def _cross_lock(key: str) -> threading.Lock:
    with _CROSS_LOCKS_GUARD:
        lock = _CROSS_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _CROSS_LOCKS[key] = lock
        return lock


def _cross_cache_key(member: Dict[str, Any], foreign: str, market: str) -> str:
    user = str(core.get_member_chat_id(member) or member.get("tg_chat_id") or member.get("chat_id") or member.get("user_id") or "")
    return f"{user}:{foreign.upper()}:{str(market).upper()}"


def _is_cross_mode_text(v: Any) -> bool:
    t = str(v or "").strip().lower().replace("-", "_").replace(" ", "_")
    return t in {"cross", "crossed", "cross_margin", "crossmargin", "multi", "portfolio"}


def _is_isolated_mode_text(v: Any) -> bool:
    t = str(v or "").strip().lower().replace("-", "_").replace(" ", "_")
    return t in {"isolated", "isolate", "isolated_margin", "isolatedmargin", "single"}


def _error_means_already_cross(err: Exception) -> bool:
    text = str(err).lower()
    ok_words = ["already", "no need", "not modified", "same margin", "same mode", "not change"]
    return any(w in text for w in ok_words) and ("cross" in text or "crossed" in text)


def _extract_margin_mode_from_position(p: Dict[str, Any]) -> str:
    if not isinstance(p, dict):
        return ""
    info = p.get("info") if isinstance(p.get("info"), dict) else {}
    candidates = [
        p.get("marginMode"), p.get("margin_mode"), p.get("mode"),
        info.get("marginMode"), info.get("margin_mode"), info.get("marginType"),
        info.get("openType"), info.get("positionMode"), info.get("mode"),
    ]
    for v in candidates:
        if v in (None, ""):
            continue
        sv = str(v).lower()
        if "cross" in sv or "isolat" in sv:
            return sv
    return ""


def _fetch_symbol_margin_mode(ex: Any, market: str) -> Tuple[str, str]:
    """현재 심볼 마진모드 조회. cross / isolated / unknown 반환."""
    try:
        if hasattr(ex, "fetch_margin_mode"):
            res = ex.fetch_margin_mode(market)
            if isinstance(res, dict):
                mode = res.get("marginMode") or res.get("mode") or (res.get("info") or {}).get("marginMode")
                if _is_cross_mode_text(mode):
                    return "cross", f"fetch_margin_mode={mode}"
                if _is_isolated_mode_text(mode):
                    return "isolated", f"fetch_margin_mode={mode}"
                return "unknown", f"fetch_margin_mode_unknown={str(res)[:180]}"
    except Exception as e:
        return "unknown", f"fetch_margin_mode_error={repr(e)}"

    try:
        if hasattr(ex, "fetch_positions"):
            positions = ex.fetch_positions([market])
            for p in positions or []:
                if not isinstance(p, dict):
                    continue
                sym = str(p.get("symbol") or (p.get("info") or {}).get("symbol") or "").upper()
                if sym and str(market).upper() not in sym and sym not in str(market).upper():
                    continue
                mode = _extract_margin_mode_from_position(p)
                if _is_cross_mode_text(mode):
                    return "cross", f"fetch_positions={mode}"
                if _is_isolated_mode_text(mode):
                    return "isolated", f"fetch_positions={mode}"
    except Exception as e:
        return "unknown", f"fetch_positions_mode_error={repr(e)}"

    return "unknown", "mode_lookup_not_supported_or_empty"


def _set_symbol_cross_margin(ex: Any, foreign: str, market: str) -> Tuple[bool, str]:
    """CCXT set_margin_mode 계열로 심볼별 Cross 전환을 강제 시도."""
    f = str(foreign or "").upper()
    attempts: List[Tuple[str, Dict[str, Any]]] = [("cross", {})]

    if f == "MEXC":
        attempts.extend([("cross", {"openType": 2}), ("crossed", {"openType": 2})])
    elif f == "BITGET":
        attempts.extend([("cross", {"marginCoin": "USDT"}), ("crossed", {"marginCoin": "USDT"})])
    elif f == "BINGX":
        attempts.extend([("cross", {"side": "BOTH"}), ("cross", {"positionSide": "BOTH"}), ("crossed", {})])
    elif f == "GATE":
        attempts.extend([("cross", {"settle": "usdt"}), ("crossed", {"settle": "usdt"})])

    if not hasattr(ex, "set_margin_mode"):
        return False, "exchange.set_margin_mode not supported"

    last_err = None
    for mode, params in attempts:
        try:
            res = ex.set_margin_mode(mode, market, params)
            return True, f"set_margin_mode({mode},{params}) ok {str(res)[:180]}"
        except Exception as e:
            last_err = e
            if _error_means_already_cross(e):
                return True, f"already_cross_or_nochange: {repr(e)}"
            continue
    return False, f"set_margin_mode failed: {repr(last_err)}"


def ensure_cross_margin_before_entry(member: Dict[str, Any], signal: Dict[str, Any]) -> Tuple[bool, str]:
    """해외숏 주문 전 Cross 보장. 실패하면 주문 전 단계에서 진입 취소."""
    if not CROSS_GUARD_ENABLED:
        return True, "cross guard disabled"

    foreign = _norm_exchange(signal.get("foreign") or signal.get("foreign_exchange") or signal.get("exchange"))
    coin = _norm_coin(signal.get("coin") or signal.get("symbol"))
    if not foreign or not coin:
        return False, f"교차모드 확인 실패: foreign/coin missing foreign={foreign} coin={coin}"

    try:
        ex = None
        if hasattr(core, "build_user_exchange_from_member"):
            ex = core.build_user_exchange_from_member(member, foreign.lower(), "future")
        if ex is None:
            return False, f"{foreign} 선물 API 객체 생성 실패"

        try:
            ex.load_markets()
        except Exception as e:
            log(f"[CROSS GUARD WARN] load_markets {foreign} {coin} / {e}")

        market = signal.get("foreign_market") or signal.get("future_market") or ""
        if not market and hasattr(core, "find_future_market"):
            market = core.find_future_market(ex, coin)
        if not market:
            return False, f"{foreign} {coin} 선물마켓 찾기 실패"

        cache_key = _cross_cache_key(member, foreign, str(market))
        cached_ts = float(_CROSS_OK_CACHE.get(cache_key) or 0.0)
        if cached_ts and time.time() - cached_ts < _CROSS_OK_CACHE_TTL_SEC:
            return True, f"CROSS 캐시 OK {foreign} {market}"

        with _cross_lock(cache_key):
            cached_ts = float(_CROSS_OK_CACHE.get(cache_key) or 0.0)
            if cached_ts and time.time() - cached_ts < _CROSS_OK_CACHE_TTL_SEC:
                return True, f"CROSS 캐시 OK {foreign} {market}"

            before_mode, before_detail = _fetch_symbol_margin_mode(ex, str(market))
            log(f"[CROSS GUARD] {foreign} {coin} market={market} before={before_mode} detail={before_detail}")

            if before_mode == "cross":
                _CROSS_OK_CACHE[cache_key] = time.time()
                return True, f"이미 CROSS {foreign} {market}"

            set_ok, set_detail = _set_symbol_cross_margin(ex, foreign, str(market))
            log(f"[CROSS GUARD] {foreign} {coin} set_cross ok={set_ok} detail={set_detail}")
            if not set_ok:
                return False, f"{foreign} {coin} 교차모드 변경 실패: {set_detail}"

            if CROSS_GUARD_VERIFY_AFTER_SET:
                after_mode, after_detail = _fetch_symbol_margin_mode(ex, str(market))
                log(f"[CROSS GUARD] {foreign} {coin} after={after_mode} detail={after_detail}")
                if after_mode == "isolated":
                    return False, f"{foreign} {coin} 교차모드 변경 후에도 ISOLATED 감지: {after_detail}"
                # unknown은 set_margin_mode 성공 후면 허용. 일부 거래소는 무포지션 심볼 모드 조회가 안 됨.

            _CROSS_OK_CACHE[cache_key] = time.time()
            return True, f"CROSS 준비 완료 {foreign} {market}"
    except Exception as e:
        return False, f"교차모드 가드 예외: {repr(e)}"


def notify_cross_guard_fail(tg_id: str, member: Dict[str, Any], signal: Dict[str, Any], detail: str) -> None:
    try:
        coin = _norm_coin(signal.get("coin") or signal.get("symbol"))
        foreign = _norm_exchange(signal.get("foreign") or signal.get("foreign_exchange") or signal.get("exchange"))
        domestic = _norm_exchange(signal.get("domestic") or signal.get("domestic_exchange") or "BITHUMB")
        msg = (
            "❌ 자동진입 취소\n\n"
            "사유: 해외 선물 교차모드 변경/확인 실패\n\n"
            f"코인: {coin}\n"
            f"경로: {domestic} ↔ {foreign}\n\n"
            "해외숏 주문 전 단계에서 중단했습니다.\n"
            "국내 매수는 실행하지 않았습니다.\n\n"
            f"상세: {detail}"
        )
        if hasattr(core, "telegram_send_private") and tg_id:
            core.telegram_send_private(str(tg_id), msg)
    except Exception as e:
        log(f"[CROSS GUARD DM WARN] {tg_id} / {e}")



# ---------------------------------------------------------------------
# V9.5.8 FOREIGN-FILL -> DOMESTIC BUY AMOUNT SYNC
# ---------------------------------------------------------------------
# 목적:
# - K-EDGE는 해외숏 선진입 → 빗썸 후매수 구조다.
# - 따라서 국내 매수 KRW는 "설정금액"보다 "해외 실제 체결 명목금액"에 맞추는 것이 헷지 균형에 더 안전하다.
# - ORDER WORKER에서 core 주문함수를 크게 뜯지 않고, 런타임 래퍼로 해외 주문 응답과 빗썸 매수 요청 사이를 연결한다.
#
# 안전장치:
# - 해외 주문 응답에서 cost 또는 filled*average가 확인될 때만 국내 KRW를 동기화한다.
# - 계산된 국내 매수금액이 원래 목표금액 대비 과도하게 벗어나면 동기화하지 않고 기존 금액을 유지한다.
# - MEXC처럼 주문 응답에 cost/filled가 비어 있으면 기존 방식으로 진행한다.
# - SCAN/CLOSE/현재엣지/중복 LOCK은 건드리지 않는다.

AMOUNT_SYNC_ENABLED = os.getenv("ORDER_FOREIGN_FILL_AMOUNT_SYNC_ENABLED", "true").lower() == "true"
AMOUNT_SYNC_MAX_DEVIATION_PERCENT = float(os.getenv("ORDER_FOREIGN_FILL_AMOUNT_SYNC_MAX_DEVIATION_PERCENT", "5.0"))
AMOUNT_SYNC_MIN_KRW = float(os.getenv("ORDER_FOREIGN_FILL_AMOUNT_SYNC_MIN_KRW", "5000"))
_AMOUNT_SYNC_TLS = threading.local()
_AMOUNT_SYNC_INSTALLED = False
_AMOUNT_SYNC_INSTALL_LOCK = threading.Lock()


def _sync_safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def _sync_usd_krw(signal: Dict[str, Any]) -> float:
    return _sync_safe_float(
        signal.get("usd_krw")
        or getattr(core, "FALLBACK_USD_KRW", None)
        or getattr(core, "MANUAL_USD_KRW", None)
        or 1509.0,
        1509.0,
    )


def _sync_target_krw(signal: Dict[str, Any]) -> float:
    for k in [
        "final_entry_krw", "domestic_entry_krw", "amount_krw",
        "entry_krw", "trade_krw", "target_krw", "krw",
    ]:
        n = _sync_safe_float(signal.get(k), 0.0)
        if n > 0:
            return n
    return 0.0


def _sync_get_ctx() -> Dict[str, Any]:
    ctx = getattr(_AMOUNT_SYNC_TLS, "ctx", None)
    return ctx if isinstance(ctx, dict) else {}


def _sync_set_ctx(ctx: Dict[str, Any]) -> None:
    _AMOUNT_SYNC_TLS.ctx = ctx


def _sync_clear_ctx() -> None:
    _AMOUNT_SYNC_TLS.ctx = {}


def _extract_foreign_notional_usdt_from_order(order: Any) -> Tuple[float, str]:
    """CCXT 주문 응답에서 실제 선물 체결 명목 USDT를 최대한 안전하게 추출."""
    if not isinstance(order, dict):
        return 0.0, "order_not_dict"

    info = order.get("info") if isinstance(order.get("info"), dict) else {}

    # 1) ccxt unified cost가 가장 신뢰 가능. Gate/BingX는 대부분 여기에 USDT 명목이 들어온다.
    cost = _sync_safe_float(order.get("cost"), 0.0)
    if cost > 0:
        return cost, "order.cost"

    # 2) average * filled
    avg = _sync_safe_float(order.get("average") or order.get("price"), 0.0)
    filled = _sync_safe_float(order.get("filled") or order.get("amount"), 0.0)
    if avg > 0 and filled > 0:
        return avg * filled, "order.average*filled"

    # 3) 거래소 raw info
    info_cost_keys = [
        "cost", "dealValue", "deal_value", "quoteVolume", "quoteQty",
        "quoteOrderQty", "cumQuote", "filledValue", "value", "turnover",
    ]
    for k in info_cost_keys:
        n = _sync_safe_float(info.get(k), 0.0)
        if n > 0:
            return n, f"info.{k}"

    info_price = _sync_safe_float(
        info.get("avgPrice") or info.get("fill_price") or info.get("price") or info.get("dealAvgPrice"),
        0.0,
    )
    info_qty = _sync_safe_float(
        info.get("executedQty") or info.get("filled") or info.get("size") or info.get("quantity") or info.get("amount"),
        0.0,
    )
    if info_price > 0 and info_qty > 0:
        return info_price * abs(info_qty), "info.price*qty"

    return 0.0, "notional_unavailable"


def _capture_foreign_order_result(order: Any, src: str) -> None:
    ctx = _sync_get_ctx()
    if not ctx.get("enabled"):
        return

    notional_usdt, source = _extract_foreign_notional_usdt_from_order(order)
    if notional_usdt <= 0:
        log(f"[AMOUNT SYNC] foreign fill notional unavailable src={src} reason={source}")
        return

    usd_krw = _sync_usd_krw(ctx.get("signal") or {})
    filled_krw = notional_usdt * max(1.0, usd_krw)
    target_krw = _sync_safe_float(ctx.get("target_krw"), 0.0)

    if target_krw > 0:
        diff_pct = abs(filled_krw - target_krw) / max(1.0, target_krw) * 100.0
        # 동기화 자체는 목표 대비 5% 이내일 때만 수행한다.
        # 5% 초과면 금액이 비정상적으로 튄 것이므로 기존 목표금액을 유지하고 로그만 남긴다.
        if diff_pct > AMOUNT_SYNC_MAX_DEVIATION_PERCENT:
            ctx["foreign_fill_krw_rejected"] = filled_krw
            ctx["foreign_fill_reject_reason"] = f"target_diff {diff_pct:.2f}% > {AMOUNT_SYNC_MAX_DEVIATION_PERCENT:.2f}%"
            log(
                f"[AMOUNT SYNC WARN] foreign fill ignored target={target_krw:.0f} "
                f"foreign={filled_krw:.0f} diff={diff_pct:.2f}% source={source}"
            )
            return

    if filled_krw < AMOUNT_SYNC_MIN_KRW:
        log(f"[AMOUNT SYNC WARN] foreign fill ignored too_small krw={filled_krw:.0f}")
        return

    ctx["foreign_fill_usdt"] = notional_usdt
    ctx["foreign_fill_krw"] = filled_krw
    ctx["foreign_fill_source"] = source
    _sync_set_ctx(ctx)
    log(
        f"[AMOUNT SYNC] foreign filled captured {notional_usdt:.6f} USDT "
        f"≈ {filled_krw:.0f} KRW source={source} src={src}"
    )


def _synced_domestic_krw(original_krw: float) -> Tuple[float, str]:
    ctx = _sync_get_ctx()
    if not ctx.get("enabled"):
        return original_krw, "disabled"

    foreign_krw = _sync_safe_float(ctx.get("foreign_fill_krw"), 0.0)
    if foreign_krw <= 0:
        return original_krw, "foreign_fill_missing"

    # 빗썸 원화주문은 정수 KRW 기준으로 내림 처리.
    synced = max(0.0, float(int(foreign_krw)))
    if synced < AMOUNT_SYNC_MIN_KRW:
        return original_krw, "synced_too_small"

    if original_krw > 0:
        diff_pct = abs(synced - original_krw) / max(1.0, original_krw) * 100.0
        if diff_pct > AMOUNT_SYNC_MAX_DEVIATION_PERCENT:
            return original_krw, f"diff_too_large {diff_pct:.2f}%"

    return synced, "synced_to_foreign_fill"


def _patch_exchange_order_methods(ex: Any, foreign: str) -> Any:
    """유저별 해외 선물 객체의 create_order류를 래핑해서 실제 체결 명목을 캡처."""
    if ex is None:
        return ex

    # 같은 객체 중복 래핑 방지
    if getattr(ex, "_kedge_amount_sync_wrapped", False):
        return ex

    method_names = [
        "create_order",
        "create_market_order",
        "create_market_sell_order",
        "create_limit_sell_order",
    ]

    for name in method_names:
        fn = getattr(ex, name, None)
        if not callable(fn):
            continue

        def make_wrapper(orig_fn, method_name):
            def wrapper(*args, **kwargs):
                res = orig_fn(*args, **kwargs)
                try:
                    ctx = _sync_get_ctx()
                    if ctx.get("enabled"):
                        wanted = str(ctx.get("foreign") or "").upper()
                        if not wanted or wanted == str(foreign or "").upper():
                            _capture_foreign_order_result(res, f"{foreign}.{method_name}")
                except Exception as e:
                    log(f"[AMOUNT SYNC WARN] capture failed {foreign}.{method_name} / {e}")
                return res
            return wrapper

        try:
            setattr(ex, name, make_wrapper(fn, name))
        except Exception:
            pass

    try:
        setattr(ex, "_kedge_amount_sync_wrapped", True)
    except Exception:
        pass
    return ex


def _adjust_domestic_order_args(args: tuple, kwargs: dict) -> Tuple[tuple, dict, str]:
    """빗썸 매수 함수에 들어가는 KRW 금액을 해외 실제 체결 명목 KRW로 교체."""
    ctx = _sync_get_ctx()
    if not ctx.get("enabled"):
        return args, kwargs, "disabled"

    if _sync_safe_float(ctx.get("foreign_fill_krw"), 0.0) <= 0:
        return args, kwargs, "foreign_fill_missing"

    target_krw = _sync_safe_float(ctx.get("target_krw"), 0.0)

    new_args = list(args)
    new_kwargs = dict(kwargs)

    # 1) kwargs 우선 교체
    for k in ["krw", "amount_krw", "entry_krw", "price", "funds", "cash_amount", "buy_krw"]:
        if k in new_kwargs:
            orig = _sync_safe_float(new_kwargs.get(k), 0.0)
            if orig > 0 and (target_krw <= 0 or abs(orig - target_krw) / max(1.0, target_krw) * 100.0 <= 30.0):
                synced, why = _synced_domestic_krw(orig)
                if synced != orig:
                    new_kwargs[k] = int(synced)
                    return tuple(new_args), new_kwargs, f"kw.{k}:{orig:.0f}->{synced:.0f} {why}"

    # 2) params dict 안 price 교체
    for idx, val in enumerate(new_args):
        if isinstance(val, dict):
            d = dict(val)
            for k in ["price", "krw", "amount_krw", "funds"]:
                if k in d:
                    orig = _sync_safe_float(d.get(k), 0.0)
                    if orig > 0 and (target_krw <= 0 or abs(orig - target_krw) / max(1.0, target_krw) * 100.0 <= 30.0):
                        synced, why = _synced_domestic_krw(orig)
                        if synced != orig:
                            d[k] = str(int(synced)) if isinstance(d.get(k), str) else int(synced)
                            new_args[idx] = d
                            return tuple(new_args), new_kwargs, f"argdict.{k}:{orig:.0f}->{synced:.0f} {why}"

    for k, val in list(new_kwargs.items()):
        if isinstance(val, dict):
            d = dict(val)
            for dk in ["price", "krw", "amount_krw", "funds"]:
                if dk in d:
                    orig = _sync_safe_float(d.get(dk), 0.0)
                    if orig > 0 and (target_krw <= 0 or abs(orig - target_krw) / max(1.0, target_krw) * 100.0 <= 30.0):
                        synced, why = _synced_domestic_krw(orig)
                        if synced != orig:
                            d[dk] = str(int(synced)) if isinstance(d.get(dk), str) else int(synced)
                            new_kwargs[k] = d
                            return tuple(new_args), new_kwargs, f"kwdict.{k}.{dk}:{orig:.0f}->{synced:.0f} {why}"

    # 3) positional numeric 교체. 빗썸 매수 함수는 보통 krw가 3~5번째 인자로 들어온다.
    for idx, val in enumerate(new_args):
        orig = _sync_safe_float(val, 0.0)
        if orig <= 0:
            continue
        if orig < 1000:
            continue
        if target_krw > 0 and abs(orig - target_krw) / max(1.0, target_krw) * 100.0 > 30.0:
            continue
        synced, why = _synced_domestic_krw(orig)
        if synced != orig:
            new_args[idx] = int(synced) if isinstance(val, int) else (str(int(synced)) if isinstance(val, str) else synced)
            return tuple(new_args), new_kwargs, f"arg{idx}:{orig:.0f}->{synced:.0f} {why}"

    return tuple(new_args), new_kwargs, "no_krw_arg_found"


def _wrap_core_function_for_amount_sync(name: str, fn: Any) -> Any:
    lower = name.lower()

    def wrapper(*args, **kwargs):
        adj_args = args
        adj_kwargs = kwargs
        changed = ""

        # 빗썸 매수/주문 함수로 보이는 경우에만 KRW 교체 시도.
        if "bithumb" in lower and any(w in lower for w in ["buy", "order", "bid"]):
            try:
                adj_args, adj_kwargs, changed = _adjust_domestic_order_args(args, kwargs)
                if changed and changed not in ("disabled", "foreign_fill_missing", "no_krw_arg_found"):
                    log(f"[AMOUNT SYNC] domestic buy amount adjusted by {name}: {changed}")
            except Exception as e:
                log(f"[AMOUNT SYNC WARN] domestic adjust failed {name} / {e}")
                adj_args, adj_kwargs = args, kwargs

        return fn(*adj_args, **adj_kwargs)

    try:
        wrapper.__name__ = getattr(fn, "__name__", name)
        wrapper.__doc__ = getattr(fn, "__doc__", None)
    except Exception:
        pass
    return wrapper


def install_amount_sync_wrappers() -> None:
    """core 함수들을 런타임 래핑. ORDER WORKER 프로세스에만 적용된다."""
    global _AMOUNT_SYNC_INSTALLED
    if not AMOUNT_SYNC_ENABLED:
        return
    with _AMOUNT_SYNC_INSTALL_LOCK:
        if _AMOUNT_SYNC_INSTALLED:
            return

        # 1) build_user_exchange_from_member를 감싸서 해외 선물 주문 객체의 create_order 응답을 캡처.
        orig_build = getattr(core, "build_user_exchange_from_member", None)
        if callable(orig_build):
            def build_wrapper(member, exchange_name, account_type="future", *args, **kwargs):
                ex = orig_build(member, exchange_name, account_type, *args, **kwargs)
                try:
                    ctx = _sync_get_ctx()
                    if ctx.get("enabled") and str(account_type).lower().startswith("future"):
                        foreign = _norm_exchange(exchange_name)
                        ex = _patch_exchange_order_methods(ex, foreign)
                except Exception as e:
                    log(f"[AMOUNT SYNC WARN] exchange wrapper failed {exchange_name} / {e}")
                return ex
            try:
                setattr(core, "build_user_exchange_from_member", build_wrapper)
                log("[AMOUNT SYNC] wrapped core.build_user_exchange_from_member")
            except Exception as e:
                log(f"[AMOUNT SYNC WARN] build wrapper install failed / {e}")

        # 2) core 안의 빗썸 매수/주문 함수 후보를 감싸서 국내 KRW를 해외 체결금액으로 조정.
        wrapped_names = []
        for name in dir(core):
            if name.startswith("__"):
                continue
            lower = name.lower()
            if "bithumb" not in lower:
                continue
            if not any(w in lower for w in ["buy", "order", "bid"]):
                continue
            try:
                fn = getattr(core, name)
            except Exception:
                continue
            if not callable(fn) or getattr(fn, "_kedge_amount_sync_wrapped_fn", False):
                continue
            try:
                wfn = _wrap_core_function_for_amount_sync(name, fn)
                setattr(wfn, "_kedge_amount_sync_wrapped_fn", True)
                setattr(core, name, wfn)
                wrapped_names.append(name)
            except Exception as e:
                log(f"[AMOUNT SYNC WARN] wrap core.{name} failed / {e}")

        log(f"[AMOUNT SYNC] installed domestic wrappers={wrapped_names}")
        _AMOUNT_SYNC_INSTALLED = True


def begin_amount_sync_context(member: Dict[str, Any], signal: Dict[str, Any], tg_id: str) -> None:
    if not AMOUNT_SYNC_ENABLED:
        _sync_clear_ctx()
        return
    target = _sync_target_krw(signal)
    ctx = {
        "enabled": True,
        "member": member,
        "signal": dict(signal or {}),
        "tg_id": str(tg_id or ""),
        "foreign": _norm_exchange(signal.get("foreign") or signal.get("foreign_exchange") or signal.get("exchange")),
        "coin": _norm_coin(signal.get("coin") or signal.get("symbol")),
        "target_krw": target,
        "started_at": time.time(),
    }
    _sync_set_ctx(ctx)


def end_amount_sync_context() -> None:
    ctx = _sync_get_ctx()
    if ctx.get("enabled"):
        fk = _sync_safe_float(ctx.get("foreign_fill_krw"), 0.0)
        target = _sync_safe_float(ctx.get("target_krw"), 0.0)
        if fk > 0:
            diff = abs(fk - target) / max(1.0, target) * 100.0 if target > 0 else 0.0
            log(
                f"[AMOUNT SYNC SUMMARY] tg={ctx.get('tg_id')} {ctx.get('coin')} {ctx.get('foreign')} "
                f"target={target:.0f} foreign_fill={fk:.0f} diff_vs_target={diff:.2f}%"
            )
    _sync_clear_ctx()


# install once at worker startup
install_amount_sync_wrappers()



def _state_files_for_lock() -> List[str]:
    """중복진입 LOCK용 state 파일 탐색.
    주문 전 확인만 수행하며 파일을 수정하지 않는다.
    """
    names = [
        "semi_auto_state_mexc.json",
        "semi_auto_state_gate.json",
        "semi_auto_state_bitget.json",
        "semi_auto_state_bingx.json",
    ]
    paths = []
    for name in names:
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p):
            paths.append(p)
    for p in sorted(glob.glob(os.path.join(BASE_DIR, "semi_auto_state_*.json"))):
        if p not in paths:
            paths.append(p)
    return paths


def _iter_active_positions_for_lock() -> List[Dict[str, Any]]:
    """현재 state 안의 ACTIVE/OPEN 포지션 전체를 읽는다."""
    out: List[Dict[str, Any]] = []
    for path in _state_files_for_lock():
        try:
            data = read_json(path, {})
            positions = data.get("positions") if isinstance(data, dict) else {}
            if isinstance(positions, dict):
                vals = positions.values()
            elif isinstance(positions, list):
                vals = positions
            else:
                vals = []
            for pos in vals:
                if not isinstance(pos, dict):
                    continue
                status = str(pos.get("status") or "").upper()
                if status not in ("ACTIVE", "OPEN", "REAL_OPEN", "VIRTUAL_OPEN", "DOMESTIC_ONLY", "FUTURES_ONLY", "FUTURES_CLOSED_ONLY", "SPOT_CLOSED_ONLY"):
                    continue
                out.append(pos)
        except Exception as e:
            log(f"[ORDER ACTIVE LOCK WARN] read state failed {os.path.basename(path)} / {e}")
    return out


def has_duplicate_active_position(member: Dict[str, Any], signal: Dict[str, Any]) -> Tuple[bool, str]:
    """유저별 같은 코인 + 같은 해외거래소 ACTIVE 중복 진입 차단.
    같은 코인이라도 해외거래소가 다르면 허용한다.
    """
    target_coin = _norm_coin(signal.get("coin") or signal.get("symbol"))
    target_foreign = _norm_exchange(signal.get("foreign") or signal.get("foreign_exchange") or signal.get("exchange"))
    target_user = str(core.get_member_chat_id(member) or member.get("tg_chat_id") or member.get("chat_id") or member.get("user_id") or "").strip()

    if not target_coin or not target_foreign or not target_user:
        return False, ""

    for pos in _iter_active_positions_for_lock():
        pos_coin = _norm_coin(pos.get("coin") or pos.get("symbol"))
        pos_foreign = _norm_exchange(pos.get("foreign") or pos.get("foreign_exchange") or pos.get("exchange"))
        pos_user = str(pos.get("user_id") or pos.get("tg_chat_id") or pos.get("chat_id") or pos.get("telegram_chat_id") or "").strip()

        if pos_coin == target_coin and pos_foreign == target_foreign and pos_user == target_user:
            pos_id = pos.get("pos_id") or pos.get("position_id") or pos.get("id") or ""
            return True, f"{target_coin} {target_foreign} ACTIVE already exists pos_id={pos_id}"

    return False, ""


def get_offset() -> int:
    try:
        if os.path.exists(ORDER_QUEUE_OFFSET_PATH):
            return int(open(ORDER_QUEUE_OFFSET_PATH, "r", encoding="utf-8").read().strip() or "0")
    except Exception:
        pass
    return 0


def set_offset(offset: int) -> None:
    with open(ORDER_QUEUE_OFFSET_PATH, "w", encoding="utf-8") as f:
        f.write(str(int(offset)))


def load_processed() -> Set[str]:
    data = read_json(ORDER_WORKER_PROCESSED_PATH, {})
    if isinstance(data, dict):
        return set(str(k) for k in data.keys())
    return set()


def mark_processed(signal_id: str, result: str) -> None:
    data = read_json(ORDER_WORKER_PROCESSED_PATH, {})
    if not isinstance(data, dict):
        data = {}
    data[str(signal_id)] = {"at": core.now_str(), "result": result}
    # keep size bounded
    if len(data) > 2000:
        for k in list(data.keys())[:500]:
            data.pop(k, None)
    write_json(ORDER_WORKER_PROCESSED_PATH, data)


def build_order_member(raw_member: Dict[str, Any], seen: Set[str]) -> Tuple[str, Dict[str, Any], str]:
    """Validate and normalize one approved member before parallel order execution."""
    raw_tg = str(core.get_member_chat_id(raw_member) or "").strip()
    member = core.merge_member_auto_settings(raw_member)
    tg_id = raw_tg or str(core.get_member_chat_id(member) or "").strip()

    if raw_tg and not str(member.get("tg_chat_id") or member.get("chat_id") or "").strip():
        member["tg_chat_id"] = raw_tg

    if not tg_id:
        return "", member, "missing tg_id"
    if tg_id in seen:
        return "", member, "duplicate tg_id"
    seen.add(tg_id)

    if not core.is_member_service_enabled(member):
        return "", member, "service off"
    if not core.is_member_auto_enabled(member):
        return "", member, "auto off"

    return tg_id, member, ""


def run_member_entry(member: Dict[str, Any], signal: Dict[str, Any], tg_id: str) -> Tuple[str, bool, str]:
    """Run one member order. Exception is converted to fail result so worker keeps running."""
    try:
        dup, reason = has_duplicate_active_position(member, signal)
        if dup:
            return tg_id, False, "[DUPLICATE ACTIVE LOCK] " + reason

        cross_ok, cross_detail = ensure_cross_margin_before_entry(member, signal)
        if not cross_ok:
            notify_cross_guard_fail(tg_id, member, signal, cross_detail)
            return tg_id, False, "[CROSS MARGIN GUARD] " + cross_detail

        log(f"[CROSS GUARD OK] tg={tg_id} {signal.get('coin')} {signal.get('foreign')} / {cross_detail}")
        begin_amount_sync_context(member, signal, tg_id)
        try:
            ok, detail = core.perform_auto_entry_for_member(member, signal)
        finally:
            end_amount_sync_context()
        return tg_id, bool(ok), str(detail)
    except Exception as e:
        return tg_id, False, "EXCEPTION: " + repr(e) + "\n" + traceback.format_exc()


def process_signal(signal: Dict[str, Any]) -> None:
    signal_id = str(signal.get("signal_id") or "")
    if not signal_id:
        log("[ORDER SKIP] signal_id missing")
        return

    members = get_approved_members_cached()
    if not members:
        log("[ORDER SKIP] approved members empty")
        return

    seen: Set[str] = set()
    eligible: List[Tuple[str, Dict[str, Any]]] = []
    skipped = 0

    # Member filtering is still sequential and cheap. Actual order execution is parallel below.
    for raw_member in members:
        tg_id, member, reason = build_order_member(raw_member, seen)
        if not tg_id:
            skipped += 1
            if reason not in ("duplicate tg_id", "missing tg_id"):
                log(f"[ORDER SKIP] {reason} tg={str(core.get_member_chat_id(raw_member) or '').strip()}")
            continue
        eligible.append((tg_id, member))

    if not eligible:
        log(f"[ORDER RESULT] {signal.get('coin')} {signal.get('domestic')}->{signal.get('foreign')} eligible=0 skipped={skipped}")
        return

    max_workers = max(1, min(ORDER_WORKER_MAX_PARALLEL, len(eligible)))
    log(f"[ORDER PARALLEL START] {signal.get('coin')} {signal.get('domestic')}->{signal.get('foreign')} users={len(eligible)} workers={max_workers}")

    ok_count = 0
    fail_count = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(run_member_entry, member, signal, tg_id) for tg_id, member in eligible]
        for fut in as_completed(futures):
            tg_id, ok, detail = fut.result()
            if ok:
                ok_count += 1
                log(f"[ORDER SUCCESS] tg={tg_id} {signal.get('coin')} {signal.get('foreign')} pos={detail}")
            else:
                fail_count += 1
                log(f"[ORDER FAIL/SKIP] tg={tg_id} {signal.get('coin')} {signal.get('foreign')} / {detail}")

    elapsed = time.time() - started
    log(f"[ORDER RESULT] {signal.get('coin')} {signal.get('domestic')}->{signal.get('foreign')} ok={ok_count} fail={fail_count} skipped={skipped} elapsed={elapsed:.2f}s workers={max_workers}")

def poll_once(processed: Set[str]) -> Set[str]:
    if not os.path.exists(ORDER_QUEUE_PATH):
        return processed
    offset = get_offset()
    with open(ORDER_QUEUE_PATH, "rb") as f:
        f.seek(offset)
        while True:
            pos_before = f.tell()
            raw = f.readline()
            if not raw:
                set_offset(pos_before)
                break
            try:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                item = json.loads(line)
                signal = item.get("signal") or {}
                signal_id = str(item.get("signal_id") or signal.get("signal_id") or "")
                queued_ts = float(item.get("queued_ts") or 0.0)
                age = time.time() - queued_ts if queued_ts else 0.0
                if not signal_id:
                    continue
                if signal_id in processed:
                    continue
                if QUEUE_ITEM_MAX_AGE_SEC > 0 and age > QUEUE_ITEM_MAX_AGE_SEC:
                    print(f"[ORDER SKIP] stale signal age={age:.1f}s signal_id={signal_id}")
                    mark_processed(signal_id, "STALE")
                    processed.add(signal_id)
                    continue
                print(f"[ORDER PICK] {signal.get('coin')} {signal.get('domestic')}->{signal.get('foreign')} age={age:.2f}s signal_id={signal_id}")
                process_signal(signal)
                mark_processed(signal_id, "DONE")
                processed.add(signal_id)
            except Exception as e:
                print(f"[ORDER ERROR] {e}")
                traceback.print_exc()
        set_offset(f.tell())
    return processed


def main():
    print("="*70)
    print("K-EDGE V9.5.8 ORDER WORKER PARALLEL + DUPLICATE LOCK + CROSS + AMOUNT SYNC")
    print("Queue:", ORDER_QUEUE_PATH)
    print(f"Parallel workers: {ORDER_WORKER_MAX_PARALLEL}")
    print("Stop: Ctrl+C")
    print("="*70)
    processed = load_processed()
    while True:
        processed = poll_once(processed)
        time.sleep(ORDER_WORKER_POLL_SEC)


if __name__ == "__main__":
    main()
