# -*- coding: utf-8 -*-
"""
K-EDGE V9.5.14 TELEGRAM MENU WORKER - POSITIONS MARGIN/LEVERAGE + CURRENT EDGE

핵심:
- @Kedge0203bot 토큰 자동 선택
- /start, 메뉴 입력 시 하단 고정 버튼(reply_keyboard) 전송
- 📊 포지션조회 / 📉 현재엣지 / 📈 통계조회 / 🛑 자동정지 / ▶ 자동시작
- 조회/통계는 읽기 전용
"""

import os
import json
import time
import glob
import traceback
import importlib.util
from pathlib import Path

try:
    import requests
except Exception:
    requests = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_BOT_USERNAME = os.environ.get("KEDGE_MENU_BOT_USERNAME", "Kedge0203bot").strip().lstrip("@")
OFFSET_PATH = os.path.join(BASE_DIR, "telegram_menu_worker.offset")
MENU_LOG_PREFIX = "[MENU WORKER]"


def load_core():
    candidates = []
    candidates += sorted(glob.glob(os.path.join(BASE_DIR, "kedge_v9_5_2_SCAN_QUEUE_MEXC.py")))
    candidates += sorted(glob.glob(os.path.join(BASE_DIR, "kedge*_SCAN_QUEUE_MEXC.py")))
    candidates += sorted(glob.glob(os.path.join(BASE_DIR, "kedge*_MEXC*.py")))
    seen = []
    for p in candidates:
        if p not in seen:
            seen.append(p)
    if not seen:
        print("[치명] core MEXC 파일을 찾을 수 없습니다.")
        return None

    target = seen[-1]
    try:
        spec = importlib.util.spec_from_file_location("kedge_core", target)
        core = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(core)
        print(f"{MENU_LOG_PREFIX} core loaded: {os.path.basename(target)}")
        return core
    except Exception as e:
        print("[치명] core 로드 실패:", e)
        traceback.print_exc()
        return None


core = load_core()


def looks_like_bot_token(s):
    if not isinstance(s, str):
        return False
    s = s.strip()
    if len(s) < 30 or ":" not in s:
        return False
    left, right = s.split(":", 1)
    return left.isdigit() and len(right) >= 20


def collect_token_candidates():
    tokens = []

    for name in [
        "KEDGE_COMMON_BOT_TOKEN",
        "KEDGE_MENU_BOT_TOKEN",
        "COMMON_TELEGRAM_BOT_TOKEN",
        "COMMON_BOT_TOKEN",
        "KEDGE_BOT_TOKEN",
    ]:
        val = os.environ.get(name, "").strip()
        if looks_like_bot_token(val):
            tokens.append((name, val))

    for fname in [
        "kedge_common_bot_token.txt",
        "kedge_menu_bot_token.txt",
        "common_bot_token.txt",
    ]:
        p = os.path.join(BASE_DIR, fname)
        if os.path.exists(p):
            try:
                val = Path(p).read_text(encoding="utf-8").strip()
                if looks_like_bot_token(val):
                    tokens.append((fname, val))
            except Exception:
                pass

    if core:
        priority_names = [
            "COMMON_TELEGRAM_BOT_TOKEN",
            "COMMON_BOT_TOKEN",
            "KEDGE_COMMON_BOT_TOKEN",
            "KEDGE_COMMON_BOT_TOKEN_DEFAULT",
            "KEDGE_BOT_TOKEN",
            "AUTO_COMMON_BOT_TOKEN",
            "TELEGRAM_COMMON_BOT_TOKEN",
        ]

        for name in priority_names:
            val = getattr(core, name, None)
            if looks_like_bot_token(val):
                tokens.append((f"core.{name}", val.strip()))

        for name in dir(core):
            if name.startswith("__"):
                continue
            try:
                val = getattr(core, name)
            except Exception:
                continue
            if looks_like_bot_token(val):
                tokens.append((f"core.{name}", val.strip()))

    dedup = []
    seen = set()
    for src, tok in tokens:
        if tok not in seen:
            seen.add(tok)
            dedup.append((src, tok))
    return dedup


def test_token(token):
    if requests is None:
        raise RuntimeError("requests 모듈이 없습니다. pip install requests 필요")
    url = f"https://api.telegram.org/bot{token}/getMe"
    r = requests.post(url, json={}, timeout=10)
    try:
        data = r.json()
    except Exception:
        data = {"ok": False, "raw": r.text}
    return r.status_code, data


def select_bot_token():
    candidates = collect_token_candidates()
    print(f"{MENU_LOG_PREFIX} token candidates={len(candidates)} / target=@{TARGET_BOT_USERNAME}")

    fallback = None

    for src, tok in candidates:
        masked = tok[:10] + "..." + tok[-6:]
        try:
            code, data = test_token(tok)
            username = ((data.get("result") or {}).get("username") or "")
            ok = data.get("ok")
            print(f"{MENU_LOG_PREFIX} token test src={src} token={masked} ok={ok} username=@{username}")
            if ok and username == TARGET_BOT_USERNAME:
                print(f"{MENU_LOG_PREFIX} SELECTED BOT @{TARGET_BOT_USERNAME} from {src}")
                return tok
            if ok and fallback is None:
                fallback = (src, tok, data)
        except Exception as e:
            print(f"{MENU_LOG_PREFIX} token test fail src={src} token={masked} err={e}")

    print("")
    print("[치명] @Kedge0203bot 토큰을 찾지 못했습니다.")
    print("해결방법: yang 폴더에 kedge_common_bot_token.txt 파일을 만들고 @Kedge0203bot 토큰 전체를 첫 줄에 넣으세요.")
    if fallback:
        src, tok, data = fallback
        uname = ((data.get("result") or {}).get("username") or "")
        print(f"[참고] 찾은 봇은 @{uname} 입니다. 목표 봇이 아닙니다: {src}")
    raise SystemExit(1)


BOT_TOKEN = select_bot_token()


def tg_api(method, payload=None, timeout=15):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    r = requests.post(url, json=payload or {}, timeout=timeout)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text}


def reply_keyboard_markup():
    return {
        "keyboard": [
            [
                {"text": "📊 포지션조회"},
                {"text": "📉 현재엣지"},
            ],
            [
                {"text": "📈 통계조회"},
                {"text": "🛑 자동정지"},
            ],
            [
                {"text": "▶ 자동시작"},
            ],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "is_persistent": True,
        "input_field_placeholder": "K-EDGE 메뉴를 선택하세요",
    }


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    code, data = tg_api("sendMessage", payload)
    print(f"{MENU_LOG_PREFIX} sendMessage chat={chat_id} code={code} ok={data.get('ok')}")
    if not data.get("ok"):
        print(f"{MENU_LOG_PREFIX} sendMessage error={data}")
    return data


def send_main_menu(chat_id):
    text = (
        "🤖 <b>K-EDGE AUTO 메뉴</b>\n\n"
        "아래 고정 버튼에서 원하는 기능을 선택하세요.\n\n"
        "📊 포지션조회: 현재 보유 포지션 확인\n"
        "📉 현재엣지: 포지션별 현재엣지/익절거리 확인\n"
        "📈 통계조회: 누적/일별 통계 확인\n"
        "🛑 자동정지: 신규 자동진입 정지\n"
        "▶ 자동시작: 자동진입 재시작\n\n"
        "※ 조회 기능은 읽기 전용이며 주문/청산을 실행하지 않습니다."
    )
    return send_message(chat_id, text, reply_keyboard_markup())


def safe_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def fmt_krw(v):
    v = safe_float(v)
    if abs(v) >= 100000000:
        return f"{v/100000000:.2f}억"
    if abs(v) >= 10000:
        return f"{v/10000:.1f}만"
    return f"{v:,.0f}원"



def fmt_pct(v, default="-"):
    try:
        if v is None or v == "":
            return default
        return f"{float(v):+.2f}%"
    except Exception:
        return str(v) if v not in (None, "") else default


def fmt_int(v):
    try:
        return f"{int(float(v)):,}"
    except Exception:
        return "0"


def html_escape(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def read_json_safe(path, default=None):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"{MENU_LOG_PREFIX} json read fail {path}: {e}")
    return default


def read_csv_rows_safe(path):
    rows = []
    try:
        import csv
        if not os.path.exists(path):
            return rows
        with open(path, "r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"{MENU_LOG_PREFIX} csv read fail {path}: {e}")
    return rows

def find_paper_entries_file():
    candidates = [
        os.path.join(BASE_DIR, "paper_trading_data", "paper_entries.csv"),
        os.path.join(BASE_DIR, "paper_entries.csv"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def _csv_get(row, *keys, default=""):
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return v
    return default


def load_open_positions_from_paper_entries(chat_id=None):
    path = find_paper_entries_file()
    if not path:
        print(f"{MENU_LOG_PREFIX} paper_entries.csv not found")
        return []

    rows = read_csv_rows_safe(path)
    out = []
    chat_id = str(chat_id or "").strip()
    open_statuses = {
        "OPEN", "ACTIVE", "REAL_OPEN", "VIRTUAL_OPEN",
        "FUTURES_CLOSED_ONLY", "SPOT_CLOSED_ONLY",
        "DOMESTIC_ONLY", "FUTURES_ONLY",
        "ENTRY_SUCCESS", "SUCCESS", "FILLED",
    }
    closed_words = ["CLOSED", "AUTO_CLOSED", "STOPPED", "CANCEL", "FAIL", "ERROR"]

    for r in rows:
        if not isinstance(r, dict):
            continue

        status_raw = str(_csv_get(r, "status", "entry_status", "position_status", default="OPEN") or "OPEN").upper()
        if any(w in status_raw for w in closed_words) and status_raw not in {"FUTURES_CLOSED_ONLY", "SPOT_CLOSED_ONLY"}:
            continue
        if status_raw not in open_statuses:
            closed_at = str(_csv_get(r, "closed_at", "close_time", "exit_time", default="")).strip()
            if closed_at:
                continue

        uid = str(_csv_get(
            r,
            "user_id", "tg_chat_id", "chat_id", "telegram_chat_id",
            "telegram_id", "member_chat_id",
            default=""
        )).strip()

        if chat_id and uid and uid != chat_id:
            continue
        if chat_id and not uid:
            continue

        pos = {
            "status": "ACTIVE" if status_raw in ("ENTRY_SUCCESS", "SUCCESS", "FILLED") else status_raw,
            "coin": _csv_get(r, "coin", "symbol", "base", "ticker"),
            "domestic": _csv_get(r, "domestic", "domestic_exchange", "domestic_name", default="BITHUMB"),
            "foreign": _csv_get(r, "foreign", "foreign_exchange", "exchange", "future_exchange"),
            "tg_chat_id": uid,
            "user_id": uid,
            "pos_id": _csv_get(r, "pos_id", "position_id", "id", "position_key", "signal_id"),
            "position_id": _csv_get(r, "pos_id", "position_id", "id", "position_key", "signal_id"),
            "entry_edge": _csv_get(r, "entry_edge", "entry_real_edge", "real_edge", "detected_edge", "entry_edge_percent"),
            "domestic_entry_krw": _csv_get(r, "domestic_entry_krw", "domestic_amount_krw", "entry_krw", "amount_krw", "final_entry_krw"),
            "foreign_entry_krw": _csv_get(r, "foreign_entry_krw", "foreign_notional_krw", "foreign_amount_krw", "final_entry_krw"),
            "opened_at": _csv_get(r, "opened_at", "entry_time", "created_at", "event_time", "queued_at"),
            "_state_file": os.path.basename(path),
            "_source": "paper_entries.csv",
        }
        out.append(pos)

    print(f"{MENU_LOG_PREFIX} paper_entries load chat={chat_id} rows={len(rows)} open={len(out)} path={path}")
    return out


def _position_dedupe_key(pos):
    return str(
        pos.get("pos_id")
        or pos.get("position_id")
        or pos.get("id")
        or (
            str(pos.get("coin") or pos.get("symbol") or "")
            + "_"
            + str(pos.get("domestic") or pos.get("domestic_exchange") or "")
            + "_"
            + str(pos.get("foreign") or pos.get("foreign_exchange") or pos.get("exchange") or "")
            + "_"
            + str(pos.get("opened_at") or pos.get("entry_time") or pos.get("created_at") or "")
            + "_"
            + str(pos.get("tg_chat_id") or pos.get("chat_id") or pos.get("user_id") or "")
        )
    )


def _position_chat(pos):
    return str(
        pos.get("tg_chat_id")
        or pos.get("chat_id")
        or pos.get("user_id")
        or pos.get("telegram_chat_id")
        or ""
    ).strip()


def find_stats_file():
    candidates = [
        os.path.join(BASE_DIR, "paper_trading_data", "daily_stats.json"),
        os.path.join(BASE_DIR, "daily_stats.json"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def find_trade_results_file():
    candidates = [
        os.path.join(BASE_DIR, "paper_trading_data", "trade_results.csv"),
        os.path.join(BASE_DIR, "trade_results.csv"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def summarize_today_from_results(rows):
    """trade_results.csv가 있으면 오늘 실현 통계를 보강 계산."""
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    out = {
        "today_closed": 0,
        "today_tp": 0,
        "today_pnl_krw": 0.0,
        "today_entry_krw": 0.0,
        "today_avg_pnl_percent": 0.0,
        "last_rows": [],
    }
    pnl_values = []
    for r in rows:
        closed_at = str(r.get("closed_at") or r.get("event_time") or "")
        if not closed_at.startswith(today):
            continue
        out["today_closed"] += 1
        status = str(r.get("status") or "").upper()
        pnl = safe_float(r.get("pnl_krw"))
        pnl_pct = safe_float(r.get("pnl_percent"))
        out["today_pnl_krw"] += pnl
        out["today_entry_krw"] += safe_float(r.get("entry_krw") or r.get("domestic_entry_krw"))
        pnl_values.append(pnl_pct)
        if "TP" in status or "PROFIT" in status or "CLOSED" in status or pnl > 0:
            out["today_tp"] += 1
        out["last_rows"].append(r)
    if pnl_values:
        out["today_avg_pnl_percent"] = sum(pnl_values) / max(1, len(pnl_values))
    out["last_rows"] = out["last_rows"][-5:]
    return out


def load_state_files():
    """4개 거래소 state 전체 탐색.
    파일명이 조금 달라져도 semi_auto_state_*.json이면 모두 포함한다.
    """
    paths = []
    for pattern in [
        "semi_auto_state_*.json",
        "*semi*state*.json",
    ]:
        for p in sorted(glob.glob(os.path.join(BASE_DIR, pattern))):
            if os.path.exists(p) and p not in paths:
                paths.append(p)

    # 명시적 fallback
    for name in [
        "semi_auto_state_mexc.json",
        "semi_auto_state_gate.json",
        "semi_auto_state_bitget.json",
        "semi_auto_state_bingx.json",
    ]:
        p = os.path.join(BASE_DIR, name)
        if os.path.exists(p) and p not in paths:
            paths.append(p)
    print(f"{MENU_LOG_PREFIX} state files={','.join(os.path.basename(p) for p in paths)}")
    return paths


def extract_positions_for_chat(chat_id):
    """V9.5.12 포지션조회:
    - paper_entries.csv + semi_auto_state_*.json 전체를 합산한다.
    - MEXC/GATE/BITGET/BINGX 누락 방지.
    - pos_id 기준 중복 제거.
    """
    chat_id = str(chat_id).strip()
    merged = []
    seen = set()

    paper_positions = load_open_positions_from_paper_entries(chat_id)
    for pos in paper_positions:
        key = _position_dedupe_key(pos)
        if key and key not in seen:
            seen.add(key)
            merged.append(pos)

    state_count = 0
    for path in load_state_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        candidates = []
        if isinstance(data, dict):
            for key in ["active_positions", "positions", "paper_entries", "entries"]:
                val = data.get(key)
                if isinstance(val, list):
                    candidates.extend(val)
                elif isinstance(val, dict):
                    candidates.extend(val.values())

            for k, v in data.items():
                if isinstance(v, dict) and ("position_id" in v or "pos_id" in v or "coin" in v or "symbol" in v):
                    candidates.append(v)
        elif isinstance(data, list):
            candidates = data

        for pos in candidates:
            if not isinstance(pos, dict):
                continue

            status = str(pos.get("status", "ACTIVE")).upper()
            if status not in [
                "ACTIVE", "OPEN", "REAL_OPEN", "VIRTUAL_OPEN",
                "DOMESTIC_ONLY", "FUTURES_ONLY",
                "FUTURES_CLOSED_ONLY", "SPOT_CLOSED_ONLY"
            ]:
                continue

            pos_chat = _position_chat(pos)
            if pos_chat and pos_chat != chat_id:
                continue
            if not pos_chat:
                continue

            pos["_state_file"] = os.path.basename(path)
            pos["_source"] = "semi_auto_state"
            state_count += 1
            key = _position_dedupe_key(pos)
            if key and key not in seen:
                seen.add(key)
                merged.append(pos)

    print(f"{MENU_LOG_PREFIX} positions merged chat={chat_id} paper={len(paper_positions)} state={state_count} total={len(merged)}")
    return merged




# -------------------------
# Position margin/leverage lookup section
# -------------------------
# 조회 전용 기능. 주문/청산/마진모드 변경은 절대 수행하지 않는다.
# 포지션조회 화면에 해외 선물 마진모드와 레버리지를 표시한다.

POSITION_MARGIN_LOOKUP_ENABLED = os.getenv("KEDGE_MENU_POSITION_MARGIN_LOOKUP", "true").lower() == "true"
_POSITION_MEMBER_CACHE = {"ts": 0.0, "members": []}
_POSITION_MEMBER_CACHE_TTL_SEC = float(os.getenv("KEDGE_MENU_MEMBER_CACHE_TTL_SEC", "120"))
_POSITION_MARGIN_CACHE = {}
_POSITION_MARGIN_CACHE_TTL_SEC = float(os.getenv("KEDGE_MENU_MARGIN_CACHE_TTL_SEC", "20"))


def _lookup_norm_coin(v):
    return str(v or "").upper().replace("KRW-", "").replace("_KRW", "").replace("/KRW", "").replace("/USDT:USDT", "").replace("/USDT", "").replace("_USDT", "").strip()


def _lookup_member_chat_id(m):
    try:
        if core and hasattr(core, "get_member_chat_id"):
            cid = str(core.get_member_chat_id(m) or "").strip()
            if cid:
                return cid
    except Exception:
        pass
    try:
        return str(m.get("tg_chat_id") or m.get("chat_id") or m.get("user_id") or m.get("telegram_chat_id") or "").strip()
    except Exception:
        return ""


def _get_approved_members_for_menu():
    now = time.time()
    if _POSITION_MEMBER_CACHE.get("members") and now - float(_POSITION_MEMBER_CACHE.get("ts") or 0) < _POSITION_MEMBER_CACHE_TTL_SEC:
        return _POSITION_MEMBER_CACHE.get("members") or []
    members = []
    try:
        if core and hasattr(core, "supabase_get_approved_members"):
            members = core.supabase_get_approved_members(force_refresh=True) or []
    except Exception as e:
        print(f"{MENU_LOG_PREFIX} margin member load fail: {e}")
        members = []
    out = []
    for m in members:
        if not isinstance(m, dict):
            continue
        try:
            if core and hasattr(core, "merge_member_auto_settings"):
                m = core.merge_member_auto_settings(m)
        except Exception:
            pass
        out.append(m)
    _POSITION_MEMBER_CACHE["members"] = out
    _POSITION_MEMBER_CACHE["ts"] = now
    return out


def _find_member_by_chat_id(chat_id):
    chat_id = str(chat_id or "").strip()
    if not chat_id:
        return None
    for m in _get_approved_members_for_menu():
        if _lookup_member_chat_id(m) == chat_id:
            return m
    return None


def _mode_from_text(v):
    t = str(v or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not t:
        return ""
    if "isolat" in t or t in {"isolated", "isolate", "single"}:
        return "ISOLATED"
    if "cross" in t or t in {"crossed", "multi", "portfolio"}:
        return "CROSS"
    if t == "0":
        return "CROSS"
    return ""


def _extract_margin_mode_from_position_menu(pos):
    if not isinstance(pos, dict):
        return "", ""
    info = pos.get("info") if isinstance(pos.get("info"), dict) else {}
    candidates = [
        ("marginMode", pos.get("marginMode")),
        ("margin_mode", pos.get("margin_mode")),
        ("mode", pos.get("mode")),
        ("info.marginMode", info.get("marginMode")),
        ("info.margin_mode", info.get("margin_mode")),
        ("info.marginType", info.get("marginType")),
        ("info.openType", info.get("openType")),
        ("info.mode", info.get("mode")),
    ]
    for k, v in list(info.items()):
        lk = str(k).lower()
        if "margin" in lk or "open" in lk:
            candidates.append((f"info.{k}", v))
    for name, value in candidates:
        mode = _mode_from_text(value)
        if mode:
            return mode, f"{name}={value}"
    return "", ""


def _extract_leverage_from_position_menu(pos):
    if not isinstance(pos, dict):
        return 0.0, ""
    info = pos.get("info") if isinstance(pos.get("info"), dict) else {}
    candidates = [
        ("leverage", pos.get("leverage")),
        ("info.leverage", info.get("leverage")),
        ("info.leverage_max", info.get("leverage_max")),
        ("info.cross_leverage_limit", info.get("cross_leverage_limit")),
    ]
    for k, v in list(info.items()):
        if "lever" in str(k).lower():
            candidates.append((f"info.{k}", v))
    for name, value in candidates:
        n = safe_float(value, 0.0)
        if n > 0:
            return n, f"{name}={value}"
    return 0.0, ""


def _position_usd_krw(pos):
    try:
        return safe_float(
            pos.get("usd_krw")
            or pos.get("entry_usd_krw")
            or getattr(core, "FALLBACK_USD_KRW", None)
            or getattr(core, "MANUAL_USD_KRW", None)
            or 1509.0,
            1509.0,
        )
    except Exception:
        return 1509.0


def _extract_foreign_position_notional_usdt_menu(pos):
    """해외 실제 포지션 명목 USDT를 최대한 추출한다. 조회 전용."""
    if not isinstance(pos, dict):
        return 0.0, ""
    info = pos.get("info") if isinstance(pos.get("info"), dict) else {}

    # 1) CCXT unified / raw notional 계열
    candidates = [
        ("notional", pos.get("notional")),
        ("contractSize*contracts*markPrice", None),
        ("info.notional", info.get("notional")),
        ("info.value", info.get("value")),
        ("info.positionValue", info.get("positionValue")),
        ("info.position_value", info.get("position_value")),
        ("info.openValue", info.get("openValue")),
        ("info.open_value", info.get("open_value")),
        ("info.marginValue", info.get("marginValue")),
        ("info.initialMargin", info.get("initialMargin")),
    ]
    for name, value in candidates:
        if value is None:
            continue
        n = abs(safe_float(value, 0.0))
        # initialMargin은 증거금일 수 있어 마지막 fallback 취급. 그래도 없는 것보다는 참고값.
        if n > 0:
            return n, name

    # 2) contracts * contractSize * markPrice/entryPrice
    contracts = abs(safe_float(pos.get("contracts") or pos.get("contract") or pos.get("amount") or info.get("size") or info.get("positionAmt") or info.get("quantity"), 0.0))
    contract_size = abs(safe_float(pos.get("contractSize") or info.get("contractSize") or info.get("contract_size"), 1.0)) or 1.0
    price = safe_float(pos.get("markPrice") or pos.get("entryPrice") or pos.get("average") or info.get("markPrice") or info.get("entryPrice") or info.get("avgPrice") or info.get("fill_price"), 0.0)
    if contracts > 0 and price > 0:
        return contracts * contract_size * price, "contracts*contractSize*price"

    # 3) Gate/BingX raw: size * fill/mark price
    size = abs(safe_float(info.get("size") or info.get("executedQty") or info.get("qty"), 0.0))
    price2 = safe_float(info.get("fill_price") or info.get("avgPrice") or info.get("mark_price") or info.get("markPrice"), 0.0)
    if size > 0 and price2 > 0:
        return size * price2, "info.size*price"

    return 0.0, "notional_unavailable"


def _position_symbol_matches_market(pos, market):
    try:
        ps = str(pos.get("symbol") or (pos.get("info") or {}).get("symbol") or (pos.get("info") or {}).get("contract") or "").upper()
        ms = str(market or "").upper()
        if not ps or not ms:
            return True
        c_ps = "".join(ch for ch in ps if ch.isalnum())
        c_ms = "".join(ch for ch in ms if ch.isalnum())
        return c_ps in c_ms or c_ms in c_ps
    except Exception:
        return True


def _fetch_margin_leverage_for_position(member, pos):
    """실제 해외 선물 포지션에서 마진모드/레버리지/실제명목금액 조회. 조회 전용."""
    if not POSITION_MARGIN_LOOKUP_ENABLED:
        return "UNKNOWN", 0.0, 0.0, "disabled"
    if not core or member is None:
        return "UNKNOWN", 0.0, 0.0, "member/core missing"

    foreign = str(pos.get("foreign_exchange") or pos.get("exchange") or pos.get("foreign") or "").upper().strip()
    coin = _lookup_norm_coin(pos.get("coin") or pos.get("symbol") or pos.get("base"))
    if not foreign or not coin:
        return "UNKNOWN", 0.0, 0.0, "foreign/coin missing"

    cache_key = f"{_lookup_member_chat_id(member)}:{foreign}:{coin}"
    cached = _POSITION_MARGIN_CACHE.get(cache_key)
    if isinstance(cached, dict) and time.time() - float(cached.get("ts") or 0) < _POSITION_MARGIN_CACHE_TTL_SEC:
        return cached.get("mode", "UNKNOWN"), safe_float(cached.get("leverage"), 0.0), safe_float(cached.get("actual_krw"), 0.0), cached.get("detail", "cache")

    mode = "UNKNOWN"
    lev = 0.0
    actual_krw = 0.0
    detail = ""
    try:
        ex = None
        if hasattr(core, "build_user_exchange_from_member"):
            ex = core.build_user_exchange_from_member(member, foreign.lower(), "future")
        if ex is None:
            raise RuntimeError(f"{foreign} future exchange object missing")
        try:
            ex.load_markets()
        except Exception as e:
            print(f"{MENU_LOG_PREFIX} margin load_markets warn {foreign} {coin}: {e}")

        market = pos.get("foreign_market") or pos.get("future_market") or ""
        if not market and hasattr(core, "find_future_market"):
            market = core.find_future_market(ex, coin)
        if not market:
            raise RuntimeError(f"future market missing {foreign} {coin}")

        positions = []
        if hasattr(ex, "fetch_positions"):
            try:
                positions = ex.fetch_positions([market]) or []
            except Exception as e:
                detail = f"fetch_positions error={repr(e)[:160]}"
                positions = []
        for fp in positions:
            if not isinstance(fp, dict):
                continue
            if not _position_symbol_matches_market(fp, market):
                continue
            m, md = _extract_margin_mode_from_position_menu(fp)
            l, ld = _extract_leverage_from_position_menu(fp)
            notional_usdt, nd = _extract_foreign_position_notional_usdt_menu(fp)
            if m:
                mode = m
            if l > 0:
                lev = l
            if notional_usdt > 0:
                actual_krw = notional_usdt * _position_usd_krw(pos)
            if mode != "UNKNOWN" or lev > 0 or actual_krw > 0:
                detail = f"market={market} {md} {ld} {nd}".strip()
                break

        if mode == "UNKNOWN" and hasattr(ex, "fetch_margin_mode"):
            try:
                res = ex.fetch_margin_mode(market)
                if isinstance(res, dict):
                    m, md = _extract_margin_mode_from_position_menu(res)
                    if m:
                        mode = m
                        detail = f"market={market} fetch_margin_mode {md}"
            except Exception as e:
                if not detail:
                    detail = f"fetch_margin_mode error={repr(e)[:160]}"
        if not detail:
            detail = f"market={market} mode/leverage unknown"
    except Exception as e:
        mode = "ERROR"
        detail = repr(e)[:180]

    _POSITION_MARGIN_CACHE[cache_key] = {"ts": time.time(), "mode": mode, "leverage": lev, "actual_krw": actual_krw, "detail": detail}
    return mode, lev, actual_krw, detail


def _margin_mode_label(mode):
    m = str(mode or "").upper()
    if m == "CROSS":
        return "✅ 교차"
    if m == "ISOLATED":
        return "🚨 격리 / 교차변경요망"
    if m == "ERROR":
        return "⚠️ 확인오류"
    return "⚠️ 확인불가"


def _leverage_label(lev):
    n = safe_float(lev, 0.0)
    if n <= 0:
        return "⚠️ 확인불가"
    return f"x{n:g}"

def position_text(chat_id):
    positions = extract_positions_for_chat(chat_id)

    if not positions:
        return (
            "📊 <b>현재 보유 포지션</b>\n\n"
            "현재 조회되는 ACTIVE 포지션이 없습니다.\n\n"
            "※ 조회 시점 기준입니다."
        )

    member = _find_member_by_chat_id(chat_id)

    lines = []
    lines.append(f"📊 <b>현재 보유 포지션 ({len(positions)}개)</b>")
    lines.append("")

    for i, p in enumerate(positions, 1):
        coin = p.get("coin") or p.get("symbol") or p.get("base") or "-"
        domestic = p.get("domestic_exchange") or p.get("domestic") or "BITHUMB"
        foreign = p.get("foreign_exchange") or p.get("exchange") or p.get("foreign") or "-"
        entry_edge = p.get("entry_edge") or p.get("entry_real_edge") or p.get("real_edge") or p.get("entry_edge_percent")
        margin_mode, _leverage, _actual_foreign_krw, _margin_detail = _fetch_margin_leverage_for_position(member, p)

        lines.append("━━━━━━━━━━━━━━")
        lines.append(f"🟢 <b>{html_escape(coin)}</b>")
        lines.append(f"경로: {html_escape(domestic)} ↔ {html_escape(foreign)}")
        lines.append(f"마진모드: <b>{_margin_mode_label(margin_mode)}</b>")
        if entry_edge not in [None, ""]:
            try:
                lines.append(f"진입엣지: {float(entry_edge):+.2f}%")
            except Exception:
                lines.append(f"진입엣지: {html_escape(entry_edge)}")
        else:
            lines.append("진입엣지: -")

    lines.append("")
    lines.append("🚨 격리 = 교차변경요망")
    lines.append("✅ 교차 = 정상")
    lines.append("※ 조회 기능은 읽기 전용이며 주문/청산/마진변경을 실행하지 않습니다.")
    return "\n".join(lines)

def _parse_dt_date(s):
    try:
        return str(s or "")[:10]
    except Exception:
        return ""


def _today_key():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def _load_all_state_positions():
    """semi_auto_state_*.json 전체 포지션을 그대로 읽는다."""
    all_positions = []
    for path in load_state_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"{MENU_LOG_PREFIX} state read fail {path}: {e}")
            continue

        if not isinstance(data, dict):
            continue

        positions = data.get("positions") or data.get("active_positions") or {}
        if isinstance(positions, dict):
            iterable = positions.items()
        elif isinstance(positions, list):
            iterable = [(str(i), p) for i, p in enumerate(positions)]
        else:
            iterable = []

        for pos_id, pos in iterable:
            if not isinstance(pos, dict):
                continue
            item = dict(pos)
            item.setdefault("pos_id", pos_id)
            item["_state_file"] = os.path.basename(path)
            all_positions.append(item)
    return all_positions


def _positions_for_chat_from_state(chat_id):
    chat_id = str(chat_id)
    out = []
    for pos in _load_all_state_positions():
        pos_chat = str(
            pos.get("tg_chat_id")
            or pos.get("chat_id")
            or pos.get("user_id")
            or pos.get("telegram_chat_id")
            or ""
        )
        if pos_chat and pos_chat != chat_id:
            continue
        if not pos_chat:
            continue
        out.append(pos)
    return out


def _is_open_status(status):
    return str(status or "").upper() in {
        "ACTIVE", "OPEN", "REAL_OPEN", "VIRTUAL_OPEN",
        "FUTURES_CLOSED_ONLY", "SPOT_CLOSED_ONLY",
        "DOMESTIC_ONLY", "FUTURES_ONLY"
    }


def _is_closed_status(status):
    s = str(status or "").upper()
    return (
        "CLOSED" in s
        or "AUTO_CLOSED" in s
        or "TAKE" in s
        or "TP" in s
        or "STOPPED" in s
        or "MANUAL_STOP_CLOSED" in s
    ) and not _is_open_status(s)


def _is_tp_status(status):
    s = str(status or "").upper()
    return "AUTO_CLOSED" in s or "TP" in s or "TAKE" in s or ("CLOSED" in s and "STOP" not in s)


def _pos_amount_krw(pos):
    return safe_float(
        pos.get("domestic_entry_krw")
        or pos.get("amount_krw")
        or pos.get("entry_krw")
        or pos.get("final_entry_krw")
        or pos.get("domestic_amount_krw")
        or 0
    )


def _pos_foreign(pos):
    return str(pos.get("foreign_exchange") or pos.get("exchange") or pos.get("foreign") or "UNKNOWN").upper()


def _pos_coin(pos):
    return str(pos.get("coin") or pos.get("symbol") or pos.get("base") or "-").upper()


def _pos_opened_date(pos):
    return _parse_dt_date(
        pos.get("opened_at")
        or pos.get("entry_time")
        or pos.get("created_at")
        or pos.get("event_time")
        or pos.get("queued_at")
    )


def _pos_closed_date(pos):
    return _parse_dt_date(
        pos.get("closed_at")
        or pos.get("close_time")
        or pos.get("updated_at")
    )


def _estimate_pnl_from_pos(pos):
    """state만 있을 때 대략 추정용.
    entry_edge - close_edge 기준이며 수수료/펀딩/실제 체결차이는 반영하지 않는다.
    """
    entry_edge = safe_float(pos.get("entry_edge") or pos.get("entry_real_edge") or pos.get("real_edge"))
    close_edge = safe_float(pos.get("close_edge"))
    amount = _pos_amount_krw(pos)
    if amount <= 0:
        return 0.0, 0.0
    if close_edge == 0 and not pos.get("close_edge"):
        return 0.0, 0.0
    pnl_pct = entry_edge - close_edge
    pnl_krw = amount * pnl_pct / 100.0
    return pnl_krw, pnl_pct


def _load_auto_attempt_rows():
    paths = [
        os.path.join(BASE_DIR, "paper_trading_data", "auto_entry_attempts.csv"),
        os.path.join(BASE_DIR, "auto_entry_attempts.csv"),
    ]
    for p in paths:
        rows = read_csv_rows_safe(p)
        if rows:
            return rows
    return []


def _count_today_attempts_from_csv(chat_id):
    """auto_entry_attempts.csv 기준 후보/진입/실패 보조 집계."""
    today = _today_key()
    rows = _load_auto_attempt_rows()
    candidate = 0
    entry_ok = 0
    fail = 0
    by_exchange = {}
    edge_tiers = {"2%+": 0, "3%+": 0, "4%+": 0, "5%+": 0}

    for r in rows:
        event_time = str(r.get("event_time") or r.get("queued_at") or "")
        if not event_time.startswith(today):
            continue
        uid = str(r.get("user_id") or r.get("tg_chat_id") or "")
        if uid and str(uid) != str(chat_id):
            continue

        candidate += 1
        status = str(r.get("status") or "").upper()
        if "SUCCESS" in status or "OPEN" in status or "ENTRY" in status:
            entry_ok += 1
        elif status:
            fail += 1

        ex = str(r.get("foreign") or r.get("foreign_exchange") or "UNKNOWN").upper()
        by_exchange[ex] = by_exchange.get(ex, 0) + 1

        edge = safe_float(r.get("detected_edge") or r.get("real_edge") or r.get("entry_edge"))
        for k, threshold in [("2%+", 2.0), ("3%+", 3.0), ("4%+", 4.0), ("5%+", 5.0)]:
            if edge >= threshold:
                edge_tiers[k] += 1

    return {
        "candidate": candidate,
        "entry_ok": entry_ok,
        "fail": fail,
        "by_exchange": by_exchange,
        "edge_tiers": edge_tiers,
    }


def build_state_based_stats(chat_id):
    today = _today_key()
    positions = _positions_for_chat_from_state(chat_id)

    active = [p for p in positions if _is_open_status(p.get("status", "ACTIVE"))]
    closed_today = []
    entry_today = []

    for p in positions:
        if _pos_opened_date(p) == today:
            entry_today.append(p)
        if _is_closed_status(p.get("status")) and (_pos_closed_date(p) == today or _pos_closed_date(p) == ""):
            # closed_at이 없는 구버전 CLOSED는 오늘 통계에서 누락될 수 있어 fallback 허용
            closed_today.append(p)

    attempt = _count_today_attempts_from_csv(chat_id)

    # entries
    entry_count = len(entry_today)
    if entry_count == 0:
        # state opened_at이 없는 경우 ACTIVE 중 오늘 진입만 모를 수 있으므로 attempts 보조 사용
        entry_count = int(attempt.get("entry_ok") or 0)

    candidate_count = int(attempt.get("candidate") or 0)
    fail_count = int(attempt.get("fail") or 0)

    tp_count = sum(1 for p in closed_today if _is_tp_status(p.get("status")))
    closed_count = len(closed_today)

    # 금액
    active_amount = sum(_pos_amount_krw(p) for p in active)
    entry_amount_today = sum(_pos_amount_krw(p) for p in entry_today)
    if entry_amount_today <= 0:
        entry_amount_today = sum(_pos_amount_krw(p) for p in active)

    est_pnl_krw = 0.0
    pnl_pcts = []
    for p in closed_today:
        pnl, pct = _estimate_pnl_from_pos(p)
        est_pnl_krw += pnl
        if pct:
            pnl_pcts.append(pct)
    avg_pnl_pct = sum(pnl_pcts) / max(1, len(pnl_pcts)) if pnl_pcts else 0.0

    # 거래소별 active/entry/closed
    by_exchange = {}
    for p in active:
        ex = _pos_foreign(p)
        d = by_exchange.setdefault(ex, {"active": 0, "amount": 0.0, "closed": 0})
        d["active"] += 1
        d["amount"] += _pos_amount_krw(p)
    for p in closed_today:
        ex = _pos_foreign(p)
        d = by_exchange.setdefault(ex, {"active": 0, "amount": 0.0, "closed": 0})
        d["closed"] += 1

    # 최근 포지션/청산
    recent_active = sorted(active, key=lambda p: str(p.get("opened_at") or p.get("pos_id") or ""), reverse=True)[:5]
    recent_closed = sorted(closed_today, key=lambda p: str(p.get("closed_at") or p.get("pos_id") or ""), reverse=True)[:5]

    return {
        "today": today,
        "candidate_count": candidate_count,
        "entry_count": entry_count,
        "fail_count": fail_count,
        "active_count": len(active),
        "closed_count": closed_count,
        "tp_count": tp_count,
        "active_amount": active_amount,
        "entry_amount_today": entry_amount_today,
        "est_pnl_krw": est_pnl_krw,
        "avg_pnl_pct": avg_pnl_pct,
        "by_exchange": by_exchange,
        "edge_tiers": attempt.get("edge_tiers") or {},
        "recent_active": recent_active,
        "recent_closed": recent_closed,
    }


def stats_text(chat_id):
    """state JSON 직접 기반 통계조회.

    원칙:
    - 추가 stats worker 없음
    - semi_auto_state_*.json을 진실 데이터로 사용
    - auto_entry_attempts.csv가 있으면 후보/실패 통계만 보조 사용
    """
    s = build_state_based_stats(chat_id)
    closed_count = int(s.get("closed_count", 0))
    tp_count = int(s.get("tp_count", 0))
    win_rate = (tp_count / closed_count * 100.0) if closed_count else 0.0

    lines = []
    lines.append("📈 <b>K-EDGE 통계조회</b>")
    lines.append("")
    lines.append(f"기준일: <b>{html_escape(s.get('today'))}</b>")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("📊 <b>오늘 현황</b>")
    lines.append(f"후보: <b>{fmt_int(s.get('candidate_count'))}건</b>")
    lines.append(f"진입: <b>{fmt_int(s.get('entry_count'))}건</b>")
    lines.append(f"익절/청산: <b>{fmt_int(closed_count)}건</b>")
    lines.append(f"현재 보유: <b>{fmt_int(s.get('active_count'))}개</b>")
    if s.get("fail_count"):
        lines.append(f"미진입/실패: <b>{fmt_int(s.get('fail_count'))}건</b>")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━")
    lines.append("💰 <b>금액</b>")
    lines.append(f"현재 보유금액: <b>{fmt_krw(s.get('active_amount'))}</b>")
    lines.append(f"오늘 진입금액: <b>{fmt_krw(s.get('entry_amount_today'))}</b>")
    if closed_count:
        lines.append(f"추정 실현손익: <b>{fmt_krw(s.get('est_pnl_krw'))}</b>")
        lines.append(f"평균 수익률: <b>{fmt_pct(s.get('avg_pnl_pct'))}</b>")
        lines.append(f"승률: <b>{win_rate:.1f}%</b>")
    else:
        lines.append("실현손익: <b>청산 기록 생성 후 표시</b>")

    by_exchange = s.get("by_exchange") or {}
    if by_exchange:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━")
        lines.append("🏦 <b>거래소별 보유</b>")
        for ex in ["MEXC", "GATE", "BITGET", "BINGX"]:
            d = by_exchange.get(ex)
            if not d:
                continue
            lines.append(
                f"{html_escape(ex)}: "
                f"보유 {fmt_int(d.get('active'))}개 / "
                f"{fmt_krw(d.get('amount'))}"
            )

    edge_tiers = s.get("edge_tiers") or {}
    if any(safe_float(v) > 0 for v in edge_tiers.values()):
        lines.append("")
        lines.append("━━━━━━━━━━━━━━")
        lines.append("⚖️ <b>오늘 후보 엣지구간</b>")
        for key in ["2%+", "3%+", "4%+", "5%+"]:
            if safe_float(edge_tiers.get(key)) > 0:
                lines.append(f"{html_escape(key)}: {fmt_int(edge_tiers.get(key))}건")

    recent_closed = s.get("recent_closed") or []
    if recent_closed:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━")
        lines.append("🧾 <b>최근 청산</b>")
        for p in recent_closed[:5]:
            coin = html_escape(_pos_coin(p))
            ex = html_escape(_pos_foreign(p))
            close_edge = fmt_pct(p.get("close_edge"))
            status = html_escape(p.get("status") or "-")
            lines.append(f"{coin} {ex} / {close_edge} / {status}")
    else:
        recent_active = s.get("recent_active") or []
        if recent_active:
            lines.append("")
            lines.append("━━━━━━━━━━━━━━")
            lines.append("🟢 <b>최근 보유</b>")
            for p in recent_active[:5]:
                coin = html_escape(_pos_coin(p))
                ex = html_escape(_pos_foreign(p))
                entry = fmt_pct(p.get("entry_edge") or p.get("real_edge"))
                amt = fmt_krw(_pos_amount_krw(p))
                lines.append(f"{coin} {ex} / 진입 {entry} / {amt}")

    lines.append("")
    lines.append("※ 통계는 semi_auto_state_*.json 기준입니다.")
    lines.append("※ 손익은 close_edge가 저장된 경우에만 추정 표시됩니다.")
    return "\n".join(lines)



# -------------------------
# Current edge lookup section
# -------------------------

_EDGE_EXS_READY = False


def normalize_symbol_menu(v):
    try:
        return core.normalize_symbol(str(v or ""))
    except Exception:
        return str(v or "").upper().replace("/", "").replace("_", "").replace("-", "").replace("KRW", "").replace("USDT", "")


def _pick_exchange_from_container(container, name):
    """future_exs 컨테이너에서 거래소 객체를 이름으로 최대한 찾아낸다.
    - dict: key 대소문자/부분매칭
    - list/tuple: id/name/class명 매칭
    """
    target = str(name or "").upper()
    try:
        if isinstance(container, dict):
            # 1) 정확한 key 매칭
            for k, v in container.items():
                if str(k).upper() == target and v is not None:
                    return v
            # 2) key 부분 매칭
            for k, v in container.items():
                if target in str(k).upper() and v is not None:
                    return v
            # 3) 객체 속성 매칭
            for _, v in container.items():
                vid = str(getattr(v, "id", "") or "").upper()
                vname = str(getattr(v, "name", "") or "").upper()
                cls = v.__class__.__name__.upper() if v is not None else ""
                if target in (vid, vname, cls) or target in vid or target in vname or target in cls:
                    return v
        elif isinstance(container, (list, tuple)):
            for v in container:
                vid = str(getattr(v, "id", "") or "").upper()
                vname = str(getattr(v, "name", "") or "").upper()
                cls = v.__class__.__name__.upper() if v is not None else ""
                if target in (vid, vname, cls) or target in vid or target in vname or target in cls:
                    return v
    except Exception:
        pass
    return None


def _ensure_edge_future_exs():
    """현재엣지 조회용 futures 객체 준비.
    버튼을 눌렀을 때만 실행되며 주문/청산은 수행하지 않는다.

    V9.5.13 fix:
    - V9.5.12에서 기존 MEXC만 있으면 재초기화는 했지만,
      core.init_callback_future_exs()가 메뉴워커 환경에서 MEXC만 반환하는 케이스가 있었다.
    - 그래서 재초기화 후 누락된 GATE/BITGET/BINGX는 init_ccxt_all()의 future_exs에서
      직접 찾아 GLOBAL_FUTURE_EXS에 보강한다.
    - 4개가 모두 준비될 때만 ready 처리한다.
    """
    global _EDGE_EXS_READY
    required = {"MEXC", "GATE", "BITGET", "BINGX"}

    if not core:
        return False, "core missing"

    try:
        existing = getattr(core, "GLOBAL_FUTURE_EXS", None)
        if isinstance(existing, dict) and required.issubset(set(str(k).upper() for k in existing.keys())):
            # key 대소문자 정규화
            normalized = {}
            for k, v in existing.items():
                ku = str(k).upper()
                if ku in required and v is not None:
                    normalized[ku] = v
            core.GLOBAL_FUTURE_EXS = normalized
            _EDGE_EXS_READY = True
            print(f"EDGE GLOBAL_FUTURE_EXS={sorted(core.GLOBAL_FUTURE_EXS.keys())}")
            return True, "existing_all_futures"

        # 메뉴워커에서는 poller를 실제로 돌리지 않지만,
        # core 쪽 futures 객체 생성 분기가 ENABLE_CALLBACK_POLLER에 묶여있는 파일이 있어 True로 둔다.
        try:
            core.ENABLE_CALLBACK_POLLER = True
        except Exception:
            pass

        _, future_exs = core.init_ccxt_all()

        initialized = {}
        try:
            tmp = core.init_callback_future_exs(future_exs)
            if isinstance(tmp, dict):
                for k, v in tmp.items():
                    ku = str(k).upper()
                    if ku in required and v is not None:
                        initialized[ku] = v
        except Exception as e:
            print(f"EDGE init_callback_future_exs warning={e}")

        # 핵심 fallback: init_callback_future_exs가 MEXC만 줄 경우 future_exs에서 직접 보강
        for name in sorted(required):
            if name not in initialized or initialized.get(name) is None:
                obj = _pick_exchange_from_container(future_exs, name)
                if obj is not None:
                    initialized[name] = obj

        core.GLOBAL_FUTURE_EXS = initialized
        keys = set(initialized.keys())
        print(f"EDGE GLOBAL_FUTURE_EXS={sorted(keys)}")

        missing = sorted(required - keys)
        if missing:
            _EDGE_EXS_READY = False
            # 디버그용: future_exs 형태/키 출력
            try:
                if isinstance(future_exs, dict):
                    print(f"EDGE future_exs keys={list(future_exs.keys())}")
                else:
                    print(f"EDGE future_exs type={type(future_exs).__name__}")
            except Exception:
                pass
            return False, "missing futures: " + ",".join(missing)

        _EDGE_EXS_READY = True
        return True, "initialized_all_futures"
    except Exception as e:
        _EDGE_EXS_READY = False
        return False, repr(e)


def _current_edge_target(pos):
    try:
        return safe_float(
            pos.get("take_profit_edge")
            or getattr(core, "AUTO_TAKE_PROFIT_EDGE_PERCENT", 0.3),
            0.3
        )
    except Exception:
        return 0.3


def _btc_basis_for_edge(source, future_name, fex, usd_krw, cache):
    key = f"{source}_{future_name}"
    if key in cache:
        return cache[key]
    btc_basis = 0.0
    try:
        btc_spot = core.fetch_current_btc_spot_for_source(source)
        btc_market = core.find_future_market(fex, "BTC")
        btc_future = core.fetch_ccxt_book(fex, btc_market, is_future=True) if btc_market else None
        if btc_spot and btc_future:
            btc_spot_bid_usdt = safe_float(btc_spot.get("best_bid")) / max(1.0, usd_krw)
            btc_future_ask = safe_float(btc_future.get("best_ask") or btc_future.get("ask"))
            if btc_spot_bid_usdt > 0 and btc_future_ask > 0:
                btc_basis = core.calc_basis_percent(btc_future_ask, btc_spot_bid_usdt)
    except Exception:
        btc_basis = 0.0
    cache[key] = btc_basis
    return btc_basis


def calc_current_edge_for_position(pos, btc_cache=None):
    """포지션별 현재 청산 기준 실제엣지 계산.
    Close 기준: 국내 현물 매도 bid + 해외 선물 숏 청산 ask.
    주문/청산 없이 호가 조회만 수행한다.
    """
    btc_cache = btc_cache if isinstance(btc_cache, dict) else {}
    try:
        ok, why = _ensure_edge_future_exs()
        if not ok:
            return None, "futures init failed: " + why

        coin = normalize_symbol_menu(pos.get("coin") or pos.get("symbol"))
        source = str(pos.get("domestic") or pos.get("domestic_exchange") or "BITHUMB").upper()
        future_name = str(pos.get("foreign") or pos.get("foreign_exchange") or pos.get("exchange") or "").upper()
        usd_krw = safe_float(pos.get("usd_krw"), safe_float(getattr(core, "FALLBACK_USD_KRW", 1509.0), 1509.0))

        if not coin or not source or not future_name:
            return None, "coin/domestic/foreign missing"

        spot = core.fetch_current_domestic_book_for_signal(pos)
        if not spot:
            return None, "domestic book failed"
        spot_bid_usdt = safe_float(spot.get("best_bid")) / max(1.0, usd_krw)
        if spot_bid_usdt <= 0:
            return None, "domestic bid invalid"

        fex = getattr(core, "GLOBAL_FUTURE_EXS", {}).get(future_name)
        if not fex:
            return None, f"future object missing {future_name}"

        fmarket = pos.get("foreign_market") or core.find_future_market(fex, coin)
        if not fmarket:
            return None, f"future market missing {future_name} {coin}"

        future_book = core.fetch_ccxt_book(fex, fmarket, is_future=True)
        if not future_book:
            return None, "future book failed"
        future_ask = safe_float(future_book.get("best_ask") or future_book.get("ask"))
        if future_ask <= 0:
            return None, "future ask invalid"

        basis_now = core.calc_basis_percent(future_ask, spot_bid_usdt)
        btc_basis_now = _btc_basis_for_edge(source, future_name, fex, usd_krw, btc_cache)
        edge_now = basis_now - btc_basis_now
        return edge_now, f"basis={basis_now:+.2f}% btc={btc_basis_now:+.2f}%"
    except Exception as e:
        return None, repr(e)


def current_edge_text(chat_id):
    """유저용 현재엣지 버튼 출력."""
    positions = extract_positions_for_chat(chat_id)
    if not positions:
        return (
            "📉 <b>현재엣지 조회</b>\n\n"
            "현재 조회되는 ACTIVE 포지션이 없습니다.\n\n"
            "※ 조회 기능은 읽기 전용이며 주문/청산을 실행하지 않습니다."
        )

    start = time.time()
    btc_cache = {}
    rows = []

    for p in positions:
        coin = p.get("coin") or p.get("symbol") or p.get("base") or "-"
        domestic = p.get("domestic_exchange") or p.get("domestic") or "BITHUMB"
        foreign = p.get("foreign_exchange") or p.get("exchange") or p.get("foreign") or "-"
        entry_edge = safe_float(p.get("entry_edge") or p.get("entry_real_edge") or p.get("real_edge") or p.get("entry_edge_percent"))
        tp_edge = _current_edge_target(p)
        current_edge, detail = calc_current_edge_for_position(p, btc_cache)
        if current_edge is None:
            rows.append({
                "coin": coin,
                "domestic": domestic,
                "foreign": foreign,
                "entry_edge": entry_edge,
                "current_edge": None,
                "tp_edge": tp_edge,
                "remain": None,
                "detail": detail,
            })
        else:
            rows.append({
                "coin": coin,
                "domestic": domestic,
                "foreign": foreign,
                "entry_edge": entry_edge,
                "current_edge": current_edge,
                "tp_edge": tp_edge,
                "remain": current_edge - tp_edge,
                "detail": detail,
            })

    # V9.5.18: 현재엣지 전체 목록도 익절거리 짧은 순으로 정렬한다.
    # - 익절거리 = 현재엣지 - 익절목표
    # - remain 낮을수록 익절에 가깝거나 이미 익절권
    # - 조회실패 항목은 맨 아래로 보낸다.
    valid = [r for r in rows if r.get("remain") is not None]
    failed = [r for r in rows if r.get("remain") is None]
    valid_sorted = sorted(valid, key=lambda r: safe_float(r.get("remain"), 9999.0))
    display_rows = valid_sorted + failed

    lines = []
    lines.append("📉 <b>현재엣지 조회</b>")
    lines.append("")
    lines.append(f"보유수: <b>{len(positions)}개</b>")
    lines.append(f"익절목표: <b>현재엣지 ≤ +0.30% 기준</b>")
    lines.append("")

    if valid_sorted:
        lines.append("🔥 <b>익절 근접 TOP 3</b>")
        for r in valid_sorted[:3]:
            remain = safe_float(r.get("remain"))
            label = "익절권" if remain <= 0 else f"{remain:.2f}% 남음"
            lines.append(
                f"{html_escape(r['coin'])} {html_escape(r['foreign'])} / "
                f"현재 {fmt_pct(r['current_edge'])} / {html_escape(label)}"
            )
        lines.append("")

    lines.append("━━━━━━━━━━━━━━")
    lines.append("📋 <b>전체 포지션</b>")

    for i, r in enumerate(display_rows, 1):
        lines.append("━━━━━━━━━━━━━━")
        lines.append(f"{i}) <b>{html_escape(r['coin'])}</b>")
        lines.append(f"경로: {html_escape(r['domestic'])} ↔ {html_escape(r['foreign'])}")
        lines.append(f"진입엣지: {fmt_pct(r.get('entry_edge'))}")
        if r.get("current_edge") is None:
            lines.append("현재엣지: 조회실패")
            lines.append(f"사유: {html_escape(r.get('detail'))}")
            continue
        remain = safe_float(r.get("remain"))
        lines.append(f"현재엣지: <b>{fmt_pct(r.get('current_edge'))}</b>")
        lines.append(f"익절목표: {fmt_pct(r.get('tp_edge'))}")
        if remain <= 0:
            lines.append("익절거리: <b>🔥 익절권</b>")
        elif remain <= 0.3:
            lines.append(f"익절거리: <b>🔥 {remain:.2f}% 남음</b>")
        elif remain <= 0.8:
            lines.append(f"익절거리: <b>🟡 {remain:.2f}% 남음</b>")
        else:
            lines.append(f"익절거리: {remain:.2f}% 남음")

    elapsed = time.time() - start
    lines.append("")
    lines.append(f"조회 소요: {elapsed:.2f}초")
    lines.append("※ 현재엣지는 국내 매도호가 + 해외 숏청산호가 기준입니다.")
    lines.append("※ 조회 기능은 읽기 전용이며 주문/청산을 실행하지 않습니다.")
    return "\n".join(lines)



def handle_stop(chat_id):
    return send_message(
        chat_id,
        "🛑 <b>자동정지 요청 접수</b>\n\n"
        "현재 V9.5.10 메뉴 워커에서는 안전상 실제 정지 상태 변경은 아직 수행하지 않습니다.\n"
        "다음 패치에서 auto_settings running=false 저장과 연동합니다.",
        reply_keyboard_markup()
    )


def handle_start(chat_id):
    return send_message(
        chat_id,
        "▶ <b>자동시작 요청 접수</b>\n\n"
        "현재 V9.5.10 메뉴 워커에서는 안전상 실제 시작 상태 변경은 아직 수행하지 않습니다.\n"
        "다음 패치에서 auto_settings running=true 저장과 연동합니다.",
        reply_keyboard_markup()
    )


def read_offset():
    try:
        if os.path.exists(OFFSET_PATH):
            return int(Path(OFFSET_PATH).read_text(encoding="utf-8").strip() or "0")
    except Exception:
        pass
    return 0


def write_offset(offset):
    try:
        Path(OFFSET_PATH).write_text(str(offset), encoding="utf-8")
    except Exception:
        pass


def send_startup_menu_to_approved_members():
    """워커 실행 직후 승인회원에게 메뉴를 1회 표시한다."""
    if not core:
        return
    try:
        members = []
        if hasattr(core, "supabase_get_approved_members"):
            members = core.supabase_get_approved_members(force_refresh=True)
        sent = set()
        for m in members or []:
            try:
                chat_id = ""
                if hasattr(core, "get_member_chat_id"):
                    chat_id = core.get_member_chat_id(m)
                if not chat_id:
                    chat_id = str(m.get("tg_chat_id") or m.get("chat_id") or "").strip()
                if not chat_id or chat_id in sent:
                    continue
                sent.add(chat_id)
                send_message(
                    chat_id,
                    "🤖 <b>K-EDGE AUTO 메뉴가 활성화되었습니다.</b>\n\n"
                    "📊 포지션조회: 빠른 보유 포지션 확인\n"
                    "📉 현재엣지: 익절까지 남은 거리 확인\n"
                    "📈 통계조회: state 기준 실시간 통계\n\n"
                    "※ 조회 기능은 읽기 전용이며 주문/청산을 실행하지 않습니다.",
                    reply_keyboard_markup(),
                )
                print(f"{MENU_LOG_PREFIX} startup menu sent chat={chat_id}")
            except Exception as e:
                print(f"{MENU_LOG_PREFIX} startup menu send fail: {e}")
    except Exception as e:
        print(f"{MENU_LOG_PREFIX} startup approved members fail: {e}")


def poll_loop():
    print("=" * 70)
    print("K-EDGE V9.5.14 TELEGRAM MENU WORKER - POSITIONS MARGIN/LEVERAGE + CURRENT EDGE")
    print(f"Target bot: @{TARGET_BOT_USERNAME}")
    print("Keyboard: persistent reply keyboard")
    print("Buttons: 📊 포지션조회 / 📉 현재엣지 / 📈 통계조회 / 🛑 자동정지 / ▶ 자동시작")
    print("Safe: read-only lookup, no order, no close")
    print("Start: send /start or 메뉴 to @Kedge0203bot DM")
    print("Stop: Ctrl+C")
    print("=" * 70)

    try:
        code, me = tg_api("getMe", {})
        print("[BOT]", me)
    except Exception as e:
        print("[BOT ERROR]", e)
        return

    send_startup_menu_to_approved_members()

    offset = read_offset()

    while True:
        try:
            code, data = tg_api("getUpdates", {
                "offset": offset + 1 if offset else 0,
                "timeout": 25,
                "allowed_updates": ["message"]
            }, timeout=35)

            if not data.get("ok"):
                print("[getUpdates fail]", code, data)
                time.sleep(3)
                continue

            for upd in data.get("result", []):
                offset = max(offset, int(upd.get("update_id", 0)))
                write_offset(offset)

                if "message" not in upd:
                    continue

                msg = upd["message"]
                chat_id = msg.get("chat", {}).get("id")
                text = (msg.get("text") or "").strip()
                print(f"[MESSAGE] chat={chat_id} text={text}")

                if text in ["/start", "start", "시작", "메뉴", "/menu"]:
                    send_main_menu(chat_id)
                elif text in ["📊 포지션조회", "조회", "포지션", "내포지션", "/positions", "/position"]:
                    send_message(chat_id, "⏳ <b>포지션 조회 중...</b>\n\n마진모드/레버리지/실제금액을 확인하고 있습니다.", reply_keyboard_markup())
                    send_message(chat_id, position_text(chat_id), reply_keyboard_markup())
                elif text in ["📉 현재엣지", "현재엣지", "엣지", "익절거리", "/edge", "/edges"]:
                    send_message(chat_id, "⏳ <b>현재엣지 조회 중...</b>\n\n국내/해외 호가와 BTC 기준값을 확인하고 있습니다.", reply_keyboard_markup())
                    send_message(chat_id, current_edge_text(chat_id), reply_keyboard_markup())
                elif text in ["📈 통계조회", "통계", "/stats", "통계조회"]:
                    send_message(chat_id, stats_text(chat_id), reply_keyboard_markup())
                elif text in ["🛑 자동정지", "자동정지", "정지", "/stop"]:
                    handle_stop(chat_id)
                elif text in ["▶ 자동시작", "자동시작", "시작", "/start_auto"]:
                    handle_start(chat_id)
                else:
                    send_main_menu(chat_id)

        except KeyboardInterrupt:
            print("Stopped.")
            break
        except Exception as e:
            print("[LOOP ERROR]", e)
            traceback.print_exc()
            time.sleep(3)


if __name__ == "__main__":
    poll_loop()
