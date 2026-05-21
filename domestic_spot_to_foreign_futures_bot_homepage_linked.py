# -*- coding: utf-8 -*-
"""
국내 현물 → 해외 선물 괴리 감시봇 - BTC프리미엄 적용

목표:
    현물 가격 < 선물 가격 인 경우만 감지
    예) 업비트 현물 100원 / Gate 선물 110원 = +10%
    전략: 현물 매수 + 선물 숏

국내 현물:
    업비트 / 빗썸 / 고팍스 / 코인원 / 코빗

해외 현물:
    MEXC / Gate / Bitget / BingX

해외 선물:
    MEXC / Gate / Bitget / BingX

필요 설치:
    py -m pip install requests ccxt

실행:
    py domestic_spot_to_foreign_futures_bot_btc_premium.py
"""

import time
import traceback
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import requests

try:
    import ccxt
except Exception:
    ccxt = None


# ============================================================
# 텔레그램
# ============================================================

TELEGRAM_BOT_TOKEN = "8859181727:AAEpF5Lj85JXSHXJSjDC7nW2vuOFBna4_ug"
TELEGRAM_CHAT_ID = "-1003920360370"

FREE_TELEGRAM_BOT_TOKEN = "8605442809:AAGwuuHr3LZwjxqCTiHj6pkryPKGlp1nVwE"
FREE_TELEGRAM_CHAT_ID = "-1003935178171"


# ============================================================
# BingX API
# 현재는 공용 호가 조회 위주라 없어도 됨.
# ============================================================

BINGX_API_KEY = "35mFYxMAK1VMgnztRpqmKFlu8jaaF49I2NJVbNLp89fPhsYMkOMtBukkMMkJh1VSZcLf542caPoZvxhLSscXQ"
BINGX_SECRET_KEY = "ETNEk9nJ3PPUyBzm2FXFa9gRBKnMvPu0wZDh0Urd5ZfenUyXE1cccKuUuAMicZ3XQZNTnsvLsNo19W4JINyA"


# ============================================================
# 감시 기준
# ============================================================

# 기존 절대 괴리 기준
# 이제는 BTC 기준 프리미엄을 뺀 "실제 엣지" 기준으로 알림
MIN_BASIS_PERCENT = 3.0

# BTC 기준 프리미엄 차감 후 실제 엣지 기준
# 예: BTC +1%, 코인 +3% => 실제 엣지 +2%
MIN_EDGE_PERCENT = 2.0

# 알림 후 진입했다고 가정하고, 실제 엣지가 이 값 이하로 줄어들 때까지 같은 코인은 재알림 금지
POSITION_RELEASE_PERCENT = 0.5

# BTC 기준 프리미엄을 못 구하면 알림 제외
REQUIRE_BTC_BASELINE = True

# 최소 실체결 가능금액
# 국내 현물은 KRW 기준, 해외 현물은 USDT를 KRW 환산해서 비교
MIN_REAL_FILL_KRW = 1_000_000

# 국내 현물 24h 거래대금 최소
MIN_DOMESTIC_VOLUME_KRW = 2_000_000

# 해외 현물/선물 24h 거래대금 최소
MIN_FOREIGN_VOLUME_USDT = 5_000

# 스프레드 허용
MAX_SPOT_SPREAD_PERCENT = 5.0
MAX_FUTURES_SPREAD_PERCENT = 3.0

# 오더북 벽 계산 범위
WALL_RANGE_PERCENT = 1.0

# 루프
LOOP_SLEEP_SEC = 20

# 중복 알림 방지
ALERT_COOLDOWN_SEC = 60 * 10

# 같은 코인이 여러 해외선물 거래소에서 동시에 뜰 때 도배 방지
# 예: HIGH MEXC, HIGH GATE, HIGH BINANCE가 동시에 뜨면 가장 먼저 걸린 1개만 전송
SYMBOL_ALERT_COOLDOWN_SEC = 60 * 30

# 너무 많은 검사 방지
MAX_SPOT_ITEMS = 160

# 1% 벽 기준: 현물/선물 각각 100만원 이상이어야 알림
MIN_SPOT_WALL_KRW = 1_000_000
MIN_FUTURES_WALL_KRW = 1_000_000

# 심볼/단위 오매칭 방어
MAX_REASONABLE_BASIS_PERCENT = 30.0

# 같은 거래소 현물-선물 비교 허용 여부
ALLOW_SAME_EXCHANGE_BASIS = True

# 레버리지/지수/1000단위/이상 심볼 제외
BAD_SYMBOL_PARTS = [
    "3L", "3S", "5L", "5S", "UP", "DOWN", "BULL", "BEAR",
    "1000", "1000000", "PERP", "INDEX"
]

# 국내-해외 전용:
# 국내 현물 → 해외 선물만 검사
ENABLE_FOREIGN_SPOT_SCAN = False

# 국내 거래소별 최대 후보 수
MAX_UPBIT_ITEMS = 140
MAX_BITHUMB_ITEMS = 70
MAX_GOPAX_ITEMS = 40
MAX_COINONE_ITEMS = 50
MAX_KORBIT_ITEMS = 40

# 국제 USD/KRW fallback
FALLBACK_USD_KRW = 1400.0


# ============================================================
# 홈페이지 실시간 대시보드 연동
# ============================================================
# 기본값: 이 py 파일과 같은 폴더의 data 폴더에 저장
# 홈페이지 폴더가 따로 있으면 환경변수 KEDGE_DATA_DIR 로 지정 가능
# 예: set KEDGE_DATA_DIR=C:\Users\pc1\Desktop\kedge_homepage\data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DATA_DIR = os.environ.get("KEDGE_DATA_DIR", os.path.join(BASE_DIR, "data"))
WEB_SIGNALS_PATH = os.path.join(WEB_DATA_DIR, "signals.json")
WEB_STATS_PATH = os.path.join(WEB_DATA_DIR, "stats.json")
MAX_WEB_SIGNALS = 100



# ============================================================
# 해외 거래소
# ============================================================

SPOT_EXCHANGES = [
    ("MEXC", "mexc"),
    ("GATE", "gateio"),
    ("BITGET", "bitget"),
    ("BINGX", "bingx"),
]

FUTURES_EXCHANGES = [
    ("MEXC", "mexc"),
    ("GATE", "gateio"),
    ("BITGET", "bitget"),
    ("BINGX", "bingx"),
    ("BINANCE", "binance"),
    ("OKX", "okx"),
    ("BYBIT", "bybit"),
]


# ============================================================
# 기본 유틸
# ============================================================

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 spot-futures-basis-bot/1.0"})
last_alert_at: Dict[str, float] = {}
active_symbol_locks: Dict[str, Dict[str, Any]] = {}
last_symbol_alert_at: Dict[str, float] = {}


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(x, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def normalize_symbol(symbol: str) -> str:
    s = str(symbol).upper().strip()
    s = s.replace("-", "").replace("_", "").replace("/", "")
    replace_map = {
        "1000SATS": "1000SATS",
        "1000BONK": "1000BONK",
        "1000PEPE": "1000PEPE",
    }
    return replace_map.get(s, s)


def is_bad_symbol(symbol: str) -> bool:
    s = str(symbol).upper().strip()
    if not s or len(s) <= 1:
        return True
    if s.startswith("1000") or s.startswith("1000000"):
        return True
    for part in BAD_SYMBOL_PARTS:
        if part in s:
            return True
    return False


def strict_same_base(spot: Dict[str, Any], future_market: str, fex: Any = None) -> bool:
    """
    현물/선물 실제 base가 같은지 2중 확인.
    ccxt market metadata와 문자열 심볼을 같이 비교해서 오매칭 방어.
    """
    spot_base = normalize_symbol(spot.get("symbol", ""))
    if is_bad_symbol(spot_base):
        return False

    future_base = ""
    try:
        if fex is not None and hasattr(fex, "markets"):
            m = fex.markets.get(future_market) or {}
            future_base = normalize_symbol(m.get("base", ""))
    except Exception:
        future_base = ""

    if not future_base:
        future_base = normalize_symbol(str(future_market).split("/")[0].split(":")[0])

    if is_bad_symbol(future_base):
        return False

    return spot_base == future_base


def calc_spread_percent(bid: float, ask: float) -> float:
    if bid <= 0 or ask <= 0:
        return 999.0
    return (ask / bid - 1.0) * 100.0


def calc_basis_percent(futures_bid: float, spot_ask: float) -> float:
    if spot_ask <= 0:
        return 0.0
    return (futures_bid / spot_ask - 1.0) * 100.0


def build_btc_baseline_map(
    domestic_spots: List[Dict[str, Any]],
    future_exs: Dict[str, Any],
    usd_krw: float,
) -> Dict[Tuple[str, str], float]:
    """
    BTC 기준 실시간 프리미엄 계산.
    key = (국내현물거래소, 해외선물거래소)
    value = BTC 현물-선물 괴리율

    예:
    빗썸 BTC 현물 ask vs Binance BTC 선물 bid
    업비트 BTC 현물 ask vs OKX BTC 선물 bid
    """
    baseline = {}

    btc_spots = {}
    for item in domestic_spots:
        if normalize_symbol(item.get("symbol", "")) == "BTC":
            btc_spots[item.get("source")] = item

    if not btc_spots:
        print("[BTC기준] 국내 BTC 현물 없음")
        return baseline

    for source, btc_spot in btc_spots.items():
        btc_spot_ask_usdt = 0.0
        if btc_spot.get("quote") == "KRW":
            btc_spot_ask_usdt = safe_float(btc_spot.get("best_ask")) / usd_krw
        else:
            btc_spot_ask_usdt = safe_float(btc_spot.get("best_ask"))

        if btc_spot_ask_usdt <= 0:
            continue

        for future_ex_name, fex in future_exs.items():
            try:
                btc_market = find_future_market(fex, "BTC")
                if not btc_market:
                    continue

                btc_future = fetch_ccxt_book(fex, btc_market, is_future=True)
                if not btc_future:
                    continue

                btc_basis = calc_basis_percent(btc_future["best_bid"], btc_spot_ask_usdt)
                baseline[(source, future_ex_name)] = btc_basis
                print(f"[BTC기준] {source} -> {future_ex_name}: {btc_basis:+.2f}%")
                time.sleep(0.02)
            except Exception as e:
                print(f"[BTC기준 실패] {source} -> {future_ex_name}: {e}")
                continue

    return baseline


def fmt_krw(v: float) -> str:
    return f"{v:,.0f} KRW"


def fmt_usdt(v: float) -> str:
    return f"{v:,.2f} USDT"


def cooldown_ok(key: str) -> bool:
    t = time.time()
    old = last_alert_at.get(key, 0)
    if t - old >= ALERT_COOLDOWN_SEC:
        last_alert_at[key] = t
        return True
    return False


def active_lock_check(symbol: str, current_percent: float) -> bool:
    """
    알림 발생 = 진입했다고 가정.
    목표 도달 전까지 같은 코인 재알림을 막는다.

    return True  -> 아직 잠금 중, 이번 알림 스킵
    return False -> 잠금 없음 또는 목표 도달로 잠금 해제됨
    """
    symbol = normalize_symbol(symbol)
    locked = active_symbol_locks.get(symbol)
    if not locked:
        return False

    if current_percent <= POSITION_RELEASE_PERCENT:
        print(
            f"[목표도달 잠금해제] {symbol} "
            f"현재={current_percent:.2f}% / 해제기준={POSITION_RELEASE_PERCENT:.2f}% "
            f"/ 진입기준={locked.get('entry_percent', 0):.2f}%"
        )
        active_symbol_locks.pop(symbol, None)
        return False

    print(
        f"[진입가정 잠금중] {symbol} "
        f"현재={current_percent:.2f}% / 해제기준={POSITION_RELEASE_PERCENT:.2f}% "
        f"/ 진입기준={locked.get('entry_percent', 0):.2f}%"
    )
    return True


def mark_active_lock(symbol: str, current_percent: float, spot_source: str, future_source: str) -> None:
    """알림을 보낸 코인은 목표 도달 전까지 재알림 금지."""
    symbol = normalize_symbol(symbol)
    active_symbol_locks[symbol] = {
        "entry_percent": current_percent,
        "spot_source": spot_source,
        "future_source": future_source,
        "locked_at": time.time(),
    }


def symbol_cooldown_ok(symbol: str) -> bool:
    """
    같은 코인이 여러 해외 선물 거래소에서 동시에 잡히는 도배 방지.
    예: HIGH가 MEXC/GATE/BINANCE에 동시에 잡혀도 30분에 1회만 전송.
    """
    t = time.time()
    symbol = normalize_symbol(symbol)
    old = last_symbol_alert_at.get(symbol, 0)
    if t - old >= SYMBOL_ALERT_COOLDOWN_SEC:
        last_symbol_alert_at[symbol] = t
        return True
    return False


def _telegram_send_to(token: str, chat_id: str, text: str, label: str) -> bool:
    if not token or not chat_id:
        print(f"[{label} 텔레그램 미설정]\n", text)
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        r = session.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print(f"[{label} 텔레그램 전송 성공]")
            return True
        print(f"[{label} 텔레그램 전송 실패]", r.status_code, r.text[:300])
        return False
    except Exception as e:
        print(f"[{label} 텔레그램 예외]", e)
        return False


def telegram_send(text: str) -> bool:
    """VIP/유료방 전송"""
    return _telegram_send_to(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, text, "VIP")


def telegram_send_free(text: str) -> bool:
    """FREE/무료방 전송"""
    return _telegram_send_to(FREE_TELEGRAM_BOT_TOKEN, FREE_TELEGRAM_CHAT_ID, text, "FREE")


# ============================================================
# 홈페이지 JSON 저장
# ============================================================

def _read_json(path: str, default):
    try:
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write_json_atomic(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)


def save_web_signal(signal: Dict[str, Any]) -> None:
    """
    홈페이지 data/signals.json 저장.
    최신 신호가 맨 위로 오고, 최대 100개만 유지.
    """
    rows = _read_json(WEB_SIGNALS_PATH, [])
    if not isinstance(rows, list):
        rows = []

    rows.insert(0, signal)
    rows = rows[:MAX_WEB_SIGNALS]

    _write_json_atomic(WEB_SIGNALS_PATH, rows)
    update_web_stats(rows)


def update_web_stats(rows: Optional[List[Dict[str, Any]]] = None) -> None:
    """
    홈페이지 data/stats.json 저장.
    최근 24시간 기준으로 감지 수 / 평균 엣지 / 최대 엣지 / VIP 알림 수 계산.
    """
    if rows is None:
        rows = _read_json(WEB_SIGNALS_PATH, [])
    if not isinstance(rows, list):
        rows = []

    now_ts = time.time()
    rows_24h = []
    for row in rows:
        ts = safe_float(row.get("ts"))
        if ts <= 0:
            rows_24h.append(row)
        elif now_ts - ts <= 24 * 60 * 60:
            rows_24h.append(row)

    edges = [safe_float(x.get("real_edge")) for x in rows_24h if safe_float(x.get("real_edge")) > 0]

    stats = {
        "updated_at": now_str(),
        "today": len(rows_24h),
        "avg_edge": round(sum(edges) / len(edges), 2) if edges else 0,
        "max_edge": round(max(edges), 2) if edges else 0,
        "vip": len([x for x in rows_24h if str(x.get("status", "")).upper() in ("VIP_SENT", "VIP 전송") or "VIP" in str(x.get("status", ""))]),
    }

    _write_json_atomic(WEB_STATS_PATH, stats)


def build_free_alert_message(
    spot: Dict[str, Any],
    future_ex_name: str,
    basis_percent: float,
    btc_basis_percent: float,
    edge_percent: float,
    real_fill_krw: float,
) -> str:
    """
    무료방용 요약 알림.
    상세 호가/벽/실체결 세부값은 VIP에서 보게 분리.
    """
    return f"""⚖️ 양방 후보 감지

코인: {spot['symbol']}
국내: {spot['source']}
해외선물: {future_ex_name}

실제 엣지: {edge_percent:+.2f}%
실체결 가능금액: {fmt_krw(real_fill_krw)}

상세 호가 / 벽 / BTC 기준 프리미엄은 VIP에서 확인 가능합니다.

🕒 {now_str()}
"""


def fetch_usd_krw() -> float:
    """
    국제 USD/KRW 환율 기준.
    국내 USDT/KRW는 김프가 섞일 수 있어서 사용하지 않음.
    """
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        data = session.get(url, timeout=5).json()
        krw = safe_float((data.get("rates") or {}).get("KRW"))
        if krw > 1000:
            return krw
    except Exception:
        pass

    try:
        url = "https://api.exchangerate.host/latest"
        data = session.get(url, params={"base": "USD", "symbols": "KRW"}, timeout=5).json()
        krw = safe_float((data.get("rates") or {}).get("KRW"))
        if krw > 1000:
            return krw
    except Exception:
        pass

    return FALLBACK_USD_KRW


# ============================================================
# 오더북 벽 계산
# ============================================================

def sum_ask_wall_quote(asks: List[List[float]], best_ask: float, range_pct: float) -> float:
    """
    현물 매수 가능금액:
    ask 기준 위 range_pct% 안의 quote 누적.
    KRW 마켓이면 KRW, USDT 마켓이면 USDT.
    """
    if not asks or best_ask <= 0:
        return 0.0
    max_price = best_ask * (1.0 + range_pct / 100.0)
    total = 0.0
    for price, amount in asks:
        price = safe_float(price)
        amount = safe_float(amount)
        if price <= 0 or amount <= 0:
            continue
        if price <= max_price:
            total += price * amount
    return total


def sum_bid_wall_quote(bids: List[List[float]], best_bid: float, range_pct: float) -> float:
    """
    선물 숏 가능금액:
    bid 기준 아래 range_pct% 안의 quote 누적.
    USDT 선물이면 USDT.
    """
    if not bids or best_bid <= 0:
        return 0.0
    min_price = best_bid * (1.0 - range_pct / 100.0)
    total = 0.0
    for price, amount in bids:
        price = safe_float(price)
        amount = safe_float(amount)
        if price <= 0 or amount <= 0:
            continue
        if price >= min_price:
            total += price * amount
    return total


# ============================================================
# 국내 현물 수집
# ============================================================

def fetch_upbit_spots() -> List[Dict[str, Any]]:
    out = []
    try:
        markets = session.get("https://api.upbit.com/v1/market/all", timeout=10).json()
        krw_markets = [m["market"] for m in markets if str(m.get("market", "")).startswith("KRW-")]

        # ticker는 한 번에 100개 정도씩
        tickers = []
        for i in range(0, len(krw_markets), 100):
            chunk = krw_markets[i:i+100]
            data = session.get(
                "https://api.upbit.com/v1/ticker",
                params={"markets": ",".join(chunk)},
                timeout=10
            ).json()
            if isinstance(data, list):
                tickers.extend(data)
            time.sleep(0.02)

        for t in tickers:
            market = t.get("market")
            base = normalize_symbol(str(market).split("-")[1])
            volume_krw = safe_float(t.get("acc_trade_price_24h"))
            if volume_krw < MIN_DOMESTIC_VOLUME_KRW:
                continue

            try:
                ob = session.get(
                    "https://api.upbit.com/v1/orderbook",
                    params={"markets": market},
                    timeout=5
                ).json()
                units = ob[0].get("orderbook_units") or []
                bids = [[safe_float(x.get("bid_price")), safe_float(x.get("bid_size"))] for x in units]
                asks = [[safe_float(x.get("ask_price")), safe_float(x.get("ask_size"))] for x in units]
                if not bids or not asks:
                    continue
                best_bid = bids[0][0]
                best_ask = asks[0][0]
                spread = calc_spread_percent(best_bid, best_ask)
                if best_bid > best_ask or spread < 0 or spread > MAX_SPOT_SPREAD_PERCENT:
                    continue

                out.append({
                    "source": "UPBIT",
                    "kind": "DOMESTIC_SPOT",
                    "symbol": base,
                    "market": market,
                    "quote": "KRW",
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": spread,
                    "volume_quote": volume_krw,
                    "volume_krw": volume_krw,
                    "bids": bids,
                    "asks": asks,
                })
                time.sleep(0.01)
            except Exception:
                continue
    except Exception as e:
        print("[업비트 수집 오류]", e)
    return out


def fetch_bithumb_spots() -> List[Dict[str, Any]]:
    out = []
    try:
        ticker = session.get("https://api.bithumb.com/public/ticker/ALL_KRW", timeout=10).json()
        data = ticker.get("data") or {}
        for base, t in data.items():
            if base == "date":
                continue
            base = normalize_symbol(base)
            volume_krw = safe_float(t.get("acc_trade_value_24H"))
            if volume_krw < MIN_DOMESTIC_VOLUME_KRW:
                continue

            try:
                ob = session.get(
                    f"https://api.bithumb.com/public/orderbook/{base}_KRW",
                    params={"count": 30},
                    timeout=5
                ).json()
                od = ob.get("data") or {}
                bids = [[safe_float(x.get("price")), safe_float(x.get("quantity"))] for x in od.get("bids", [])]
                asks = [[safe_float(x.get("price")), safe_float(x.get("quantity"))] for x in od.get("asks", [])]
                bids.sort(key=lambda x: x[0], reverse=True)
                asks.sort(key=lambda x: x[0])
                if not bids or not asks:
                    continue
                best_bid = bids[0][0]
                best_ask = asks[0][0]
                spread = calc_spread_percent(best_bid, best_ask)
                if best_bid > best_ask or spread < 0 or spread > MAX_SPOT_SPREAD_PERCENT:
                    continue

                out.append({
                    "source": "BITHUMB",
                    "kind": "DOMESTIC_SPOT",
                    "symbol": base,
                    "market": f"{base}_KRW",
                    "quote": "KRW",
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": spread,
                    "volume_quote": volume_krw,
                    "volume_krw": volume_krw,
                    "bids": bids,
                    "asks": asks,
                })
                time.sleep(0.01)
            except Exception:
                continue
    except Exception as e:
        print("[빗썸 수집 오류]", e)
    return out


def fetch_gopax_spots() -> List[Dict[str, Any]]:
    out = []
    try:
        pairs = session.get("https://api.gopax.co.kr/trading-pairs", timeout=10).json()
        if not isinstance(pairs, list):
            return out

        for p in pairs:
            name = str(p.get("name") or p.get("id") or "")
            if not name.endswith("-KRW"):
                continue

            base = normalize_symbol(name.split("-")[0])
            try:
                stats = session.get(f"https://api.gopax.co.kr/trading-pairs/{name}/stats", timeout=5).json()
                volume_krw = safe_float(stats.get("quoteVolume")) or safe_float(stats.get("volume")) * safe_float(stats.get("close"))
                if volume_krw < MIN_DOMESTIC_VOLUME_KRW:
                    continue

                book = session.get(f"https://api.gopax.co.kr/trading-pairs/{name}/book", timeout=5).json()
                # GOPAX: [orderId, price, amount]
                bids = [[safe_float(x[1]), safe_float(x[2])] for x in book.get("bid", []) if len(x) >= 3]
                asks = [[safe_float(x[1]), safe_float(x[2])] for x in book.get("ask", []) if len(x) >= 3]
                bids = [x for x in bids if x[0] > 0 and x[1] > 0]
                asks = [x for x in asks if x[0] > 0 and x[1] > 0]
                bids.sort(key=lambda x: x[0], reverse=True)
                asks.sort(key=lambda x: x[0])
                if not bids or not asks:
                    continue

                best_bid = bids[0][0]
                best_ask = asks[0][0]
                spread = calc_spread_percent(best_bid, best_ask)
                if best_bid > best_ask or spread < 0 or spread > MAX_SPOT_SPREAD_PERCENT:
                    continue

                out.append({
                    "source": "GOPAX",
                    "kind": "DOMESTIC_SPOT",
                    "symbol": base,
                    "market": name,
                    "quote": "KRW",
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": spread,
                    "volume_quote": volume_krw,
                    "volume_krw": volume_krw,
                    "bids": bids,
                    "asks": asks,
                })
                time.sleep(0.01)
            except Exception:
                continue
    except Exception as e:
        print("[고팍스 수집 오류]", e)
    return out


def fetch_coinone_spots() -> List[Dict[str, Any]]:
    out = []
    symbols = []

    try:
        data = session.get("https://api.coinone.co.kr/public/v2/markets/KRW", timeout=10).json()
        markets = data.get("markets") or data.get("data") or []
        for m in markets:
            target = m.get("target_currency") or m.get("currency") or m.get("target")
            if target:
                symbols.append(normalize_symbol(target))
    except Exception:
        pass

    if not symbols:
        try:
            data = session.get("https://api.coinone.co.kr/ticker/?currency=all", timeout=10).json()
            for k in data.keys():
                if k.lower() not in ("result", "errorcode", "timestamp", "krw"):
                    symbols.append(normalize_symbol(k))
        except Exception:
            pass

    for base in sorted(set(symbols)):
        try:
            volume_krw = 0.0
            try:
                tdata = session.get(f"https://api.coinone.co.kr/public/v2/ticker_new/KRW/{base}", timeout=5).json()
                tickers = tdata.get("tickers") or []
                if tickers:
                    t = tickers[0]
                    volume_krw = safe_float(t.get("quote_volume")) or safe_float(t.get("target_volume")) * safe_float(t.get("last"))
            except Exception:
                pass

            if volume_krw <= 0:
                try:
                    t = session.get(f"https://api.coinone.co.kr/ticker/?currency={base.lower()}", timeout=5).json()
                    volume_krw = safe_float(t.get("volume")) * safe_float(t.get("last"))
                except Exception:
                    pass

            if volume_krw < MIN_DOMESTIC_VOLUME_KRW:
                continue

            bids, asks = [], []
            try:
                odata = session.get(f"https://api.coinone.co.kr/public/v2/orderbook/KRW/{base}", timeout=5).json()
                orderbooks = odata.get("orderbooks") or []
                if orderbooks:
                    ob = orderbooks[0]
                    bids = [[safe_float(x.get("price")), safe_float(x.get("qty") or x.get("quantity"))] for x in ob.get("bid", [])]
                    asks = [[safe_float(x.get("price")), safe_float(x.get("qty") or x.get("quantity"))] for x in ob.get("ask", [])]
            except Exception:
                pass

            if not bids or not asks:
                try:
                    ob = session.get(f"https://api.coinone.co.kr/orderbook/?currency={base.lower()}", timeout=5).json()
                    bids = [[safe_float(x.get("price")), safe_float(x.get("qty"))] for x in ob.get("bid", [])]
                    asks = [[safe_float(x.get("price")), safe_float(x.get("qty"))] for x in ob.get("ask", [])]
                except Exception:
                    pass

            bids = [x for x in bids if x[0] > 0 and x[1] > 0]
            asks = [x for x in asks if x[0] > 0 and x[1] > 0]
            bids.sort(key=lambda x: x[0], reverse=True)
            asks.sort(key=lambda x: x[0])
            if not bids or not asks:
                continue

            best_bid = bids[0][0]
            best_ask = asks[0][0]
            spread = calc_spread_percent(best_bid, best_ask)
            if best_bid > best_ask or spread < 0 or spread > MAX_SPOT_SPREAD_PERCENT:
                continue

            out.append({
                "source": "COINONE",
                "kind": "DOMESTIC_SPOT",
                "symbol": base,
                "market": f"{base}/KRW",
                "quote": "KRW",
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": spread,
                "volume_quote": volume_krw,
                "volume_krw": volume_krw,
                "bids": bids,
                "asks": asks,
            })
            time.sleep(0.01)
        except Exception:
            continue

    return out


def fetch_korbit_spots() -> List[Dict[str, Any]]:
    out = []
    try:
        data = session.get("https://api.korbit.co.kr/v1/ticker/detailed/all", timeout=10).json()
        if not isinstance(data, dict):
            return out

        for pair, ticker in data.items():
            if not str(pair).endswith("_krw"):
                continue
            base = normalize_symbol(str(pair).split("_")[0])
            volume_krw = safe_float(ticker.get("volume")) * safe_float(ticker.get("last"))
            if volume_krw < MIN_DOMESTIC_VOLUME_KRW:
                continue

            try:
                ob = session.get(
                    "https://api.korbit.co.kr/v1/orderbook",
                    params={"currency_pair": pair},
                    timeout=5
                ).json()
                bids = [[safe_float(x[0]), safe_float(x[1])] for x in ob.get("bids", [])]
                asks = [[safe_float(x[0]), safe_float(x[1])] for x in ob.get("asks", [])]
                bids = [x for x in bids if x[0] > 0 and x[1] > 0]
                asks = [x for x in asks if x[0] > 0 and x[1] > 0]
                bids.sort(key=lambda x: x[0], reverse=True)
                asks.sort(key=lambda x: x[0])
                if not bids or not asks:
                    continue

                best_bid = bids[0][0]
                best_ask = asks[0][0]
                spread = calc_spread_percent(best_bid, best_ask)
                if best_bid > best_ask or spread < 0 or spread > MAX_SPOT_SPREAD_PERCENT:
                    continue

                out.append({
                    "source": "KORBIT",
                    "kind": "DOMESTIC_SPOT",
                    "symbol": base,
                    "market": pair,
                    "quote": "KRW",
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": spread,
                    "volume_quote": volume_krw,
                    "volume_krw": volume_krw,
                    "bids": bids,
                    "asks": asks,
                })
                time.sleep(0.01)
            except Exception:
                continue

    except Exception as e:
        print("[코빗 수집 오류]", e)
    return out


# ============================================================
# 해외 CCXT
# ============================================================

def init_exchange(name: str, ccxt_id: str, default_type: str):
    klass = getattr(ccxt, ccxt_id, None)
    if klass is None:
        raise RuntimeError(f"ccxt 미지원: {ccxt_id}")

    options = {"defaultType": default_type}

    # 거래소별 선물 타입 보정
    if default_type == "swap":
        if ccxt_id == "binance":
            options["defaultType"] = "future"
        elif ccxt_id == "okx":
            options["defaultType"] = "swap"
        elif ccxt_id == "bybit":
            options["defaultType"] = "swap"
        elif ccxt_id == "bitget":
            options["defaultType"] = "swap"
        elif ccxt_id == "gateio":
            options["defaultType"] = "swap"
        elif ccxt_id == "mexc":
            options["defaultType"] = "swap"
        elif ccxt_id == "bingx":
            options["defaultType"] = "swap"

    params = {
        "enableRateLimit": True,
        "timeout": 8000,
        "options": options,
    }

    if ccxt_id == "bingx":
        params["apiKey"] = BINGX_API_KEY
        params["secret"] = BINGX_SECRET_KEY

    ex = klass(params)
    ex.load_markets()
    return ex


def init_ccxt_all() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    spot_exs = {}
    future_exs = {}

    if ccxt is None:
        print("ccxt 미설치: py -m pip install ccxt")
        return spot_exs, future_exs

    for name, ccxt_id in SPOT_EXCHANGES:
        try:
            ex = init_exchange(name, ccxt_id, "spot")
            spot_exs[name] = ex
            print(f"[해외 현물 등록] {name} / 마켓 {len(ex.markets)}개")
        except Exception as e:
            print(f"[해외 현물 등록 실패] {name}: {e}")

    for name, ccxt_id in FUTURES_EXCHANGES:
        try:
            # 대부분 swap이 USDT 무기한 선물
            ex = init_exchange(name, ccxt_id, "swap")
            future_exs[name] = ex
            print(f"[해외 선물 등록] {name} / 마켓 {len(ex.markets)}개")
        except Exception as e:
            print(f"[해외 선물 등록 실패] {name}: {e}")

    return spot_exs, future_exs


def find_spot_market(ex: Any, base: str) -> Optional[str]:
    base = normalize_symbol(base)
    if is_bad_symbol(base):
        return None

    direct = f"{base}/USDT"
    m = ex.markets.get(direct)
    if m and m.get("spot"):
        return direct

    for symbol, m in ex.markets.items():
        try:
            if not m.get("spot"):
                continue
            if normalize_symbol(m.get("base")) == base and str(m.get("quote")).upper() == "USDT":
                return symbol
        except Exception:
            continue

    return None


def find_future_market(ex: Any, base: str) -> Optional[str]:
    base = normalize_symbol(base)
    if is_bad_symbol(base):
        return None

    direct_candidates = [
        f"{base}/USDT:USDT",
        f"{base}/USDT",
    ]
    for s in direct_candidates:
        m = ex.markets.get(s)
        if m and (m.get("swap") or m.get("future")) and str(m.get("quote", "")).upper() == "USDT":
            return s

    for symbol, m in ex.markets.items():
        try:
            if not (m.get("swap") or m.get("future")):
                continue
            if normalize_symbol(m.get("base")) == base and str(m.get("quote")).upper() == "USDT":
                return symbol
        except Exception:
            continue

    return None


def fetch_ccxt_book(ex: Any, market: str, is_future: bool = False) -> Optional[Dict[str, Any]]:
    try:
        ob = ex.fetch_order_book(market, limit=50)
        bids = [[safe_float(x[0]), safe_float(x[1])] for x in (ob.get("bids") or []) if len(x) >= 2]
        asks = [[safe_float(x[0]), safe_float(x[1])] for x in (ob.get("asks") or []) if len(x) >= 2]
        bids = [x for x in bids if x[0] > 0 and x[1] > 0]
        asks = [x for x in asks if x[0] > 0 and x[1] > 0]
        bids.sort(key=lambda x: x[0], reverse=True)
        asks.sort(key=lambda x: x[0])

        if not bids or not asks:
            return None

        best_bid = bids[0][0]
        best_ask = asks[0][0]
        spread = calc_spread_percent(best_bid, best_ask)
        max_spread = MAX_FUTURES_SPREAD_PERCENT if is_future else MAX_SPOT_SPREAD_PERCENT
        if best_bid > best_ask or spread < 0 or spread > max_spread:
            return None

        volume_usdt = 0.0
        try:
            t = ex.fetch_ticker(market)
            volume_usdt = safe_float(t.get("quoteVolume"))
            if volume_usdt <= 0:
                volume_usdt = safe_float(t.get("baseVolume")) * safe_float(t.get("last"))
        except Exception:
            pass

        return {
            "market": market,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "volume_usdt": volume_usdt,
            "bids": bids,
            "asks": asks,
        }
    except Exception:
        return None


def fetch_foreign_spots(spot_exs: Dict[str, Any], symbols: List[str], usd_krw: float) -> List[Dict[str, Any]]:
    out = []

    for ex_name, ex in spot_exs.items():
        for base in symbols:
            try:
                market = find_spot_market(ex, base)
                if not market:
                    continue

                book = fetch_ccxt_book(ex, market, is_future=False)
                if not book:
                    continue

                if book["volume_usdt"] and book["volume_usdt"] < MIN_FOREIGN_VOLUME_USDT:
                    continue

                out.append({
                    "source": ex_name,
                    "kind": "FOREIGN_SPOT",
                    "symbol": base,
                    "market": market,
                    "quote": "USDT",
                    "best_bid": book["best_bid"],
                    "best_ask": book["best_ask"],
                    "spread": book["spread"],
                    "volume_quote": book["volume_usdt"],
                    "volume_krw": book["volume_usdt"] * usd_krw,
                    "bids": book["bids"],
                    "asks": book["asks"],
                })
                time.sleep(0.01)
            except Exception:
                continue

    return out


# ============================================================
# 스캔
# ============================================================

def fetch_all_domestic_spots() -> List[Dict[str, Any]]:
    funcs = [
        (fetch_upbit_spots, MAX_UPBIT_ITEMS),
        (fetch_bithumb_spots, MAX_BITHUMB_ITEMS),
        (fetch_coinone_spots, MAX_COINONE_ITEMS),
    ]

    all_items = []
    for fn, limit in funcs:
        items = fn()
        items.sort(key=lambda x: x.get("volume_krw", 0), reverse=True)
        limited = items[:limit]
        print(f"[국내 현물] {fn.__name__}: {len(items)}개 → 검사 {len(limited)}개")
        all_items.extend(limited)

    # 업비트가 대형주 위주라 거래대금 단순 정렬에서 밀리면 알람이 거의 안 뜰 수 있음.
    # 업비트 우선 → 빗썸 → 코인원 순서로 보되, 각 거래소 안에서는 거래대금 높은 순.
    source_rank = {"UPBIT": 0, "BITHUMB": 1, "COINONE": 2}
    all_items.sort(key=lambda x: (source_rank.get(x.get("source", ""), 99), -x.get("volume_krw", 0)))
    return all_items


def build_alert_message(
    spot: Dict[str, Any],
    future_ex_name: str,
    future: Dict[str, Any],
    basis_percent: float,
    btc_basis_percent: float,
    edge_percent: float,
    spot_wall_krw: float,
    future_wall_krw: float,
    real_fill_krw: float,
    usd_krw: float,
) -> str:
    symbol = spot["symbol"]

    if spot["quote"] == "KRW":
        spot_price_text = f"{spot['best_ask']:.8f} KRW"
        spot_wall_text = fmt_krw(spot_wall_krw)
        spot_volume_text = fmt_krw(spot.get("volume_krw", 0))
    else:
        spot_price_text = f"{spot['best_ask']:.8f} USDT / {spot['best_ask'] * usd_krw:.8f} KRW"
        spot_wall_text = f"{fmt_usdt(spot_wall_krw / usd_krw)} / {fmt_krw(spot_wall_krw)}"
        spot_volume_text = f"{fmt_usdt(spot.get('volume_quote', 0))} / {fmt_krw(spot.get('volume_krw', 0))}"

    future_price_krw = future["best_bid"] * usd_krw

    text = f"""⚖️ 현물-선물 양방 후보

코인: {symbol}
전략: 현물 매수 + 선물 숏

━━━━━━━━━━━━━━

현물
거래소: {spot['source']}
마켓: {spot['market']}
매수 기준 매도1호가: {spot_price_text}
스프레드: {spot['spread']:.2f}%
24h 거래대금: {spot_volume_text}

선물
거래소: {future_ex_name}
마켓: {future['market']}
숏 기준 매수1호가: {future['best_bid']:.8f} USDT / {future_price_krw:.8f} KRW
스프레드: {future['spread']:.2f}%
24h 거래대금: {fmt_usdt(future.get('volume_usdt', 0))}

━━━━━━━━━━━━━━

괴리율: +{basis_percent:.2f}%
BTC 기준 프리미엄: {btc_basis_percent:+.2f}%
실제 엣지: {edge_percent:+.2f}%

현물 매도벽({WALL_RANGE_PERCENT:.1f}%): {spot_wall_text}
선물 매수벽({WALL_RANGE_PERCENT:.1f}%): {fmt_usdt(future_wall_krw / usd_krw)} / {fmt_krw(future_wall_krw)}

실체결 가능금액: {fmt_usdt(real_fill_krw / usd_krw)} / {fmt_krw(real_fill_krw)}

━━━━━━━━━━━━━━

📌 해석
선물이 현물보다 비싸게 거래 중입니다.
단, BTC 기준 프리미엄을 차감한 실제 엣지 기준으로 선별했습니다.
현물 매수 + 선물 숏 후 BTC 기준 괴리 회귀를 노리는 구조입니다.

주의:
수수료 / 펀딩비 / 선물 강제청산 / 현물 출금 가능 여부는 별도 확인 필요.

🕒 {now_str()}
"""
    return text


def scan_once(spot_exs: Dict[str, Any], future_exs: Dict[str, Any]) -> None:
    usd_krw = fetch_usd_krw()
    print(f"[국제환율] USD/KRW = {usd_krw:.2f}")

    domestic_spots = fetch_all_domestic_spots()

    # 국내에서 나온 심볼 + 해외 주요 현물 심볼 비교용
    domestic_symbols = sorted(set(x["symbol"] for x in domestic_spots))
    print(f"[국내 심볼] {len(domestic_symbols)}개")

    if ENABLE_FOREIGN_SPOT_SCAN:
        # 해외 현물도 같이 검사: MEXC 현물 100 / Gate 선물 110 같은 구조
        foreign_spots = fetch_foreign_spots(spot_exs, domestic_symbols, usd_krw)
        print(f"[해외 현물] {len(foreign_spots)}개")
    else:
        foreign_spots = []
        print("[해외 현물] 속도 모드로 스킵")

    all_spots = domestic_spots + foreign_spots

    # 최종 검사도 업비트 우선순위 유지
    source_rank = {"UPBIT": 0, "BITHUMB": 1, "COINONE": 2}
    all_spots.sort(key=lambda x: (source_rank.get(x.get("source", ""), 99), -x.get("volume_krw", 0)))
    all_spots = all_spots[:MAX_SPOT_ITEMS]
    print(f"[최종 검사 현물] {len(all_spots)}개")

    btc_baseline_map = build_btc_baseline_map(domestic_spots, future_exs, usd_krw)

    checked = 0
    alerts = 0

    for spot in all_spots:
        base = spot["symbol"]

        # 현물 매수 기준 가격을 USDT로 환산
        if spot["quote"] == "KRW":
            spot_ask_usdt = spot["best_ask"] / usd_krw
            spot_wall_krw = sum_ask_wall_quote(spot["asks"], spot["best_ask"], WALL_RANGE_PERCENT)
        else:
            spot_ask_usdt = spot["best_ask"]
            spot_wall_usdt = sum_ask_wall_quote(spot["asks"], spot["best_ask"], WALL_RANGE_PERCENT)
            spot_wall_krw = spot_wall_usdt * usd_krw

        if spot_ask_usdt <= 0:
            continue

        for future_ex_name, fex in future_exs.items():
            try:
                fmarket = find_future_market(fex, base)
                if not fmarket:
                    continue

                if not ALLOW_SAME_EXCHANGE_BASIS and spot.get("source") == future_ex_name:
                    continue

                future = fetch_ccxt_book(fex, fmarket, is_future=True)
                if not future:
                    continue

                if not strict_same_base(spot, fmarket, fex):
                    print(f"[심볼불일치 제외] spot={spot.get('source')} {spot.get('market')} / future={future_ex_name} {fmarket}")
                    continue

                if future["volume_usdt"] and future["volume_usdt"] < MIN_FOREIGN_VOLUME_USDT:
                    continue

                checked += 1

                # 선물 숏은 bid에 때리는 기준
                basis = calc_basis_percent(future["best_bid"], spot_ask_usdt)

                btc_basis = btc_baseline_map.get((spot.get("source"), future_ex_name))
                if btc_basis is None:
                    if REQUIRE_BTC_BASELINE:
                        print(f"[BTC기준 없음 제외] {spot.get('source')} {base} -> {future_ex_name}")
                        continue
                    btc_basis = 0.0

                # BTC 기준 프리미엄 차감 후 실제 엣지
                edge = basis - btc_basis

                if edge < MIN_EDGE_PERCENT:
                    continue

                # 알림 발생 후 진입했다고 가정: 목표 도달 전까지 같은 코인 재알림 금지
                if active_lock_check(base, edge):
                    continue

                # 비정상 심볼/단위 방어
                # 30% 초과는 대부분 단위/심볼 충돌 가능성이 높아서 제외
                if basis > MAX_REASONABLE_BASIS_PERCENT:
                    print(f"[이상괴리 제외] {spot['source']} {base} -> {future_ex_name} basis={basis:.2f}% edge={edge:.2f}%")
                    continue

                future_wall_usdt = sum_bid_wall_quote(future["bids"], future["best_bid"], WALL_RANGE_PERCENT)
                future_wall_krw = future_wall_usdt * usd_krw
                real_fill_krw = min(spot_wall_krw, future_wall_krw)

                # 1% 벽 기준: 양쪽 각각 100만원 이상이어야 수익금 측정이 의미 있음
                if spot_wall_krw < MIN_SPOT_WALL_KRW:
                    continue
                if future_wall_krw < MIN_FUTURES_WALL_KRW:
                    continue
                if real_fill_krw < MIN_REAL_FILL_KRW:
                    continue

                key = f"BASIS:{spot['source']}:{spot['market']}:{future_ex_name}:{fmarket}"
                if not cooldown_ok(key):
                    continue

                if not symbol_cooldown_ok(base):
                    print(f"[동일코인 쿨다운 제외] {base} / {spot['source']} -> {future_ex_name}")
                    continue

                msg = build_alert_message(
                    spot=spot,
                    future_ex_name=future_ex_name,
                    future=future,
                    basis_percent=basis,
                    btc_basis_percent=btc_basis,
                    edge_percent=edge,
                    spot_wall_krw=spot_wall_krw,
                    future_wall_krw=future_wall_krw,
                    real_fill_krw=real_fill_krw,
                    usd_krw=usd_krw,
                )
                print(msg)
                if telegram_send(msg):
                    mark_active_lock(base, edge, spot.get("source", ""), future_ex_name)

                    free_msg = build_free_alert_message(
                        spot=spot,
                        future_ex_name=future_ex_name,
                        basis_percent=basis,
                        btc_basis_percent=btc_basis,
                        edge_percent=edge,
                        real_fill_krw=real_fill_krw,
                    )
                    telegram_send_free(free_msg)

                    save_web_signal({
                        "ts": time.time(),
                        "time": datetime.now().strftime("%H:%M"),
                        "created_at": now_str(),
                        "coin": base,
                        "domestic": spot.get("source", ""),
                        "domestic_exchange": spot.get("source", ""),
                        "domestic_market": spot.get("market", ""),
                        "foreign": future_ex_name,
                        "foreign_exchange": future_ex_name,
                        "foreign_market": future.get("market", ""),
                        "coin_gap": round(basis, 2),
                        "btc_gap": round(btc_basis, 2),
                        "real_edge": round(edge, 2),
                        "executable_krw": round(real_fill_krw),
                        "krw": round(real_fill_krw),
                        "status": "VIP 전송",
                    })
                alerts += 1
                time.sleep(0.1)

            except Exception:
                continue

    print(f"[스캔 완료] 검사 {checked}개 / 알림 {alerts}개 / {now_str()}")


def boot_message() -> None:
    msg = f"""✅ 국내 현물 → 해외 선물 괴리 감시봇 - BTC프리미엄 적용 시작

전략:
현물 매수 + 선물 숏 전용

국내 현물:
UPBIT / BITHUMB / COINONE
업비트 검사폭 강화: 140개

해외 현물:
이 파일에서는 검사하지 않음

해외 선물:
MEXC / GATE / BITGET / BINGX / BINANCE / OKX / BYBIT

기준:
BTC 기준 실제 엣지 +{MIN_EDGE_PERCENT:.1f}% 이상
기존 절대괴리 참고값 +{MIN_BASIS_PERCENT:.1f}%
1% 현물벽 {fmt_krw(MIN_SPOT_WALL_KRW)} 이상\n1% 선물벽 {fmt_krw(MIN_FUTURES_WALL_KRW)} 이상\n실체결 가능금액 {fmt_krw(MIN_REAL_FILL_KRW)} 이상
국내 거래대금 {fmt_krw(MIN_DOMESTIC_VOLUME_KRW)} 이상
국제 USD/KRW 환율 사용

🕒 {now_str()}
"""
    telegram_send(msg)
    telegram_send_free("✅ K-EDGE FREE 양방 감시 알림 시작\n\n일부 양방 후보 알림이 무료방에 전송됩니다.\n상세 호가 / 벽 / BTC 프리미엄 / 실체결 세부값은 VIP에서 제공됩니다.\n\n🕒 " + now_str())


def main() -> None:
    print("=" * 70)
    print("국내 현물 → 해외 선물 괴리 감시봇 - BTC프리미엄 적용")
    print("중지: Ctrl + C")
    print("=" * 70)

    if ccxt is None:
        print("ccxt 미설치: py -m pip install ccxt")
        return

    spot_exs, future_exs = init_ccxt_all()

    if not future_exs:
        print("선물 거래소 등록 실패")
        return

    boot_message()

    while True:
        try:
            scan_once(spot_exs, future_exs)
        except KeyboardInterrupt:
            print("사용자 중지")
            break
        except Exception as e:
            print("[메인 루프 오류]", e)
            traceback.print_exc()

        time.sleep(LOOP_SLEEP_SEC)


if __name__ == "__main__":
    main()
