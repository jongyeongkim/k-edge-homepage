# -*- coding: utf-8 -*-
"""
K-EDGE V9.3.1 TEST_CAP_FEE 저장 전용 워커

역할:
- 4개 스캔봇(MEXC/GATE/BITGET/BINGX)이 storage_queue.jsonl에 남긴 저장 요청을 읽는다.
- 실제 CSV/JSON 저장은 이 워커 1개만 담당한다.
- 스캔봇의 API/오더북 루프가 CSV 저장 때문에 느려지는 문제를 줄인다.

실행:
    py kedge_storage_worker_v93.py

중지:
    CMD 창에서 Ctrl+C
"""

import os
import csv
import json
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAPER_DATA_DIR = os.path.join(BASE_DIR, "paper_trading_data")
STORAGE_QUEUE_PATH = os.path.join(PAPER_DATA_DIR, "storage_queue.jsonl")
STORAGE_OFFSET_PATH = os.path.join(PAPER_DATA_DIR, "storage_queue.offset")
PAPER_DAILY_STATS_JSON = os.path.join(PAPER_DATA_DIR, "daily_stats.json")

# 워커 출력 조절
POLL_SEC = float(os.getenv("STORAGE_WORKER_POLL_SEC", "0.5"))
SUMMARY_EVERY_SEC = float(os.getenv("STORAGE_WORKER_SUMMARY_EVERY_SEC", "10"))
VERBOSE = os.getenv("STORAGE_WORKER_VERBOSE", "false").lower() == "true"

EDGE_TIER_LEVELS = [2.0, 3.0, 4.0, 5.0]


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir() -> None:
    os.makedirs(PAPER_DATA_DIR, exist_ok=True)


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except Exception:
        return default


def read_json(path: str, default: Any) -> Any:
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def write_json_atomic(path: str, data: Any) -> None:
    ensure_dir()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def csv_append_direct(path: str, fieldnames: List[str], row: Dict[str, Any]) -> None:
    """헤더 확장 지원 CSV append. 스캔봇 원본 함수와 같은 방식."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    exists = os.path.exists(path)

    final_fieldnames = list(fieldnames or [])
    old_rows: List[Dict[str, Any]] = []
    old_fieldnames: List[str] = []

    if exists:
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as rf:
                reader = csv.DictReader(rf)
                old_fieldnames = list(reader.fieldnames or [])
                old_rows = list(reader)
            for name in old_fieldnames:
                if name not in final_fieldnames:
                    final_fieldnames.append(name)
            for name in fieldnames or []:
                if name not in final_fieldnames:
                    final_fieldnames.append(name)

            if any(name not in old_fieldnames for name in fieldnames or []):
                with open(path, "w", newline="", encoding="utf-8-sig") as wf:
                    writer = csv.DictWriter(wf, fieldnames=final_fieldnames)
                    writer.writeheader()
                    for old_row in old_rows:
                        writer.writerow({k: old_row.get(k, "") for k in final_fieldnames})
        except Exception as e:
            print(f"[저장워커 CSV 헤더확장 실패→append 진행] {path} / {e}")
            final_fieldnames = list(fieldnames or [])

    safe_row: Dict[str, Any] = {}
    for k in final_fieldnames:
        v = row.get(k, "") if isinstance(row, dict) else ""
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        safe_row[k] = v

    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=final_fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(safe_row)


def get_entry_edge_bucket(edge_percent: float) -> str:
    edge = safe_float(edge_percent)
    if edge >= 5.0:
        return "5%+"
    if edge >= 4.0:
        return "4%+"
    if edge >= 3.0:
        return "3%+"
    if edge >= 2.0:
        return "2%+"
    if edge >= 1.5:
        return "1.5%+"
    return "under_1.5%"


def blank_edge_stat() -> Dict[str, Any]:
    return {
        "closed_count": 0,
        "tp_count": 0,
        "sl_count": 0,
        "total_entry_krw": 0.0,
        "total_pnl_krw": 0.0,
        "avg_pnl_percent": 0.0,
        "avg_hold_sec": 0.0,
    }


def add_edge_stat(stat: Dict[str, Any], entry_krw: float, pnl_krw: float, pnl_percent: float, is_tp: bool, is_sl: bool, hold_sec: float = 0.0) -> None:
    old_n = int(stat.get("closed_count", 0))
    old_avg = safe_float(stat.get("avg_pnl_percent"))
    old_hold = safe_float(stat.get("avg_hold_sec"))
    stat["closed_count"] = old_n + 1
    stat["total_entry_krw"] = safe_float(stat.get("total_entry_krw")) + safe_float(entry_krw)
    stat["total_pnl_krw"] = safe_float(stat.get("total_pnl_krw")) + safe_float(pnl_krw)
    stat["avg_pnl_percent"] = round(((old_avg * old_n) + safe_float(pnl_percent)) / max(1, old_n + 1), 4)
    if hold_sec > 0:
        stat["avg_hold_sec"] = round(((old_hold * old_n) + safe_float(hold_sec)) / max(1, old_n + 1), 2)
    if is_tp:
        stat["tp_count"] = int(stat.get("tp_count", 0)) + 1
    if is_sl:
        stat["sl_count"] = int(stat.get("sl_count", 0)) + 1


def parse_hold_sec(opened_at: str, closed_at: str) -> float:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            if opened_at and closed_at:
                a = datetime.strptime(str(opened_at), fmt)
                b = datetime.strptime(str(closed_at), fmt)
                return max(0.0, (b - a).total_seconds())
        except Exception:
            pass
    return 0.0


def update_edge_tier_stats(day: Dict[str, Any], result_row: Dict[str, Any]) -> None:
    entry_edge = safe_float(result_row.get("entry_edge"))
    entry_krw = safe_float(result_row.get("entry_krw"))
    pnl_krw = safe_float(result_row.get("pnl_krw"))
    pnl_percent = safe_float(result_row.get("pnl_percent"))
    status = str(result_row.get("status") or "")
    is_tp = ("TAKE" in status or "TP" in status or "PROFIT" in status or pnl_krw > 0)
    is_sl = ("STOP" in status or "SL" in status or pnl_krw < 0)
    hold_sec = parse_hold_sec(str(result_row.get("opened_at") or ""), str(result_row.get("closed_at") or ""))

    bucket = get_entry_edge_bucket(entry_edge)
    result_row["entry_edge_bucket"] = bucket

    by_bucket = day.setdefault("by_entry_edge_bucket", {})
    add_edge_stat(by_bucket.setdefault(bucket, blank_edge_stat()), entry_krw, pnl_krw, pnl_percent, is_tp, is_sl, hold_sec)

    ge = day.setdefault("edge_ge", {})
    for level in EDGE_TIER_LEVELS:
        if entry_edge >= level:
            key = f"{int(level)}%+"
            add_edge_stat(ge.setdefault(key, blank_edge_stat()), entry_krw, pnl_krw, pnl_percent, is_tp, is_sl, hold_sec)


def daily_stats_update(result_row: Dict[str, Any]) -> None:
    ensure_dir()
    today = str(result_row.get("closed_at") or now_str())[:10]
    if not today or len(today) != 10:
        today = datetime.now().strftime("%Y-%m-%d")

    stats = read_json(PAPER_DAILY_STATS_JSON, {})
    if not isinstance(stats, dict):
        stats = {}

    day = stats.setdefault(today, {
        "date": today,
        "closed_count": 0,
        "tp_count": 0,
        "sl_count": 0,
        "warn_or_other_count": 0,
        "total_entry_krw": 0,
        "total_pnl_krw": 0.0,
        "avg_pnl_percent": 0.0,
        "by_exchange": {},
        "by_entry_edge_bucket": {},
        "edge_ge": {},
    })

    status = str(result_row.get("status") or "")
    entry_krw = safe_float(result_row.get("entry_krw"))
    pnl_krw = safe_float(result_row.get("pnl_krw"))
    pnl_percent = safe_float(result_row.get("pnl_percent"))
    foreign = str(result_row.get("foreign") or "UNKNOWN").upper()

    old_n = int(day.get("closed_count", 0))
    old_avg = safe_float(day.get("avg_pnl_percent"))
    day["closed_count"] = old_n + 1
    day["total_entry_krw"] = safe_float(day.get("total_entry_krw")) + entry_krw
    day["total_pnl_krw"] = safe_float(day.get("total_pnl_krw")) + pnl_krw
    day["avg_pnl_percent"] = round(((old_avg * old_n) + pnl_percent) / max(1, old_n + 1), 4)

    if "TAKE" in status or "TP" in status or "PROFIT" in status or pnl_krw > 0:
        day["tp_count"] = int(day.get("tp_count", 0)) + 1
    elif "STOP" in status or "SL" in status or pnl_krw < 0:
        day["sl_count"] = int(day.get("sl_count", 0)) + 1
    else:
        day["warn_or_other_count"] = int(day.get("warn_or_other_count", 0)) + 1

    update_edge_tier_stats(day, result_row)

    ex = day.setdefault("by_exchange", {}).setdefault(foreign, {
        "closed_count": 0,
        "tp_count": 0,
        "sl_count": 0,
        "total_entry_krw": 0,
        "total_pnl_krw": 0.0,
        "avg_pnl_percent": 0.0,
    })
    old_ex_n = int(ex.get("closed_count", 0))
    old_ex_avg = safe_float(ex.get("avg_pnl_percent"))
    ex["closed_count"] = old_ex_n + 1
    ex["total_entry_krw"] = safe_float(ex.get("total_entry_krw")) + entry_krw
    ex["total_pnl_krw"] = safe_float(ex.get("total_pnl_krw")) + pnl_krw
    ex["avg_pnl_percent"] = round(((old_ex_avg * old_ex_n) + pnl_percent) / max(1, old_ex_n + 1), 4)
    if pnl_krw > 0:
        ex["tp_count"] = int(ex.get("tp_count", 0)) + 1
    elif pnl_krw < 0:
        ex["sl_count"] = int(ex.get("sl_count", 0)) + 1

    write_json_atomic(PAPER_DAILY_STATS_JSON, stats)


def read_offset() -> int:
    try:
        if os.path.exists(STORAGE_OFFSET_PATH):
            with open(STORAGE_OFFSET_PATH, "r", encoding="utf-8") as f:
                return int((f.read() or "0").strip() or "0")
    except Exception:
        pass
    return 0


def write_offset(offset: int) -> None:
    ensure_dir()
    tmp = STORAGE_OFFSET_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(int(offset)))
    os.replace(tmp, STORAGE_OFFSET_PATH)


def process_once() -> int:
    ensure_dir()
    if not os.path.exists(STORAGE_QUEUE_PATH):
        return 0

    size = os.path.getsize(STORAGE_QUEUE_PATH)
    offset = read_offset()
    if offset > size:
        offset = 0

    processed = 0
    new_offset = offset
    with open(STORAGE_QUEUE_PATH, "rb") as f:
        f.seek(offset)
        while True:
            line = f.readline()
            if not line:
                break
            # 아직 쓰는 중인 partial line은 다음 턴에 처리
            if not line.endswith(b"\n"):
                break
            new_offset += len(line)
            try:
                event = json.loads(line.decode("utf-8"))
                op = event.get("op")
                payload = event.get("payload") or {}
                if op == "csv_append":
                    csv_append_direct(payload.get("path", ""), payload.get("fieldnames", []), payload.get("row", {}))
                elif op == "daily_stats_update":
                    daily_stats_update(payload.get("result_row", {}))
                else:
                    print(f"[저장워커 알수없는 op] {op}")
                processed += 1
            except Exception as e:
                print(f"[저장워커 처리 실패] {e}")
                if VERBOSE:
                    traceback.print_exc()

    if new_offset != offset:
        write_offset(new_offset)
    return processed


def main() -> None:
    ensure_dir()
    print("=" * 60)
    print("K-EDGE V9.3.1 TEST_CAP_FEE 저장 전용 워커 시작")
    print(f"queue : {STORAGE_QUEUE_PATH}")
    print(f"offset: {STORAGE_OFFSET_PATH}")
    print("스캔봇 4개는 저장요청만 큐에 넣고, 실제 저장은 이 창에서 처리합니다.")
    print("=" * 60)

    total = 0
    last_summary = time.time()
    while True:
        try:
            n = process_once()
            total += n
            now = time.time()
            if n and VERBOSE:
                print(f"[저장워커 처리] {n}건")
            if now - last_summary >= SUMMARY_EVERY_SEC:
                if total:
                    print(f"[저장워커 상태] 누적 처리 {total}건 / {now_str()}")
                last_summary = now
            time.sleep(POLL_SEC)
        except KeyboardInterrupt:
            print("\n[저장워커 종료]")
            break
        except Exception as e:
            print(f"[저장워커 루프 예외] {e}")
            if VERBOSE:
                traceback.print_exc()
            time.sleep(2)


if __name__ == "__main__":
    main()
