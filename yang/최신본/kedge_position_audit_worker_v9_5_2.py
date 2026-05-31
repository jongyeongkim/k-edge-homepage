# -*- coding: utf-8 -*-
"""
K-EDGE V9.5.2c POSITION AUDIT WORKER - GHOST CLEANUP
- 실제 주문 없음
- 실제 매도/청산 없음
- ACTIVE 포지션을 거래소 실제 잔고/포지션과 대조해서 콘솔 + CSV 로그만 남김

사용법:
1) 이 파일을 현재 사용하는 kedge*_BINGX*.py 파일과 같은 폴더에 둔다.
2) 같은 폴더에 semi_auto_state_bingx/mexc/gate/bitget.json 이 있어야 한다.
3) py kedge_position_check_only.py

주의:
- 조회 전용이다. create_order, cancel_order 호출 없음.
"""

import os
import sys
import csv
import json
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(BASE_DIR, "position_audit_log.csv")
POSITION_AUDIT_AUTO_FIX = os.getenv("POSITION_AUDIT_AUTO_FIX", "false").lower() == "true"
POSITION_AUDIT_FIX_GHOST_ONLY = os.getenv("POSITION_AUDIT_FIX_GHOST_ONLY", "true").lower() == "true"

CHECK_INTERVAL_SEC = int(os.getenv("POSITION_CHECK_INTERVAL_SEC", "300"))
DUST_KRW = float(os.getenv("POSITION_CHECK_DUST_KRW", "1000"))
QTY_DUST_RATIO = float(os.getenv("POSITION_CHECK_QTY_DUST_RATIO", "0.05"))  # 저장금액 대비 5% 미만이면 사실상 없음 후보

STATE_FILES = [
    "semi_auto_state_bingx.json",
    "semi_auto_state_mexc.json",
    "semi_auto_state_gate.json",
    "semi_auto_state_bitget.json",
]

# 같은 폴더의 기존 K-EDGE BINGX 파일을 조회 유틸로만 사용한다.
# 버전명이 바뀌어도 kedge*_BINGX*.py 중 가장 최신 수정 파일을 자동 로드한다.
# import만 하면 main()은 실행되지 않는다.
import glob
import importlib.util


def _load_latest_bingx_core():
    patterns = [
        os.path.join(BASE_DIR, "kedge*_REAL_ORDER_BINGX*.py"),
        os.path.join(BASE_DIR, "kedge*_BINGX*.py"),
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))

    # 자기 자신/중복 제외
    self_path = os.path.abspath(__file__)
    uniq = []
    seen = set()
    for f in files:
        af = os.path.abspath(f)
        if af == self_path or af in seen:
            continue
        seen.add(af)
        uniq.append(af)

    if not uniq:
        print("[치명] 같은 폴더에서 kedge*_BINGX*.py 파일을 찾을 수 없습니다.")
        print("이 파일을 실제 K-EDGE BINGX .py 파일과 같은 폴더에 넣고 실행하세요.")
        print(f"현재 폴더: {BASE_DIR}")
        sys.exit(1)

    # 파일 수정시각 기준 최신 파일 선택
    target = max(uniq, key=lambda x: os.path.getmtime(x))
    try:
        spec = importlib.util.spec_from_file_location("kedge_core_auto", target)
        if spec is None or spec.loader is None:
            raise RuntimeError("import spec 생성 실패")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"[로드 성공] core={os.path.basename(target)}")
        return module
    except Exception as e:
        print("[치명] K-EDGE BINGX core 파일 import 실패")
        print(f"대상 파일: {target}")
        print("오류:", e)
        sys.exit(1)


core = _load_latest_bingx_core()


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except Exception:
        return default


def fmt_krw(v: Any) -> str:
    return f"{safe_float(v):,.0f}원"


def normalize_symbol(s: Any) -> str:
    try:
        return core.normalize_symbol(str(s or ""))
    except Exception:
        return str(s or "").upper().replace("/", "").replace("_", "").replace("-", "")


def read_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[JSON 읽기 실패] {path} / {e}")
        return default


def load_active_positions() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for name in STATE_FILES:
        path = os.path.join(BASE_DIR, name)
        data = read_json(path, {"positions": {}})
        positions = data.get("positions") or {}
        if not isinstance(positions, dict):
            continue
        for pos_id, pos in positions.items():
            if not isinstance(pos, dict):
                continue
            if str(pos.get("status") or "").upper() != "ACTIVE":
                continue
            pid = str(pos.get("pos_id") or pos_id)
            if pid in seen:
                continue
            seen.add(pid)
            item = dict(pos)
            item["pos_id"] = pid
            item["_state_file"] = name
            out.append(item)
    return out


def get_bithumb_coin_balance(member: Dict[str, Any], coin: str) -> Tuple[float, float, str]:
    """return=(qty, locked_qty, source_text)"""
    creds = core.get_api_credentials_priority(member, "BITHUMB", "spot")
    raw = core.bithumb_v2_accounts_direct(creds.get("api_key"), creds.get("secret")).get("raw")
    qty = 0.0
    locked = 0.0
    coin = normalize_symbol(coin)
    if isinstance(raw, list):
        for item in raw:
            if str(item.get("currency") or "").upper() == coin:
                qty = safe_float(item.get("balance"))
                locked = safe_float(item.get("locked"))
                break
    return qty, locked, "bithumb_v2_accounts"


def get_bithumb_value_krw(pos: Dict[str, Any], qty: float) -> Tuple[float, float]:
    """return=(best_bid, value_krw)"""
    if qty <= 0:
        return 0.0, 0.0
    try:
        book = core.fetch_current_domestic_book_for_signal(pos)
        bid = safe_float((book or {}).get("best_bid"))
        return bid, qty * bid
    except Exception:
        return 0.0, 0.0


def _position_amount_from_ccxt_position(p: Dict[str, Any]) -> float:
    for k in ("contracts", "contractSize", "amount"):
        pass
    amt = abs(safe_float(p.get("contracts")))
    if amt <= 0:
        amt = abs(safe_float(p.get("contractSize")))
    if amt <= 0:
        amt = abs(safe_float(p.get("amount")))
    if amt <= 0:
        info = p.get("info") or {}
        for k in ("positionAmt", "positionAmt", "holdVol", "total", "size", "available", "positionSize", "qty"):
            if k in info:
                amt = abs(safe_float(info.get(k)))
                if amt > 0:
                    break
    return amt


def _position_notional_from_ccxt_position(p: Dict[str, Any]) -> float:
    for k in ("notional", "initialMargin", "collateral"):
        v = abs(safe_float(p.get(k)))
        if v > 0:
            return v
    info = p.get("info") or {}
    for k in ("notional", "notionalUsd", "positionValue", "holdValue", "value", "margin"):
        v = abs(safe_float(info.get(k)))
        if v > 0:
            return v
    return 0.0


def _is_short_position(p: Dict[str, Any]) -> bool:
    side = str(p.get("side") or "").lower()
    if "short" in side:
        return True
    info = p.get("info") or {}
    for k in ("side", "positionSide", "holdSide"):
        s = str(info.get(k) or "").lower()
        if "short" in s:
            return True
    # One-way에서는 side가 없고 contracts만 양수일 수 있음. 숏 전략만 쓰므로 보유 포지션이면 후보 인정.
    return False


def get_foreign_position(member: Dict[str, Any], pos: Dict[str, Any]) -> Tuple[float, float, str, str]:
    """return=(amount/contracts, notional_usdt, side_text, source_text)"""
    foreign = str(pos.get("foreign") or "").upper()
    coin = normalize_symbol(pos.get("coin"))
    ex = core.build_user_exchange_from_member(member, foreign.lower(), "future")
    if ex is None:
        raise RuntimeError(f"{foreign} API 객체 생성 실패")
    try:
        ex.load_markets()
    except Exception:
        pass
    market = pos.get("foreign_market") or core.find_future_market(ex, coin)
    if not market:
        raise RuntimeError(f"{foreign} {coin} 선물 마켓 찾기 실패")

    positions = []
    try:
        positions = ex.fetch_positions([market])
    except Exception as e1:
        try:
            positions = ex.fetch_positions()
        except Exception as e2:
            raise RuntimeError(f"fetch_positions 실패: {e1} / {e2}")

    best = None
    for p in positions or []:
        sym = str(p.get("symbol") or "")
        base = normalize_symbol(sym.split("/")[0]) if sym else ""
        if sym == market or base == coin or coin in sym.upper():
            amt = _position_amount_from_ccxt_position(p)
            if amt > 0:
                best = p
                break

    if not best:
        return 0.0, 0.0, "NONE", f"{foreign}.fetch_positions"

    amt = _position_amount_from_ccxt_position(best)
    notional = _position_notional_from_ccxt_position(best)
    side = str(best.get("side") or (best.get("info") or {}).get("side") or (best.get("info") or {}).get("positionSide") or (best.get("info") or {}).get("holdSide") or "UNKNOWN")
    return amt, notional, side, f"{foreign}.fetch_positions"


def classify_position(pos: Dict[str, Any], domestic_value: float, foreign_notional_usdt: float, usd_krw: float) -> str:
    foreign_value_krw = foreign_notional_usdt * max(1.0, usd_krw)
    domestic_has = domestic_value > DUST_KRW
    foreign_has = foreign_value_krw > DUST_KRW

    if domestic_has and foreign_has:
        return "정상_ACTIVE(국내O/해외O)"
    if (not domestic_has) and (not foreign_has):
        return "유령후보(국내X/해외X)"
    if (not domestic_has) and foreign_has:
        return "비대칭(국내X/해외O)-해외숏만 남음"
    if domestic_has and (not foreign_has):
        return "비대칭(국내O/해외X)-국내현물만 남음"
    return "확인필요"


def append_log(row: Dict[str, Any]) -> None:
    fields = [
        "checked_at", "pos_id", "state_file", "user_id", "coin", "domestic", "foreign",
        "entry_krw", "domestic_entry_krw", "foreign_entry_krw",
        "domestic_qty", "domestic_locked", "domestic_bid", "domestic_value_krw",
        "foreign_amount", "foreign_notional_usdt", "foreign_value_krw", "foreign_side",
        "classification", "error"
    ]
    exists = os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


def check_one(pos: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(pos.get("user_id") or "")
    coin = normalize_symbol(pos.get("coin"))
    foreign = str(pos.get("foreign") or "").upper()
    usd_krw = safe_float(pos.get("usd_krw"), safe_float(getattr(core, "FALLBACK_USD_KRW", 1509.0), 1509.0))

    row: Dict[str, Any] = {
        "checked_at": now_str(),
        "pos_id": pos.get("pos_id"),
        "state_file": pos.get("_state_file"),
        "user_id": user_id,
        "coin": coin,
        "domestic": pos.get("domestic"),
        "foreign": foreign,
        "entry_krw": pos.get("amount_krw"),
        "domestic_entry_krw": pos.get("domestic_entry_krw"),
        "foreign_entry_krw": pos.get("foreign_entry_krw"),
        "error": "",
    }

    member = core.find_member_by_telegram_id(user_id)
    if not member:
        row["error"] = f"승인회원 조회 실패 user_id={user_id}"
        row["classification"] = "조회불가"
        return row

    try:
        d_qty, d_locked, d_src = get_bithumb_coin_balance(member, coin)
        d_bid, d_value = get_bithumb_value_krw(pos, d_qty + d_locked)
        row.update({
            "domestic_qty": d_qty,
            "domestic_locked": d_locked,
            "domestic_bid": d_bid,
            "domestic_value_krw": round(d_value, 4),
        })
    except Exception as e:
        row["error"] += f"국내조회실패={e} "
        row.update({"domestic_qty": "", "domestic_locked": "", "domestic_bid": "", "domestic_value_krw": 0})

    try:
        f_amt, f_notional, f_side, f_src = get_foreign_position(member, pos)
        row.update({
            "foreign_amount": f_amt,
            "foreign_notional_usdt": round(f_notional, 8),
            "foreign_value_krw": round(f_notional * max(1.0, usd_krw), 4),
            "foreign_side": f_side,
        })
    except Exception as e:
        row["error"] += f"해외조회실패={e} "
        row.update({"foreign_amount": "", "foreign_notional_usdt": 0, "foreign_value_krw": 0, "foreign_side": "ERROR"})

    row["classification"] = classify_position(
        pos,
        safe_float(row.get("domestic_value_krw")),
        safe_float(row.get("foreign_notional_usdt")),
        usd_krw,
    )
    return row


def print_row(row: Dict[str, Any]) -> None:
    print("-" * 70)
    print(f"[{row.get('classification')}] {row.get('coin')} {row.get('domestic')}↔{row.get('foreign')}")
    print(f"POS: {row.get('pos_id')}")
    print(f"USER: {row.get('user_id')} / STATE: {row.get('state_file')}")
    print(f"진입금액: 국내 {fmt_krw(row.get('domestic_entry_krw'))} / 해외 {fmt_krw(row.get('foreign_entry_krw'))}")
    print(f"국내: qty={row.get('domestic_qty')} locked={row.get('domestic_locked')} value={fmt_krw(row.get('domestic_value_krw'))}")
    print(f"해외: amount={row.get('foreign_amount')} side={row.get('foreign_side')} value={fmt_krw(row.get('foreign_value_krw'))}")
    if row.get("error"):
        print(f"오류: {row.get('error')}")



def _target_status_for_classification(classification: str) -> str:
    if "유령후보" in classification:
        return "GHOST_CLOSED"
    if "국내O/해외X" in classification:
        return "DOMESTIC_ONLY"
    if "국내X/해외O" in classification:
        return "FUTURES_ONLY"
    return ""


def update_state_status(row: Dict[str, Any]) -> bool:
    """Optionally update JSON status. Default is dry-run unless POSITION_AUDIT_AUTO_FIX=true."""
    if not POSITION_AUDIT_AUTO_FIX:
        return False
    new_status = _target_status_for_classification(str(row.get("classification") or ""))
    if not new_status:
        return False
    if POSITION_AUDIT_FIX_GHOST_ONLY and new_status != "GHOST_CLOSED":
        return False
    state_file = str(row.get("state_file") or "")
    pos_id = str(row.get("pos_id") or "")
    if not state_file or not pos_id:
        return False
    path = os.path.join(BASE_DIR, state_file)
    data = read_json(path, {"positions": {}})
    positions = data.get("positions") or {}
    if pos_id not in positions:
        return False
    positions[pos_id]["status"] = new_status
    positions[pos_id]["audit_status"] = new_status
    positions[pos_id]["audit_checked_at"] = now_str()
    positions[pos_id]["audit_classification"] = row.get("classification")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
    print(f"[GHOST CLEANUP] {pos_id} ACTIVE -> {new_status} / 실제 주문 없음")
    return True

def run_once() -> None:
    positions = load_active_positions()
    print("=" * 70)
    print(f"K-EDGE V9.5.2c POSITION AUDIT WORKER - GHOST CLEANUP / {now_str()} / ACTIVE {len(positions)}개")
    print(f"실제 매도/청산 없음 / 상태값만 정리 / AUTO_FIX={POSITION_AUDIT_AUTO_FIX} / GHOST_ONLY={POSITION_AUDIT_FIX_GHOST_ONLY}")
    print("=" * 70)
    if not positions:
        print("ACTIVE 포지션 없음")
        return
    for pos in positions:
        try:
            row = check_one(pos)
            print_row(row)
            append_log(row)
            update_state_status(row)
        except Exception as e:
            print("[포지션 조회 예외]", pos.get("pos_id"), e)
            traceback.print_exc()


def main() -> None:
    loop = os.getenv("POSITION_CHECK_LOOP", "true").lower() == "true"
    while True:
        run_once()
        if not loop:
            break
        print(f"\n{CHECK_INTERVAL_SEC}초 후 재조회... Ctrl+C 중지")
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
