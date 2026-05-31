# -*- coding: utf-8 -*-
"""
K-EDGE V9.5.5 CLOSE + AUDIT WORKER - GHOST POSITION FIX
- Scanner 4 files stay scanner-only.
- ORDER WORKER handles entries.
- This worker handles exits and periodic position audit in one process.

Main loop:
  1) Load ACTIVE/OPEN positions from all semi_auto_state_*.json files.
  2) Calculate current close-edge using domestic bid + futures ask, BTC baseline adjusted.
  3) If current edge reaches TP/SL conditions, execute foreign short close first, then Bithumb spot sell.
  4) CLOSED only when both sides succeed. Partial states remain retryable.
  5) Every AUDIT interval, log domestic/foreign existence classification to position_audit_log.csv.

Environment:
  CLOSE_WORKER_POLL_SEC=3
  CLOSE_WORKER_MAX_PARALLEL=4
  POSITION_AUDIT_INTERVAL_SEC=300
  POSITION_AUDIT_ENABLED=true
"""

import os
import sys
import csv
import json
import time
import glob
import re
import threading
import traceback
import importlib.util
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POLL_SEC = float(os.getenv("CLOSE_WORKER_POLL_SEC", "3"))
MAX_PARALLEL = int(os.getenv("CLOSE_WORKER_MAX_PARALLEL", "4"))
AUDIT_ENABLED = os.getenv("POSITION_AUDIT_ENABLED", "true").lower() == "true"
AUDIT_INTERVAL_SEC = int(os.getenv("POSITION_AUDIT_INTERVAL_SEC", "300"))
AUDIT_LOG_PATH = os.path.join(BASE_DIR, "position_audit_log.csv")
DUST_KRW = float(os.getenv("POSITION_CHECK_DUST_KRW", "1000"))
PRINT_LOCK = threading.Lock()

# V9.5.5: state file write locks
# - V9.5.4 used _state_lock(path) but the helper itself was missing.
# - This caused NameError and prevented AUDIT from marking ghost/broken positions.
_STATE_LOCKS: Dict[str, threading.Lock] = {}
_STATE_LOCKS_GUARD = threading.Lock()


def _state_lock(path: str) -> threading.Lock:
    key = os.path.abspath(str(path or ""))
    with _STATE_LOCKS_GUARD:
        lock = _STATE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _STATE_LOCKS[key] = lock
        return lock



def log(msg: str) -> None:
    with PRINT_LOCK:
        print(msg, flush=True)


def load_core():
    candidates = []
    candidates += sorted(glob.glob(os.path.join(BASE_DIR, "kedge_v9_5_2_SCAN_QUEUE_MEXC.py")))
    candidates += sorted(glob.glob(os.path.join(BASE_DIR, "kedge*_SCAN_QUEUE_MEXC.py")))
    candidates += sorted(glob.glob(os.path.join(BASE_DIR, "kedge*_MEXC*.py")))
    seen = []
    for p in candidates:
        if p not in seen and os.path.abspath(p) != os.path.abspath(__file__):
            seen.append(p)
    if not seen:
        log("[FATAL] MEXC core file not found")
        sys.exit(1)
    target = seen[-1]
    spec = importlib.util.spec_from_file_location("kedge_core_close_audit", target)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    log(f"[CLOSE+AUDIT WORKER] core loaded: {os.path.basename(target)}")
    return module


core = load_core()

# Worker must have all futures objects for current-edge calculation and close orders.
try:
    core.ENABLE_CALLBACK_POLLER = True
    core.AUTO_CLOSE_ENABLED = True
    _, future_exs = core.init_ccxt_all()
    core.GLOBAL_FUTURE_EXS = core.init_callback_future_exs(future_exs)
    log(f"[CLOSE+AUDIT WORKER] GLOBAL_FUTURE_EXS={sorted(core.GLOBAL_FUTURE_EXS.keys())}")
except Exception as e:
    log(f"[CLOSE+AUDIT WORKER] futures init warning: {e}")


def now_str() -> str:
    try:
        return core.now_str()
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return core.safe_float(v, default)
    except Exception:
        try:
            if v is None or v == "":
                return default
            return float(v)
        except Exception:
            return default


def normalize_symbol(v: Any) -> str:
    try:
        return core.normalize_symbol(str(v or ""))
    except Exception:
        return str(v or "").upper().replace("/", "").replace("_", "").replace("-", "")


def fmt_man_krw(v: Any) -> str:
    try:
        return core.fmt_man_krw(v)
    except Exception:
        n = safe_float(v)
        if abs(n) >= 10000:
            return f"{n/10000:.1f}만"
        return f"{n:,.0f}원"


def read_state_file(path: str) -> Dict[str, Any]:
    try:
        return core._read_state_file(path)
    except Exception:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        data.setdefault("signals", {})
                        data.setdefault("users", {})
                        data.setdefault("positions", {})
                        return data
        except Exception:
            pass
    return {"signals": {}, "users": {}, "positions": {}}


def write_state_file(path: str, state: Dict[str, Any]) -> bool:
    """Thread/process tolerant state writer.

    V9.5.4 fix:
    - CLOSE 병렬 worker가 같은 semi_auto_state_*.json을 동시에 쓰면서
      WinError 32 / PermissionError가 발생했다.
    - 같은 프로세스 내부는 파일별 Lock으로 직렬화한다.
    - 다른 프로세스가 잠깐 잡고 있으면 retry/backoff 한다.
    - 실패해도 CLOSE 감시 루프를 죽이지 않고 다음 루프에서 재시도한다.
    """
    if not path:
        return False
    lock = _state_lock(path)
    last_err = None
    with lock:
        for attempt in range(8):
            try:
                # Core writer keeps existing project atomic format.
                core._write_state_file(path, state)
                return True
            except PermissionError as e:
                last_err = e
            except OSError as e:
                last_err = e
            except Exception as e:
                # fallback writer below
                last_err = e

            try:
                # Unique tmp avoids multiple threads fighting over one .tmp file.
                tmp = f"{path}.tmp.{os.getpid()}.{threading.get_ident()}.{attempt}"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2, default=str)
                os.replace(tmp, path)
                return True
            except PermissionError as e:
                last_err = e
            except OSError as e:
                last_err = e
            except Exception as e:
                last_err = e
            finally:
                try:
                    if 'tmp' in locals() and os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
            time.sleep(0.12 * (attempt + 1))

    log(f"[STATE WRITE WARN] skip path={os.path.basename(path)} err={repr(last_err)}")
    return False


def state_paths() -> List[str]:
    paths = []
    try:
        paths.extend(core._semi_state_known_paths())
    except Exception:
        pass
    paths.extend([
        os.path.join(BASE_DIR, "semi_auto_state_mexc.json"),
        os.path.join(BASE_DIR, "semi_auto_state_gate.json"),
        os.path.join(BASE_DIR, "semi_auto_state_bitget.json"),
        os.path.join(BASE_DIR, "semi_auto_state_bingx.json"),
    ])
    out = []
    for p in paths:
        if p and p not in out:
            out.append(p)
    return out


def load_active_positions_all() -> List[Dict[str, Any]]:
    open_statuses = set(getattr(core, "OPEN_ENTRY_STATUSES", {"OPEN", "ACTIVE", "REAL_OPEN", "VIRTUAL_OPEN", "FUTURES_CLOSED_ONLY", "SPOT_CLOSED_ONLY"}))
    positions: List[Dict[str, Any]] = []
    seen = set()
    for path in state_paths():
        state = read_state_file(path)
        for pos_id, pos in (state.get("positions") or {}).items():
            if not isinstance(pos, dict):
                continue
            status = str(pos.get("status") or "").upper()
            if status not in open_statuses:
                continue
            key = str(pos.get("pos_id") or pos_id)
            if key in seen:
                continue
            seen.add(key)
            item = dict(pos)
            item["pos_id"] = key
            item["_state_path"] = path
            positions.append(item)
    return positions


def update_position_fields(pos: Dict[str, Any], fields: Dict[str, Any]) -> bool:
    pos_id = str(pos.get("pos_id") or "")
    path = str(pos.get("_state_path") or "")
    if not pos_id or not path:
        return False
    try:
        state = read_state_file(path)
        p = state.setdefault("positions", {}).get(pos_id)
        if isinstance(p, dict):
            p.update(fields)
            return write_state_file(path, state)
    except Exception as e:
        log(f"[STATE UPDATE WARN] {pos_id} {os.path.basename(path)} {repr(e)}")
    return False


def mark_position_closed_exact(pos: Dict[str, Any], status: str, current_edge: float, reason: str) -> None:
    pos_id = str(pos.get("pos_id") or "")
    path = str(pos.get("_state_path") or "")
    if not pos_id or not path:
        return
    state = read_state_file(path)
    p = state.setdefault("positions", {}).get(pos_id)
    if isinstance(p, dict):
        before_close = dict(p)
        p["status"] = status
        p["closed_at"] = now_str()
        p["close_edge"] = round(safe_float(current_edge), 4)
        p["close_reason"] = reason
        write_state_file(path, state)
        try:
            core.paper_record_close(pos_id, before_close, status, current_edge, reason)
        except Exception as e:
            log(f"[CLOSE CSV WARN] paper_record_close failed pos={pos_id} / {e}")


def send_pos_msg(pos: Dict[str, Any], title: str, body: str, current_edge: float, vip: bool = False) -> None:
    try:
        entry_edge = safe_float(pos.get("entry_edge"))
        user_id = str(pos.get("user_id") or pos.get("tg_chat_id") or pos.get("chat_id") or "")
        msg = f"""{title}

코인: {pos.get('coin')}
경로: {pos.get('domestic')} 현물 + {pos.get('foreign')} 선물숏
금액: {fmt_man_krw(pos.get('amount_krw') or pos.get('domestic_entry_krw'))}

진입 실제엣지: {entry_edge:+.2f}%
현재 실제엣지: {safe_float(current_edge):+.2f}%
상태: {pos.get('status', 'ACTIVE')}

{body}

🕒 {now_str()}"""
        if user_id:
            core.telegram_send_private(user_id, msg)
        if vip:
            core.telegram_send(msg)
    except Exception as e:
        log(f"[CLOSE DM WARN] {e}")



# ============================================================
# V9.5.6 LIVE DASHBOARD TP PUSH
# - CLOSE 성공 시 홈페이지 LIVE 대시보드에 TP_SUCCESS를 기록한다.
# - 실패해도 청산/상태저장 로직에는 영향 주지 않는다.
# ============================================================
def _live_iso_now() -> str:
    try:
        return datetime.now().isoformat(timespec="seconds")
    except Exception:
        return now_str()


def _live_headers() -> Dict[str, str]:
    key = str(getattr(core, "SUPABASE_SERVICE_KEY", "") or "")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _live_request(url: str, payload: Dict[str, Any], method: str = "post"):
    sess = getattr(core, "session", None)
    if sess is None:
        return None
    if method == "patch":
        return sess.patch(url, headers=_live_headers(), data=json.dumps(payload, ensure_ascii=False), timeout=8)
    return sess.post(url, headers=_live_headers(), data=json.dumps(payload, ensure_ascii=False), timeout=8)


def push_live_event_tp_success(pos: Dict[str, Any], current_edge: float, close_detail: str, reason: str) -> None:
    """홈페이지 공개 LIVE 이벤트에 익절완료를 저장한다."""
    try:
        supabase_url = str(getattr(core, "SUPABASE_URL", "") or "").rstrip("/")
        service_key = str(getattr(core, "SUPABASE_SERVICE_KEY", "") or "")
        if not supabase_url or not service_key:
            log("[LIVE TP] Supabase 설정 없음 - TP_SUCCESS 저장 스킵")
            return

        symbol = normalize_symbol(pos.get("coin"))
        domestic = str(pos.get("domestic") or pos.get("domestic_exchange") or "BITHUMB").upper()
        foreign = str(pos.get("foreign") or pos.get("foreign_exchange") or pos.get("exchange") or "").upper()
        entry_edge = safe_float(pos.get("entry_edge") or pos.get("entry_real_edge") or pos.get("real_edge"))
        entry_krw = safe_float(
            pos.get("domestic_entry_krw")
            or pos.get("amount_krw")
            or pos.get("final_entry_krw")
            or pos.get("entry_krw")
            or 0
        )

        event_row = {
            "event_type": "TP_SUCCESS",
            "symbol": symbol,
            "domestic_exchange": domestic,
            "foreign_exchange": foreign,
            "real_edge_percent": round(safe_float(current_edge), 4),
            "entry_edge_percent": round(entry_edge, 4),
            "executable_krw": int(entry_krw),
            "created_at": _live_iso_now(),
        }

        url = f"{supabase_url}/rest/v1/kedge_live_events"
        r = _live_request(url, event_row, "post")
        if r is None or r.status_code not in (200, 201):
            log(f"[LIVE TP] TP_SUCCESS 저장 실패 status={getattr(r, 'status_code', None)} body={getattr(r, 'text', '')[:250] if r is not None else ''}")
            return

        summary_row = {
            "bot_status": "RUNNING",
            "last_scan_at": _live_iso_now(),
            "updated_at": _live_iso_now(),
        }
        for summary_id in ("1", "main"):
            try:
                s_url = f"{supabase_url}/rest/v1/kedge_live_summary?id=eq.{summary_id}"
                sr = _live_request(s_url, summary_row, "patch")
                if sr is not None and sr.status_code in (200, 204):
                    break
            except Exception:
                pass

        log(f"[LIVE TP] TP_SUCCESS 저장 완료 {symbol} {domestic}->{foreign} edge={safe_float(current_edge):+.2f}%")
    except Exception as e:
        log(f"[LIVE TP] TP_SUCCESS PUSH 예외 {repr(e)}")


def calc_current_close_edge(pos: Dict[str, Any]) -> Tuple[Optional[float], str]:
    """Calculate close edge using executable close prices.

    Close action: sell domestic spot at bid, buy futures short at ask.
    Basis close = futures ask / domestic bid(USDT) - 1, minus BTC basis using same side.
    """
    try:
        coin = normalize_symbol(pos.get("coin"))
        source = str(pos.get("domestic") or pos.get("domestic_exchange") or "").upper()
        future_name = str(pos.get("foreign") or pos.get("foreign_exchange") or "").upper()
        usd_krw = safe_float(pos.get("usd_krw"), safe_float(getattr(core, "FALLBACK_USD_KRW", 1509.0), 1509.0))
        if not coin or not source or not future_name:
            return None, "coin/domestic/foreign missing"

        spot = core.fetch_current_domestic_book_for_signal(pos)
        if not spot:
            return None, "domestic book failed"
        spot_bid_usdt = safe_float(spot.get("best_bid")) / max(1.0, usd_krw)
        if spot_bid_usdt <= 0:
            return None, "domestic best_bid invalid"

        fex = core.GLOBAL_FUTURE_EXS.get(future_name)
        if not fex:
            return None, f"future exchange object missing {future_name}"
        fmarket = pos.get("foreign_market") or core.find_future_market(fex, coin)
        if not fmarket:
            return None, f"future market missing {future_name} {coin}"
        future_book = core.fetch_ccxt_book(fex, fmarket, is_future=True)
        if not future_book:
            return None, "future book failed"
        future_ask = safe_float(future_book.get("best_ask") or future_book.get("ask"))
        if future_ask <= 0:
            return None, "future best_ask invalid"

        basis_now = core.calc_basis_percent(future_ask, spot_bid_usdt)

        btc_basis_now = safe_float(pos.get("btc_gap"), 0.0)
        try:
            btc_spot = core.fetch_current_btc_spot_for_source(source)
            if btc_spot:
                btc_market = core.find_future_market(fex, "BTC")
                btc_future = core.fetch_ccxt_book(fex, btc_market, is_future=True) if btc_market else None
                if btc_future:
                    btc_spot_bid_usdt = safe_float(btc_spot.get("best_bid")) / max(1.0, usd_krw)
                    btc_future_ask = safe_float(btc_future.get("best_ask") or btc_future.get("ask"))
                    if btc_spot_bid_usdt > 0 and btc_future_ask > 0:
                        btc_basis_now = core.calc_basis_percent(btc_future_ask, btc_spot_bid_usdt)
        except Exception as e:
            log(f"[CLOSE EDGE BTC WARN] {coin} {future_name} / {e}")

        edge_now = basis_now - btc_basis_now
        return edge_now, f"basis={basis_now:+.4f}% btc={btc_basis_now:+.4f}% market={fmarket}"
    except Exception as e:
        return None, "edge exception: " + repr(e)


def should_close(pos: Dict[str, Any], current_edge: float) -> Tuple[bool, str, str]:
    """return=(should_close, status_when_success, reason)"""
    entry_edge = safe_float(pos.get("entry_edge"))
    tp_edge = safe_float(pos.get("take_profit_edge"), safe_float(getattr(core, "AUTO_TAKE_PROFIT_EDGE_PERCENT", 0.3), 0.3))
    tp_force = safe_float(pos.get("take_profit_force_edge"), safe_float(getattr(core, "AUTO_TAKE_PROFIT_FORCE_EDGE_PERCENT", 0.3), 0.3))
    stop_watch_edge = safe_float(pos.get("stop_watch_edge"), entry_edge + safe_float(getattr(core, "AUTO_STOP_WATCH_EDGE_ADD_PERCENT", 8.0), 8.0))
    stop_hold_sec = int(getattr(core, "AUTO_STOP_HOLD_SEC", 900))
    now_ts = time.time()

    if current_edge <= tp_edge:
        label = "TP_FORCE" if current_edge <= tp_force else "TP_TRIGGER"
        return True, "AUTO_CLOSED", f"{label}: current_edge {current_edge:+.2f}% <= target {tp_edge:+.2f}%"

    if current_edge >= stop_watch_edge:
        started = safe_float(pos.get("stop_watch_started_ts"), 0.0)
        if started <= 0:
            update_position_fields(pos, {"stop_watch_started_ts": now_ts, "stop_watch_started_at": now_str()})
            send_pos_msg(pos, "⏱ 자동손절 감시 시작", f"손절 감시 기준 도달: {current_edge:+.2f}% >= {stop_watch_edge:+.2f}%\n{stop_hold_sec//60}분 유지 시 자동손절합니다.", current_edge, vip=True)
            return False, "", "STOP_WATCH_STARTED"
        hold_sec = now_ts - started
        if hold_sec >= stop_hold_sec:
            return True, "AUTO_STOPPED", f"STOP_TRIGGER: current_edge {current_edge:+.2f}% >= {stop_watch_edge:+.2f}% for {hold_sec:.0f}s"
        return False, "", f"STOP_WATCHING remain={max(0, int(stop_hold_sec-hold_sec))}s"

    if safe_float(pos.get("stop_watch_started_ts"), 0.0) > 0:
        update_position_fields(pos, {"stop_watch_started_ts": 0, "stop_watch_started_at": None, "stop_watch_last_notice_ts": 0})
        send_pos_msg(pos, "✅ 자동손절 감시 해제", "실제엣지가 손절 감시 기준 아래로 회귀했습니다. 포지션은 유지됩니다.", current_edge)

    return False, "", "HOLD"


def process_one_position(pos: Dict[str, Any]) -> Tuple[str, str]:
    pos_id = str(pos.get("pos_id") or "")
    coin = normalize_symbol(pos.get("coin"))
    route = f"{pos.get('domestic')}->{pos.get('foreign')}"
    try:
        current_edge, detail = calc_current_close_edge(pos)
        if current_edge is None:
            # transient API/rate-limit failure: do not write state every poll
            return pos_id, f"EDGE_FAIL {coin} {route} / {detail}"

        # V9.5.4: HOLD 상태에서 매 루프 state 파일을 쓰지 않는다.
        # 파일 충돌 방지. 실제 청산/실패/손절감시 상태 변화 때만 저장한다.
        pos["last_current_edge"] = round(current_edge, 4)
        pos["last_close_checked_at"] = now_str()
        pos["last_close_edge_detail"] = detail
        close_now, success_status, reason = should_close(pos, current_edge)
        if not close_now:
            return pos_id, f"HOLD {coin} {route} edge={current_edge:+.2f}% / {reason}"

        log(f"[CLOSE TRY] {coin} {route} pos={pos_id} edge={current_edge:+.2f}% / {reason}")
        ok, close_detail = core.execute_auto_close_orders(pos, current_edge)
        if ok:
            mark_position_closed_exact(pos, success_status, current_edge, close_detail)
            if success_status == "AUTO_CLOSED":
                push_live_event_tp_success(pos, current_edge, close_detail, reason)
            send_pos_msg(pos, "✅ 자동익절 완료" if success_status == "AUTO_CLOSED" else "❌ 자동손절 실행 완료", f"결과:\n{close_detail}\n\n조건: {reason}", current_edge, vip=True)
            return pos_id, f"CLOSED {coin} {route} status={success_status} edge={current_edge:+.2f}%"

        # No position to close -> do not keep ACTIVE forever.
        no_position_close = ("No position to close" in str(close_detail) or '"code":"22002"' in str(close_detail))
        update_fields = {
            "last_close_failed_at": now_str(),
            "last_close_failed_edge": round(current_edge, 4),
            "last_close_failed_detail": close_detail,
        }
        if no_position_close:
            update_fields["status"] = "GHOST_PENDING_AUDIT"
        if "상태제안: FUTURES_CLOSED_ONLY" in str(close_detail):
            update_fields.update({"status": "FUTURES_CLOSED_ONLY", "futures_closed": True, "spot_closed": False})
        elif "상태제안: SPOT_CLOSED_ONLY" in str(close_detail):
            update_fields.update({"status": "SPOT_CLOSED_ONLY", "spot_closed": True, "futures_closed": False})
        update_position_fields(pos, update_fields)
        send_pos_msg(pos, "🚨 자동청산 실패 - CLOSED 금지", f"둘 다 성공하지 못해 CLOSED 처리하지 않았습니다. 다음 루프에서 재시도합니다.\n\n결과:\n{close_detail}\n\n조건: {reason}", current_edge, vip=True)
        return pos_id, f"CLOSE_FAIL {coin} {route} edge={current_edge:+.2f}% / {str(close_detail)[:200]}"
    except Exception as e:
        tb = traceback.format_exc()
        update_position_fields(pos, {"last_close_exception_at": now_str(), "last_close_exception": repr(e)})
        return pos_id, f"EXCEPTION {coin} {route} / {repr(e)}\n{tb}"


def close_cycle() -> None:
    positions = load_active_positions_all()
    if not positions:
        log(f"[CLOSE] ACTIVE positions=0 / {now_str()}")
        return
    workers = max(1, min(MAX_PARALLEL, len(positions)))
    log(f"[CLOSE] ACTIVE positions={len(positions)} workers={workers} / {now_str()}")
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futs = [executor.submit(process_one_position, p) for p in positions]
        for fut in as_completed(futs):
            _, msg = fut.result()
            log("[CLOSE RESULT] " + msg)


# -------------------------
# Lightweight audit section
# -------------------------

def append_audit_log(row: Dict[str, Any]) -> None:
    fields = [
        "checked_at", "pos_id", "state_file", "user_id", "coin", "domestic", "foreign", "status",
        "domestic_value_krw", "foreign_notional_usdt", "foreign_value_krw", "classification", "error"
    ]
    exists = os.path.exists(AUDIT_LOG_PATH)
    with open(AUDIT_LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def get_bithumb_value_krw(member: Dict[str, Any], pos: Dict[str, Any]) -> Tuple[float, str]:
    coin = normalize_symbol(pos.get("coin"))
    try:
        creds = core.get_api_credentials_priority(member, "BITHUMB", "spot")
        raw = core.bithumb_v2_accounts_direct(creds.get("api_key"), creds.get("secret")).get("raw")
        qty = 0.0
        locked = 0.0
        if isinstance(raw, list):
            for item in raw:
                if str(item.get("currency") or "").upper() == coin:
                    qty = safe_float(item.get("balance"))
                    locked = safe_float(item.get("locked"))
                    break
        book = core.fetch_current_domestic_book_for_signal(pos)
        bid = safe_float((book or {}).get("best_bid"))
        return (qty + locked) * bid, "ok"
    except Exception as e:
        return 0.0, str(e)


def _compact_symbol(v: Any) -> str:
    """Normalize exchange symbols for robust matching: BILL/USDT:USDT -> BILLUSDT."""
    return re.sub(r"[^A-Z0-9]", "", str(v or "").upper())


def _extract_first_positive(*values: Any) -> float:
    for v in values:
        n = abs(safe_float(v, 0.0))
        if n > 0:
            return n
    return 0.0


def get_foreign_notional_usdt(member: Dict[str, Any], pos: Dict[str, Any]) -> Tuple[float, str]:
    """Return current futures position notional in USDT.

    MEXC AUDIT fix:
    - MEXC may return coin amount/holdVol separately from price.
    - ccxt notional can be empty or tiny on some symbols.
    - We now match symbols robustly and calculate notional from raw fields.
    """
    foreign = str(pos.get("foreign") or "").lower()
    coin = normalize_symbol(pos.get("coin"))
    coin_u = coin.upper()
    try:
        ex = core.build_user_exchange_from_member(member, foreign, "future")
        if ex is None:
            return 0.0, "future api object missing"
        try:
            ex.load_markets()
        except Exception:
            pass

        market = pos.get("foreign_market") or core.find_future_market(ex, coin)
        market_u = str(market or "").upper()
        market_compact = _compact_symbol(market_u)
        coin_usdt = f"{coin_u}USDT"

        try:
            positions = ex.fetch_positions([market]) if market else ex.fetch_positions()
        except Exception:
            positions = ex.fetch_positions()

        best_notional = 0.0
        debug_best = ""

        for p in positions or []:
            if not isinstance(p, dict):
                continue

            info = p.get("info") if isinstance(p.get("info"), dict) else {}
            sym = str(p.get("symbol") or info.get("symbol") or info.get("market") or "").upper()
            info_text = json.dumps(info, ensure_ascii=False, default=str).upper()
            sym_compact = _compact_symbol(sym)
            info_compact = _compact_symbol(info_text)

            matched = False
            if market_u and sym == market_u:
                matched = True
            elif market_compact and sym_compact == market_compact:
                matched = True
            elif coin_usdt and (coin_usdt in sym_compact or coin_usdt in info_compact):
                matched = True
            elif coin_u and (coin_u in sym_compact or coin_u in info_text):
                matched = True

            if not matched:
                continue

            contracts = _extract_first_positive(
                p.get("contracts"),
                p.get("contractSize"),
                p.get("amount"),
                info.get("holdVol"),
                info.get("positionAmt"),
                info.get("size"),
                info.get("vol"),
                info.get("availableVol"),
                info.get("positionSize"),
            )

            notional = _extract_first_positive(
                p.get("notional"),
                p.get("initialMargin"),
                info.get("notional"),
                info.get("positionValue"),
                info.get("holdValue"),
                info.get("value"),
                info.get("position_value"),
                info.get("marginValue"),
                info.get("nominalValue"),
            )

            price = _extract_first_positive(
                p.get("markPrice"),
                p.get("entryPrice"),
                p.get("lastPrice"),
                info.get("markPrice"),
                info.get("fairPrice"),
                info.get("lastPrice"),
                info.get("avgPrice"),
                info.get("openAvgPrice"),
                info.get("entryPrice"),
                info.get("holdAvgPrice"),
            )

            contract_size = 1.0
            try:
                m = ex.markets.get(market) if market and hasattr(ex, "markets") else None
                if isinstance(m, dict):
                    contract_size = _extract_first_positive(
                        m.get("contractSize"),
                        (m.get("info") or {}).get("contractSize"),
                        (m.get("info") or {}).get("cs"),
                    ) or 1.0
            except Exception:
                contract_size = 1.0

            if notional <= 0 and contracts > 0 and price > 0:
                notional = contracts * contract_size * price

            raw_amount = _extract_first_positive(
                info.get("holdVol"),
                info.get("vol"),
                info.get("positionAmt"),
                info.get("size"),
                info.get("availableVol"),
            )
            if raw_amount > 0 and price > 0:
                notional = max(notional, raw_amount * contract_size * price, raw_amount * price)

            # Safety: if direct notional is suspiciously tiny but raw position exists,
            # keep recalculated value. This fixes false f=344 KRW on MEXC BILL.
            if notional > best_notional:
                best_notional = notional
                debug_best = f"sym={sym or info.get('symbol')} contracts={contracts} price={price} contractSize={contract_size} notional={notional}"

        if best_notional <= 0:
            return 0.0, f"ok/no_position_found market={market} coin={coin}"
        return best_notional, f"ok {debug_best}"
    except Exception as e:
        return 0.0, str(e)


def audit_one(pos: Dict[str, Any]) -> str:
    pos_id = str(pos.get("pos_id") or "")
    user_id = str(pos.get("user_id") or "")
    coin = normalize_symbol(pos.get("coin"))
    usd_krw = safe_float(pos.get("usd_krw"), safe_float(getattr(core, "FALLBACK_USD_KRW", 1509.0), 1509.0))
    row: Dict[str, Any] = {
        "checked_at": now_str(),
        "pos_id": pos_id,
        "state_file": os.path.basename(str(pos.get("_state_path") or "")),
        "user_id": user_id,
        "coin": coin,
        "domestic": pos.get("domestic"),
        "foreign": pos.get("foreign"),
        "status": pos.get("status"),
        "error": "",
    }
    try:
        member = core.find_member_by_telegram_id(user_id)
        if not member:
            row["classification"] = "조회불가(회원없음)"
            row["error"] = f"member not found user_id={user_id}"
            append_audit_log(row)
            return f"AUDIT_FAIL {coin} member missing"
        d_value, d_err = get_bithumb_value_krw(member, pos)
        f_notional, f_err = get_foreign_notional_usdt(member, pos)
        f_value = f_notional * max(1.0, usd_krw)
        row["domestic_value_krw"] = round(d_value, 4)
        row["foreign_notional_usdt"] = round(f_notional, 8)
        row["foreign_value_krw"] = round(f_value, 4)
        if d_err != "ok":
            row["error"] += f"domestic={d_err} "
        if f_err != "ok":
            row["error"] += f"foreign={f_err} "
        domestic_has = d_value > DUST_KRW
        foreign_has = f_value > DUST_KRW
        if domestic_has and foreign_has:
            cls = "정상_ACTIVE(국내O/해외O)"
            row["classification"] = cls
            append_audit_log(row)
            return f"{coin} {cls} d={d_value:.0f} f={f_value:.0f}"

        elif not domestic_has and not foreign_has:
            # V9.5.5 핵심:
            # 국내도 dust 이하, 해외 선물도 0이면 실제로는 더 이상 청산할 포지션이 아니다.
            # ACTIVE로 유지하면 Bitget/MEXC/Gate/BingX에서 "No position to close"를 계속 반복한다.
            cls = "유령종료(GHOST_CLOSED:국내X/해외X)"
            row["classification"] = cls
            append_audit_log(row)
            update_position_fields(pos, {
                "status": "GHOST_CLOSED",
                "closed_at": now_str(),
                "close_reason": "AUDIT_GHOST_NO_DOMESTIC_NO_FOREIGN",
                "last_audit_at": now_str(),
                "last_audit_classification": cls,
                "domestic_exists": False,
                "foreign_exists": False,
                "domestic_value_krw": round(d_value, 4),
                "foreign_value_krw": round(f_value, 4),
            })
            try:
                core.paper_record_close(pos_id, pos, "GHOST_CLOSED", safe_float(pos.get("last_current_edge"), 0.0), "AUDIT_GHOST_NO_DOMESTIC_NO_FOREIGN")
            except Exception as e:
                log(f"[GHOST CLOSE CSV WARN] {pos_id} {e}")
            return f"{coin} {cls} d={d_value:.0f} f={f_value:.0f}"

        elif domestic_has and not foreign_has:
            # 해외 숏이 0인데 국내 현물이 남아 있으면 헤지가 깨진 상태.
            # 지금은 임의 매도하지 않고 ACTIVE 재시도를 멈추기 위해 별도 상태로 격리한다.
            cls = "비대칭격리(BROKEN_DOMESTIC_ONLY:국내O/해외X)"
            row["classification"] = cls
            append_audit_log(row)
            update_position_fields(pos, {
                "status": "BROKEN_DOMESTIC_ONLY",
                "last_audit_at": now_str(),
                "last_audit_classification": cls,
                "domestic_exists": True,
                "foreign_exists": False,
                "domestic_value_krw": round(d_value, 4),
                "foreign_value_krw": round(f_value, 4),
            })
            return f"{coin} {cls} d={d_value:.0f} f={f_value:.0f}"

        else:
            # 국내 현물은 없고 해외 숏만 남은 상태. 이것도 ACTIVE 재시도 대상이 아니라 별도 격리.
            cls = "비대칭격리(BROKEN_FOREIGN_ONLY:국내X/해외O)"
            row["classification"] = cls
            append_audit_log(row)
            update_position_fields(pos, {
                "status": "BROKEN_FOREIGN_ONLY",
                "last_audit_at": now_str(),
                "last_audit_classification": cls,
                "domestic_exists": False,
                "foreign_exists": True,
                "domestic_value_krw": round(d_value, 4),
                "foreign_value_krw": round(f_value, 4),
            })
            return f"{coin} {cls} d={d_value:.0f} f={f_value:.0f}"
    except Exception as e:
        row["classification"] = "AUDIT_EXCEPTION"
        row["error"] = repr(e)
        append_audit_log(row)
        return f"AUDIT_EXCEPTION {coin} {repr(e)}"


def audit_cycle() -> None:
    if not AUDIT_ENABLED:
        return
    positions = load_active_positions_all()
    log(f"[AUDIT] ACTIVE positions={len(positions)} / {now_str()}")
    for pos in positions:
        log("[AUDIT RESULT] " + audit_one(pos))


def main() -> None:
    log("=" * 70)
    log("K-EDGE V9.5.5 CLOSE + AUDIT WORKER - GHOST POSITION FIX")
    log(f"Poll: {POLL_SEC}s / Close workers: {MAX_PARALLEL} / Audit: {AUDIT_ENABLED} every {AUDIT_INTERVAL_SEC}s")
    log("Stop: Ctrl+C")
    log("=" * 70)
    last_audit_at = 0.0
    while True:
        try:
            close_cycle()
            if AUDIT_ENABLED and (time.time() - last_audit_at >= AUDIT_INTERVAL_SEC):
                audit_cycle()
                last_audit_at = time.time()
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log(f"[CLOSE+AUDIT ERROR] {e}")
            traceback.print_exc()
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
