# -*- coding: utf-8 -*-
# [K-EDGE V9.2] BITGET ROUTE - 복리/OPEN복구/정지복구/FX파일캐시/안전장치 적용
"""
국내 현물 → 해외 선물 괴리 감시봇 - 빠른 테스트 모드

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
    ※ 홈페이지 레퍼럴 연결 거래소만 사용

필요 설치:
    py -m pip install requests ccxt yfinance

실행:
    py domestic_spot_to_foreign_futures_bot_upbit_btc_fallback_test.py
"""

import time
import traceback
import os
import json
import subprocess
import threading
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import requests

try:
    import yfinance as yf
except Exception:
    yf = None

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
MIN_EDGE_PERCENT = 1.5

# 알림 후 진입했다고 가정하고, 실제 엣지가 이 값 이하로 줄어들면 청산/종료 서포트 알림
POSITION_RELEASE_PERCENT = 0.5

# 진입 실제엣지 대비 이 값만큼 더 벌어지면 손절 서포트 알림
# 예: 진입 +2.3% / STOP_EDGE_ADD_PERCENT 2.0 => 손절 기준 +4.3%
STOP_EDGE_ADD_PERCENT = 2.0

# 펀딩비 필터
# 숏 포지션 기준: 양수 펀딩이 높으면 비용이 커지므로 신규 알림 제외
MAX_FUNDING_RATE_PERCENT = 0.05

# 진입 후 펀딩비가 이 값 이상으로 커지면 이벤트형 서포트 알림 1회
FUNDING_SUPPORT_WARN_PERCENT = 0.08

# 권장 레버리지 문구
RECOMMENDED_LEVERAGE_TEXT = "x1 기본 / x2 최대 권장"

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
# V8: 신규 진입은 고정 0.5%가 아니라 현재 실제엣지에서 최소 유지엣지 1.5%를 뺀 값까지 허용한다.
# 예: 현재 실제엣지 4.0% -> 허용 슬리피지 2.5% / 현재 실제엣지 2.1% -> 허용 슬리피지 0.6%
WALL_RANGE_PERCENT = 0.5
MIN_RETAIN_EDGE_PERCENT = float(os.getenv("MIN_RETAIN_EDGE_PERCENT", "1.5"))
DYNAMIC_SLIPPAGE_STEP_PERCENT = float(os.getenv("DYNAMIC_SLIPPAGE_STEP_PERCENT", "0.5"))

# 루프
LOOP_SLEEP_SEC = 10

# 중복 알림 방지
ALERT_COOLDOWN_SEC = 60 * 10

# 같은 코인이 여러 해외선물 거래소에서 동시에 뜰 때 도배 방지
# 예: HIGH MEXC, HIGH GATE, HIGH BINANCE가 동시에 뜨면 가장 먼저 걸린 1개만 전송
SYMBOL_ALERT_COOLDOWN_SEC = 60 * 30

# 너무 많은 검사 방지
MAX_SPOT_ITEMS = 140

# 0.5% 벽 기준: 현물/선물 각각 100만원 이상이어야 알림
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
MAX_UPBIT_ITEMS = 0
MAX_BITHUMB_ITEMS = 140
MAX_GOPAX_ITEMS = 40
MAX_COINONE_ITEMS = 0
MAX_KORBIT_ITEMS = 40

# 국제 USD/KRW fallback
# V9.0: open.er-api 과대 환율 제거 후 Yahoo 실패 시 사용할 체감 수동값
MANUAL_USD_KRW = 1509.0
FALLBACK_USD_KRW = MANUAL_USD_KRW


# ============================================================
# 홈페이지 실시간 대시보드 연동
# ============================================================
# 기본값: 이 py 파일과 같은 폴더의 data 폴더에 저장
# 홈페이지 폴더가 따로 있으면 환경변수 KEDGE_DATA_DIR 로 지정 가능
# 예: set KEDGE_DATA_DIR=C:\Users\pc1\Desktop\kedge_homepage\data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DATA_DIR = r"C:\Users\pc1\Desktop\k-edge-homepage\data"
WEB_SIGNALS_PATH = os.path.join(WEB_DATA_DIR, "signals_bitget.json")
WEB_STATS_PATH = os.path.join(WEB_DATA_DIR, "stats_bitget.json")
MAX_WEB_SIGNALS = 100




# ============================================================
# 로컬 환경설정 자동 로드
# - 4파일을 새 CMD에서 각각 실행하면 SUPABASE_URL/SERVICE_KEY 환경변수가 빠지는 경우가 많다.
# - 같은 폴더의 kedge_supabase_config.json 또는 .env 에서 자동으로 읽는다.
# ============================================================
def _load_kedge_local_env() -> None:
    try:
        cfg_path = os.path.join(BASE_DIR if 'BASE_DIR' in globals() else os.path.dirname(os.path.abspath(__file__)), "kedge_supabase_config.json")
    except Exception:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kedge_supabase_config.json")

    # JSON 우선: {"SUPABASE_URL":"...", "SUPABASE_SERVICE_KEY":"..."}
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if v is not None and str(v).strip() and not os.getenv(str(k)):
                        os.environ[str(k)] = str(v).strip()
                print(f"[로컬설정 로드] {cfg_path}")
                return
    except Exception as e:
        print("[로컬설정 JSON 로드 실패]", e)

    # .env 보조 지원
    for name in (".env", "kedge_env.txt"):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name)
        try:
            if not os.path.exists(env_path):
                continue
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v and not os.getenv(k):
                        os.environ[k] = v
            print(f"[로컬설정 로드] {env_path}")
            return
        except Exception as e:
            print("[로컬설정 ENV 로드 실패]", name, e)

_load_kedge_local_env()


# ============================================================
# AUTO / Supabase / 승인회원 DM 설정
# ============================================================
# Supabase REST API 값은 환경변수로 넣는 것을 권장.
# set SUPABASE_URL=https://xxxxx.supabase.co
# set SUPABASE_SERVICE_KEY=xxxxx
SUPABASE_URL = (os.getenv("SUPABASE_URL", "").strip() or "https://qakhbihueonefzifrmct.supabase.co").rstrip("/")
# 실수로 /rest/v1 까지 넣어도 자동 보정
if SUPABASE_URL.endswith("/rest/v1"):
    SUPABASE_URL = SUPABASE_URL[:-len("/rest/v1")].rstrip("/")
SUPABASE_SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_KEY", "").strip() or "sb_publishable_XboBFueAITcieSL75B2S5g_qlm4XmOm").strip()

# signals 저장 테이블명
SUPABASE_SIGNALS_TABLE = os.getenv("SUPABASE_SIGNALS_TABLE", "signals").strip()

# 승인회원 테이블명/컬럼명은 홈페이지 스키마에 맞게 바꾸면 됨.
SUPABASE_MEMBERS_TABLE = os.getenv("SUPABASE_MEMBERS_TABLE", "kedge_requests").strip()
SUPABASE_MEMBER_STATUS_COLUMN = os.getenv("SUPABASE_MEMBER_STATUS_COLUMN", "status").strip()
SUPABASE_MEMBER_STATUS_VALUE = os.getenv("SUPABASE_MEMBER_STATUS_VALUE", "APPROVED").strip()
# 실제 DB 컬럼명이 tg_chat_id 이므로 기본값을 tg_chat_id로 둔다.
# 환경변수로 바꾸면 다른 스키마도 사용 가능.
SUPABASE_MEMBER_TELEGRAM_ID_COLUMN = os.getenv("SUPABASE_MEMBER_TELEGRAM_ID_COLUMN", "tg_chat_id").strip()


# AUTO 설정 테이블명. 홈페이지 AUTO 설정 저장값을 봇이 읽는다.
SUPABASE_AUTO_SETTINGS_TABLE = os.getenv("SUPABASE_AUTO_SETTINGS_TABLE", "auto_settings").strip()
AUTO_SETTINGS_CACHE_TTL_SEC = int(os.getenv("AUTO_SETTINGS_CACHE_TTL_SEC", "60"))

# 승인회원 개인 DM/버튼은 기본적으로 VIP 메인 봇 토큰을 사용한다.
# 예전에 SEMI_AUTO_BOT_TOKEN 환경변수가 다른 봇으로 잡혀 있으면 403이 나므로 무시한다.
# 정말 별도 개인봇을 쓸 때만 KEDGE_USER_DM_BOT_TOKEN 환경변수로 지정한다.
# AUTO 개인 DM/정지버튼 전용 봇
# 유료방 알림봇과 분리해서 사용한다.
USER_DM_BOT_TOKEN_DEFAULT = "8055440671:AAHz8G1xtJh5dWzRzraxuyT61PqhxXweuVI"

# 테스트 중에는 이 chat_id로 강제 전송한다.
# 실제 유저 오픈 전에는 빈 문자열로 바꾸면 DB의 tg_chat_id를 사용한다.
FORCE_TEST_USER_DM_CHAT_ID = ""

SEMI_AUTO_BOT_TOKEN = (os.getenv("KEDGE_USER_DM_BOT_TOKEN", "").strip() or USER_DM_BOT_TOKEN_DEFAULT).strip()

# 과거 반자동 금액 버튼 - AUTO 전용에서는 사용하지 않음
AMOUNT_BUTTONS_KRW = [10_000, 50_000, 100_000, 500_000, 1_000_000, 5_000_000]

# 유저 1회 최대 진입금액. 선물MAX/벽금액보다 커도 여기서 한 번 더 컷.
MAX_USER_ENTRY_KRW = int(os.getenv("MAX_USER_ENTRY_KRW", "0"))  # 0이면 고정 상한 없음

# 예상구간: 최고 이론 엣지에서 1%p 차감해서 하단 표시
EXPECTED_PROFIT_DISCOUNT_PERCENT = 1.0

# 잔고 부족 방지용 여유분. 수수료/슬리피지/환율 오차 감안
BALANCE_SAFETY_BUFFER_PERCENT = 5.0

# 자동청산 감시 설정
# 실제 주문 함수가 연결되기 전에는 안전상 REAL_ORDER_ENABLED=False 권장.
REAL_ORDER_ENABLED = False  # V8.3 가상테스트 전용: 실제 주문 강제 OFF
AUTO_CLOSE_ENABLED = os.getenv("AUTO_CLOSE_ENABLED", "true").lower() == "true"

# 익절은 유연하게: +0.5% 이하부터 청산 시도, +0.3% 이하 강제 청산권
AUTO_TAKE_PROFIT_EDGE_PERCENT = float(os.getenv("AUTO_TAKE_PROFIT_EDGE_PERCENT", "0.3"))
AUTO_TAKE_PROFIT_FORCE_EDGE_PERCENT = float(os.getenv("AUTO_TAKE_PROFIT_FORCE_EDGE_PERCENT", "0.3"))

# 손절은 즉시손절이 아니라 단계 경고 후 감시 유지 방식
AUTO_WARN_EDGE_ADD_PERCENT = float(os.getenv("AUTO_WARN_EDGE_ADD_PERCENT", "4.0"))
AUTO_STRONG_WARN_EDGE_ADD_PERCENT = float(os.getenv("AUTO_STRONG_WARN_EDGE_ADD_PERCENT", "6.0"))
AUTO_STOP_WATCH_EDGE_ADD_PERCENT = float(os.getenv("AUTO_STOP_WATCH_EDGE_ADD_PERCENT", "8.0"))
AUTO_STOP_HOLD_SEC = int(os.getenv("AUTO_STOP_HOLD_SEC", "900"))  # 15분

# 하위 호환용 별칭
AUTO_CLOSE_EDGE_PERCENT = AUTO_TAKE_PROFIT_EDGE_PERCENT
AUTO_STOP_EDGE_ADD_PERCENT = AUTO_STOP_WATCH_EDGE_ADD_PERCENT

# 승인 DM 테스트용: True면 semi_auto_state에 이미 연결 기록이 있어도 재전송한다.
# 테스트 끝나면 false로 바꿔도 됨.
FORCE_APPROVAL_DM_EVERY_START = os.getenv("FORCE_APPROVAL_DM_EVERY_START", "false").lower() == "true"

# 테스트 진행 중에는 파일 실행/재실행 시 승인회원 개인 DM으로 시작 알림을 1회 보낸다.
# 실서비스 전에는 CMD에서 set SEND_STARTUP_TEST_DM=false 로 끄면 된다.
SEND_STARTUP_TEST_DM = os.getenv("SEND_STARTUP_TEST_DM", "true").lower() == "true"


# 선택금액 상태 저장
SEMI_AUTO_STATE_PATH = os.path.join(BASE_DIR, "semi_auto_state_bitget.json")


# 텔레그램 callback offset
# 4파일 동시 실행 시 callback poller는 반드시 1개만 켠다.
# 여러 파일이 동시에 getUpdates를 잡으면 버튼 1회 클릭이 2~4회 누적될 수 있다.
ENABLE_CALLBACK_POLLER = os.getenv("ENABLE_CALLBACK_POLLER", "false").lower() == "true"
last_update_id: int = 0

# 승인회원 캐시: 양방 루프마다 DB 전원조회하지 않고 5분마다 갱신
APPROVED_MEMBER_CACHE_TTL_SEC = int(os.getenv("APPROVED_MEMBER_CACHE_TTL_SEC", "300"))
_APPROVED_MEMBERS_CACHE: List[Dict[str, Any]] = []
_APPROVED_MEMBERS_CACHE_AT: float = 0.0
_APPROVED_MEMBERS_CACHE_LOCK = threading.Lock()


# AUTO 설정 캐시: 유저별 운용금액/분할/ON-OFF를 너무 자주 조회하지 않도록 60초 캐시
_AUTO_SETTINGS_CACHE: Dict[str, Dict[str, Any]] = {}
_AUTO_SETTINGS_CACHE_AT: float = 0.0
_AUTO_SETTINGS_CACHE_LOCK = threading.Lock()

# 진입 직전 재검사용 전역 거래소 객체
GLOBAL_FUTURE_EXS: Dict[str, Any] = {}



# ============================================================
# 실전가상 / 페이퍼 트레이딩 데이터 저장
# ============================================================
# REAL_ORDER_ENABLED=False 상태에서 버튼으로 진입하면 실제 주문은 나가지 않고
# 가상 진입/가상 청산 결과를 CSV/JSON으로 저장한다.
PAPER_TRADING_ENABLED = True  # V8.3 가상테스트 전용: 실전가상 저장 강제 ON
PAPER_DATA_DIR = os.path.join(BASE_DIR, "paper_trading_data")
PAPER_ENTRIES_CSV = os.path.join(PAPER_DATA_DIR, "paper_entries.csv")
PAPER_RESULTS_CSV = os.path.join(PAPER_DATA_DIR, "trade_results.csv")
PAPER_ATTEMPTS_CSV = os.path.join(PAPER_DATA_DIR, "auto_entry_attempts.csv")
PAPER_DAILY_STATS_JSON = os.path.join(PAPER_DATA_DIR, "daily_stats.json")

# ============================================================
# V8.2 자동진입 / 긴급정지 설정
# ============================================================
# 기본은 실전가상 자동진입 ON. 실제주문은 REAL_ORDER_ENABLED=True일 때만 나가도록 유지.
AUTO_ENTRY_ENABLED = True  # V8.8 감지즉시 페이퍼 재검사/저장 + 결과DM ON
AUTO_ENTRY_DEFAULT_KRW = 100_000  # V8.3 고정 자동진입금액: 10만원
AUTO_ENTRY_MIN_KRW = 100_000  # V8.3 10만원 미만이면 스킵

# ============================================================
# V9.2 국내 복리 / 안전 / 통계 보강 설정
# ============================================================
# 신규 진입마다 국내 총 운용자산 = 국내 잔고 + OPEN 국내진입금액 합계 기준으로 /20 계산.
# 실전가상(PAPER)에서는 실제 국내잔고 API가 없으므로 "초기 국내 운용금 + 실현손익"을 총 운용자산으로 본다.
DOMESTIC_COMPOUND_ENABLED = os.getenv("DOMESTIC_COMPOUND_ENABLED", "true").lower() == "true"
DOMESTIC_COMPOUND_DIVISOR = int(os.getenv("DOMESTIC_COMPOUND_DIVISOR", "20"))
PAPER_DOMESTIC_BASE_KRW = int(float(os.getenv("PAPER_DOMESTIC_BASE_KRW", "2000000")))
AUTO_ENTRY_MIN_KRW = int(os.getenv("AUTO_ENTRY_MIN_KRW", str(AUTO_ENTRY_MIN_KRW)))

# ============================================================
# V9.3.1 테스트 자금/수수료 프로필
# - 국내 200만 기준 20분할 복리
# - 해외 거래소별 증거금 50만, 레버리지 4배
# - 펀딩비 시뮬레이션 제외
# - 국내/해외 왕복 수수료 예상 차감 후 순손익 기록
# ============================================================
TEST_CAP_FEE_MODE = os.getenv("TEST_CAP_FEE_MODE", "true").lower() == "true"
PAPER_FOREIGN_MARGIN_BASE_KRW_BY_EXCHANGE = {
    "MEXC": int(float(os.getenv("PAPER_FOREIGN_MARGIN_MEXC_KRW", "500000"))),
    "GATE": int(float(os.getenv("PAPER_FOREIGN_MARGIN_GATE_KRW", "500000"))),
    "BITGET": int(float(os.getenv("PAPER_FOREIGN_MARGIN_BITGET_KRW", "500000"))),
    "BINGX": int(float(os.getenv("PAPER_FOREIGN_MARGIN_BINGX_KRW", "500000"))),
}
PAPER_FUTURES_LEVERAGE = float(os.getenv("PAPER_FUTURES_LEVERAGE", "4"))
# 수수료율은 % 단위. 기본 예시: 국내 현물 왕복 0.10% + 해외 선물 왕복 0.04% = 총 0.14%
DOMESTIC_BUY_FEE_PERCENT = float(os.getenv("DOMESTIC_BUY_FEE_PERCENT", "0.05"))
DOMESTIC_SELL_FEE_PERCENT = float(os.getenv("DOMESTIC_SELL_FEE_PERCENT", "0.05"))
FUTURES_ENTRY_FEE_PERCENT = float(os.getenv("FUTURES_ENTRY_FEE_PERCENT", "0.02"))
FUTURES_EXIT_FEE_PERCENT = float(os.getenv("FUTURES_EXIT_FEE_PERCENT", "0.02"))
FUNDING_SIMULATION_ENABLED = os.getenv("FUNDING_SIMULATION_ENABLED", "false").lower() == "true"

def calc_roundtrip_fee_percent() -> float:
    return (
        DOMESTIC_BUY_FEE_PERCENT
        + DOMESTIC_SELL_FEE_PERCENT
        + FUTURES_ENTRY_FEE_PERCENT
        + FUTURES_EXIT_FEE_PERCENT
    )

def calc_required_foreign_margin_krw(domestic_entry_krw: float) -> int:
    lev = max(1.0, safe_float(PAPER_FUTURES_LEVERAGE, 4.0))
    return int(round(max(0.0, safe_float(domestic_entry_krw)) / lev))

# CSV/상태에서 열린 포지션으로 인정할 상태값.
OPEN_ENTRY_STATUSES = {"OPEN", "VIRTUAL_OPEN", "REAL_OPEN", "ACTIVE"}
CLOSED_RESULT_STATUSES = {"AUTO_CLOSED", "AUTO_STOPPED", "MANUAL_STOP_CLOSED", "FUTURES_LIQUIDATED_AUTO_EXIT"}

# Yahoo 환율 4파일 동시호출 방지용 공유 캐시 파일
FX_CACHE_PATH = os.path.join(BASE_DIR, "fx_cache.json")
FX_CACHE_LOCK_PATH = os.path.join(BASE_DIR, "fx_cache.lock")
FX_FILE_CACHE_TTL_SEC = int(os.getenv("FX_FILE_CACHE_TTL_SEC", "30"))
FX_LOCK_STALE_SEC = int(os.getenv("FX_LOCK_STALE_SEC", "10"))

# 거래소별 API 응답속도 로그
# V9.2.1: 기본은 느린 API/실패만 조용히 저장한다.
# 이전처럼 모든 호출을 저장하면 스캔 1회마다 api_speed_log.csv 저장 로그가 수십~수백 줄 도배된다.
API_SPEED_LOG_ENABLED = os.getenv("API_SPEED_LOG_ENABLED", "true").lower() == "true"
API_SPEED_LOG_ONLY_SLOW = os.getenv("API_SPEED_LOG_ONLY_SLOW", "true").lower() == "true"
API_SPEED_LOG_SAVE_NORMAL = os.getenv("API_SPEED_LOG_SAVE_NORMAL", "false").lower() == "true"
API_SLOW_WARN_SEC = float(os.getenv("API_SLOW_WARN_SEC", "1.5"))
API_SPEED_CSV = os.path.join(PAPER_DATA_DIR, "api_speed_log.csv")

# 선물 강청/헤지붕괴 감지 자리. 실주문 연결 전까지는 상태/경고/CSV만 동작.
FUTURES_LIQUIDATION_GUARD_ENABLED = os.getenv("FUTURES_LIQUIDATION_GUARD_ENABLED", "true").lower() == "true"
AUTO_ENTRY_REQUIRE_APPROVED_MEMBER = os.getenv("AUTO_ENTRY_REQUIRE_APPROVED_MEMBER", "true").lower() == "true"
AUTO_ENTRY_SEND_DM_RESULT = os.getenv("AUTO_ENTRY_SEND_DM_RESULT", "true").lower() == "true"
AUTO_ENTRY_MODE_LABEL = "실전가상 자동진입" if (PAPER_TRADING_ENABLED and not REAL_ORDER_ENABLED) else "실전 자동진입"

# V8.8: 실전가상에서는 API/잔고 조회를 건너뛰고, 현재 호가/엣지/벽 재검사만 즉시 수행한다.
# 텔레그램 DM은 진입 판단 이후 결과만 보낸다.
PAPER_FAST_RECHECK_ONLY = True
MAX_AUTO_RECHECK_DELAY_SEC = float(os.getenv("MAX_AUTO_RECHECK_DELAY_SEC", "2.0"))

# 자동정지 상태 파일. STOP 누르면 신규 자동진입은 즉시 중단되고 ACTIVE 포지션 전체 종료 처리.
AUTO_CONTROL_PATH = os.path.join(BASE_DIR, "auto_trading_control.json")


def _ensure_paper_data_dir() -> None:
    try:
        os.makedirs(PAPER_DATA_DIR, exist_ok=True)
    except Exception:
        pass


def _csv_append(path: str, fieldnames: List[str], row: Dict[str, Any]) -> None:
    """CSV 누적 저장.

    V9.1: 기존 CSV에 새 컬럼이 추가되어도 파일을 새로 만들지 않고
    기존 행을 보존한 채 헤더를 확장해서 계속 이어서 저장한다.
    """
    _ensure_paper_data_dir()
    exists = os.path.exists(path)

    final_fieldnames = list(fieldnames)
    old_rows = []
    old_fieldnames = []

    if exists:
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as rf:
                reader = csv.DictReader(rf)
                old_fieldnames = list(reader.fieldnames or [])
                old_rows = list(reader)
            for name in old_fieldnames:
                if name not in final_fieldnames:
                    final_fieldnames.append(name)
            for name in fieldnames:
                if name not in final_fieldnames:
                    final_fieldnames.append(name)

            # 기존 헤더에 새 필드가 없으면 전체 파일을 확장 헤더로 재작성
            if any(name not in old_fieldnames for name in fieldnames):
                with open(path, "w", newline="", encoding="utf-8-sig") as wf:
                    writer = csv.DictWriter(wf, fieldnames=final_fieldnames)
                    writer.writeheader()
                    for old_row in old_rows:
                        writer.writerow({k: old_row.get(k, "") for k in final_fieldnames})
        except Exception as e:
            print(f"[CSV 헤더 확장 실패 - append로 진행] {path} / {e}")
            final_fieldnames = list(fieldnames)

    safe_row = {}
    for k in final_fieldnames:
        v = row.get(k, "")
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False)
        safe_row[k] = v

    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=final_fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(safe_row)
    print(f"[CSV 저장 성공] {path}")


# ============================================================
# V9.1 엣지 레벨별 통계(2% / 3% / 4% / 5%)
# - AUTO 진입 기준은 기존 1.5% 이상 유지
# - 통계만 2/3/4/5 이상 누적 집계
# - 기존 paper_trading_data CSV/JSON에 계속 이어서 저장
# ============================================================
EDGE_TIER_LEVELS = [2.0, 3.0, 4.0, 5.0]


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


def _blank_edge_stat() -> Dict[str, Any]:
    return {
        "closed_count": 0,
        "tp_count": 0,
        "sl_count": 0,
        "total_entry_krw": 0.0,
        "total_pnl_krw": 0.0,
        "avg_pnl_percent": 0.0,
        "avg_holding_sec": 0.0,
    }


def _add_edge_stat(stat: Dict[str, Any], entry_krw: float, pnl_krw: float, pnl_percent: float, is_tp: bool, is_sl: bool, holding_sec: float = 0.0) -> None:
    old_n = int(stat.get("closed_count", 0))
    old_avg = safe_float(stat.get("avg_pnl_percent"))
    old_hold = safe_float(stat.get("avg_holding_sec"))
    stat["closed_count"] = old_n + 1
    stat["total_entry_krw"] = safe_float(stat.get("total_entry_krw")) + safe_float(entry_krw)
    stat["total_pnl_krw"] = safe_float(stat.get("total_pnl_krw")) + safe_float(pnl_krw)
    stat["avg_pnl_percent"] = round(((old_avg * old_n) + safe_float(pnl_percent)) / max(1, old_n + 1), 4)
    stat["avg_holding_sec"] = round(((old_hold * old_n) + safe_float(holding_sec)) / max(1, old_n + 1), 2)
    if is_tp:
        stat["tp_count"] = int(stat.get("tp_count", 0)) + 1
    if is_sl:
        stat["sl_count"] = int(stat.get("sl_count", 0)) + 1


def update_edge_tier_stats(day: Dict[str, Any], result_row: Dict[str, Any]) -> None:
    """일통계에 엣지 레벨별 누적 통계를 추가한다.

    by_entry_edge_bucket: 실제 진입 엣지를 단일 구간으로 분류
      - 1.5%+, 2%+, 3%+, 4%+, 5%+

    edge_ge: 누적 기준
      - 2% 이상, 3% 이상, 4% 이상, 5% 이상
      - 예: 3.2% 진입은 ge_2와 ge_3에 모두 집계
    """
    entry_edge = safe_float(result_row.get("entry_edge"))
    entry_krw = safe_float(result_row.get("entry_krw"))
    pnl_krw = safe_float(result_row.get("pnl_krw"))
    pnl_percent = safe_float(result_row.get("pnl_percent"))
    holding_sec = safe_float(result_row.get("holding_sec"))
    status = str(result_row.get("status") or "")
    is_tp = ("TAKE" in status or "TP" in status or "PROFIT" in status or pnl_krw > 0)
    is_sl = ("STOP" in status or "SL" in status or pnl_krw < 0)

    bucket = get_entry_edge_bucket(entry_edge)
    result_row["entry_edge_bucket"] = bucket

    by_bucket = day.setdefault("by_entry_edge_bucket", {})
    _add_edge_stat(by_bucket.setdefault(bucket, _blank_edge_stat()), entry_krw, pnl_krw, pnl_percent, is_tp, is_sl, holding_sec)

    ge = day.setdefault("edge_ge", {})
    for level in EDGE_TIER_LEVELS:
        if entry_edge >= level:
            key = f"{int(level)}%+"
            _add_edge_stat(ge.setdefault(key, _blank_edge_stat()), entry_krw, pnl_krw, pnl_percent, is_tp, is_sl, holding_sec)


def paper_record_auto_attempt(user_id: str, signal: Dict[str, Any], amount_krw: int, status: str, reason: str) -> None:
    """V8.7 자동진입 시도/미진입 원인 기록.

    성공/실패와 무관하게 자동진입이 시도된 후보를 auto_entry_attempts.csv에 남긴다.
    실제 주문 OFF 가상테스트에서도 실패 사유를 나중에 추적할 수 있게 한다.
    """
    if not PAPER_TRADING_ENABLED:
        return
    try:
        fieldnames = [
            "event_time", "signal_id", "user_id", "coin", "domestic", "foreign",
            "amount_krw", "detected_edge", "expected_profit_min", "expected_profit_max",
            "btc_gap", "coin_gap", "allowed_slippage_percent", "min_retain_edge_percent",
            "spot_wall_krw", "futures_wall_krw", "real_fill_krw", "futures_position_limit_krw",
            "funding_rate", "entry_edge_bucket", "edge_ge_2", "edge_ge_3", "edge_ge_4", "edge_ge_5", "status", "reason", "real_order"
        ]
        row = {
            "event_time": now_str(),
            "signal_id": signal.get("signal_id"),
            "user_id": user_id,
            "coin": signal.get("coin"),
            "domestic": signal.get("domestic"),
            "foreign": signal.get("foreign"),
            "amount_krw": int(safe_float(amount_krw)),
            "detected_edge": round(safe_float(signal.get("real_edge")), 4),
            "expected_profit_min": round(safe_float(signal.get("expected_profit_min")), 4),
            "expected_profit_max": round(safe_float(signal.get("expected_profit_max")), 4),
            "btc_gap": round(safe_float(signal.get("btc_gap")), 4),
            "coin_gap": round(safe_float(signal.get("coin_gap")), 4),
            "allowed_slippage_percent": round(safe_float(signal.get("allowed_slippage_percent")), 4),
            "min_retain_edge_percent": round(safe_float(signal.get("min_retain_edge_percent"), MIN_RETAIN_EDGE_PERCENT), 4),
            "spot_wall_krw": round(safe_float(signal.get("spot_wall_krw")), 2),
            "futures_wall_krw": round(safe_float(signal.get("futures_wall_krw")), 2),
            "real_fill_krw": round(safe_float(signal.get("real_fill_krw")), 2),
            "futures_position_limit_krw": round(safe_float(signal.get("futures_position_limit_krw")), 2),
            "funding_rate": signal.get("funding_rate"),
            "entry_edge_bucket": get_entry_edge_bucket(safe_float(signal.get("real_edge"))),
            "edge_ge_2": safe_float(signal.get("real_edge")) >= 2.0,
            "edge_ge_3": safe_float(signal.get("real_edge")) >= 3.0,
            "edge_ge_4": safe_float(signal.get("real_edge")) >= 4.0,
            "edge_ge_5": safe_float(signal.get("real_edge")) >= 5.0,
            "status": status,
            "reason": str(reason or "")[:2000],
            "real_order": REAL_ORDER_ENABLED,
        }
        _csv_append(PAPER_ATTEMPTS_CSV, fieldnames, row)
        print(f"[자동진입 시도기록] {row['coin']} {row['domestic']}->{row['foreign']} / {status} / {str(reason)[:160]}")
    except Exception as e:
        print("[자동진입 시도기록 실패]", e)


def send_auto_entry_attempt_dm(user_id: str, signal: Dict[str, Any], title: str, detail: str, amount_krw: int = 0) -> None:
    """자동진입 성공/미진입 사유를 유저 개인방에 남긴다."""
    if not AUTO_ENTRY_SEND_DM_RESULT:
        return
    try:
        funding = signal.get("funding_rate")
        funding_text = "조회불가" if funding is None else f"{safe_float(funding):+.4f}%"
        msg = f"""{title}

코인: {signal.get('coin')}
경로: {signal.get('domestic')} ↔ {signal.get('foreign')}

감지 실제엣지: {safe_float(signal.get('real_edge')):+.2f}%
예상 구간: {safe_float(signal.get('expected_profit_min')):+.2f}%~{safe_float(signal.get('expected_profit_max')):+.2f}%
최소 유지엣지: {safe_float(signal.get('min_retain_edge_percent'), MIN_RETAIN_EDGE_PERCENT):+.2f}%
허용 슬리피지: {safe_float(signal.get('allowed_slippage_percent')):.2f}%
자동진입 금액: {fmt_man_krw(amount_krw or AUTO_ENTRY_DEFAULT_KRW)}

국내 최종벽: {fmt_man_krw(signal.get('spot_wall_krw'))}
해외 최종벽: {fmt_man_krw(signal.get('futures_wall_krw'))}
거래소MAX: {fmt_man_krw(signal.get('futures_position_limit_krw'))}
펀딩: {funding_text}

{detail}

🕒 {now_str()}
"""
        telegram_send_private(str(user_id), msg)
    except Exception as e:
        print("[자동진입 미진입DM 실패]", e)


def paper_record_entry(pos_id: str, user_id: str, signal: Dict[str, Any], amount_krw: int) -> None:
    """AUTO 정지 버튼으로 진입 등록된 순간 가상진입 기록."""
    if not PAPER_TRADING_ENABLED:
        print(f"[실전가상 기록 SKIP] PAPER_TRADING_ENABLED=False / {pos_id}")
        return

    _ensure_paper_data_dir()
    print(f"[실전가상 기록 준비] dir={PAPER_DATA_DIR} / entries={PAPER_ENTRIES_CSV}")

    fieldnames = [
        "event_time", "pos_id", "signal_id", "user_id",
        "coin", "domestic", "foreign", "domestic_market", "foreign_market",
        "entry_krw", "domestic_entry_krw", "foreign_entry_krw", "foreign_margin_krw", "futures_leverage",
        "domestic_actual_fill_krw", "foreign_actual_fill_krw", "fill_diff_krw", "fill_diff_percent",
        "entry_edge", "allowed_slippage_percent", "min_retain_edge_percent", "btc_gap", "coin_gap",
        "expected_profit_min", "expected_profit_max",
        "spot_wall_krw", "futures_wall_krw", "futures_position_limit_krw",
        "funding_rate", "entry_edge_bucket", "edge_ge_2", "edge_ge_3", "edge_ge_4", "edge_ge_5", "real_order", "status"
    ]
    domestic_entry_krw, foreign_entry_krw, final_entry_krw = calc_domestic_foreign_entry_amounts(signal, amount_krw)

    row = {
        "event_time": now_str(),
        "pos_id": pos_id,
        "signal_id": signal.get("signal_id"),
        "user_id": user_id,
        "coin": signal.get("coin"),
        "domestic": signal.get("domestic"),
        "foreign": signal.get("foreign"),
        "domestic_market": signal.get("domestic_market"),
        "foreign_market": signal.get("foreign_market"),
        "entry_krw": int(final_entry_krw),
        "domestic_entry_krw": int(domestic_entry_krw),
        "foreign_entry_krw": int(foreign_entry_krw),
        # V9.2: 실제 주문 연결 전에는 요청금액=체결금액으로 저장. 실주문 연결 시 실제 fill 값으로 교체.
        "domestic_actual_fill_krw": int(safe_float(signal.get("domestic_actual_fill_krw"), domestic_entry_krw)),
        "foreign_actual_fill_krw": int(safe_float(signal.get("foreign_actual_fill_krw"), foreign_entry_krw)),
        "fill_diff_krw": int(safe_float(signal.get("domestic_actual_fill_krw"), domestic_entry_krw) - safe_float(signal.get("foreign_actual_fill_krw"), foreign_entry_krw)),
        "fill_diff_percent": round(((safe_float(signal.get("domestic_actual_fill_krw"), domestic_entry_krw) - safe_float(signal.get("foreign_actual_fill_krw"), foreign_entry_krw)) / max(1.0, safe_float(signal.get("domestic_actual_fill_krw"), domestic_entry_krw))) * 100.0, 4),
        "entry_edge": round(safe_float(signal.get("real_edge")), 4),
        "allowed_slippage_percent": round(safe_float(signal.get("allowed_slippage_percent")), 4),
        "min_retain_edge_percent": round(safe_float(signal.get("min_retain_edge_percent"), MIN_RETAIN_EDGE_PERCENT), 4),
        "btc_gap": round(safe_float(signal.get("btc_gap")), 4),
        "coin_gap": round(safe_float(signal.get("coin_gap")), 4),
        "expected_profit_min": round(safe_float(signal.get("expected_profit_min")), 4),
        "expected_profit_max": round(safe_float(signal.get("expected_profit_max")), 4),
        "spot_wall_krw": round(safe_float(signal.get("spot_wall_krw")), 2),
        "futures_wall_krw": round(safe_float(signal.get("futures_wall_krw")), 2),
        "futures_position_limit_krw": round(safe_float(signal.get("futures_position_limit_krw")), 2),
        "funding_rate": signal.get("funding_rate"),
        "entry_edge_bucket": get_entry_edge_bucket(safe_float(signal.get("real_edge"))),
        "edge_ge_2": safe_float(signal.get("real_edge")) >= 2.0,
        "edge_ge_3": safe_float(signal.get("real_edge")) >= 3.0,
        "edge_ge_4": safe_float(signal.get("real_edge")) >= 4.0,
        "edge_ge_5": safe_float(signal.get("real_edge")) >= 5.0,
        "real_order": REAL_ORDER_ENABLED,
        "status": "VIRTUAL_OPEN" if not REAL_ORDER_ENABLED else "REAL_OPEN",
    }
    _csv_append(PAPER_ENTRIES_CSV, fieldnames, row)
    print(
        f"[실전가상 기록] 진입 저장 {pos_id} / {row['coin']} / {row['foreign']} "
        f"/ 국내 {fmt_man_krw(domestic_entry_krw)} / 해외 {fmt_man_krw(foreign_entry_krw)}"
    )


def _paper_update_daily_stats(result_row: Dict[str, Any]) -> None:
    _ensure_paper_data_dir()
    today = datetime.now().strftime("%Y-%m-%d")
    stats = _read_json(PAPER_DAILY_STATS_JSON, {})
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

    day["closed_count"] = int(day.get("closed_count", 0)) + 1
    day["total_entry_krw"] = safe_float(day.get("total_entry_krw")) + entry_krw
    day["total_pnl_krw"] = safe_float(day.get("total_pnl_krw")) + pnl_krw

    if "TAKE" in status or "TP" in status or "PROFIT" in status or pnl_krw > 0:
        day["tp_count"] = int(day.get("tp_count", 0)) + 1
    elif "STOP" in status or "SL" in status or pnl_krw < 0:
        day["sl_count"] = int(day.get("sl_count", 0)) + 1
    else:
        day["warn_or_other_count"] = int(day.get("warn_or_other_count", 0)) + 1

    # 누적 평균 수익률은 단순 평균으로 관리
    old_n = max(0, int(day.get("closed_count", 1)) - 1)
    old_avg = safe_float(day.get("avg_pnl_percent"))
    n = int(day.get("closed_count", 1))
    day["avg_pnl_percent"] = round(((old_avg * old_n) + pnl_percent) / max(1, n), 4)

    # V9.1: 2% / 3% / 4% / 5% 이상 엣지 레벨별 통계 누적
    update_edge_tier_stats(day, result_row)

    ex = day.setdefault("by_exchange", {}).setdefault(foreign, {
        "closed_count": 0,
        "tp_count": 0,
        "sl_count": 0,
        "total_entry_krw": 0,
        "total_pnl_krw": 0.0,
        "avg_pnl_percent": 0.0,
    })
    ex["closed_count"] = int(ex.get("closed_count", 0)) + 1
    ex["total_entry_krw"] = safe_float(ex.get("total_entry_krw")) + entry_krw
    ex["total_pnl_krw"] = safe_float(ex.get("total_pnl_krw")) + pnl_krw
    if pnl_krw > 0:
        ex["tp_count"] = int(ex.get("tp_count", 0)) + 1
    elif pnl_krw < 0:
        ex["sl_count"] = int(ex.get("sl_count", 0)) + 1
    old_ex_n = max(0, int(ex.get("closed_count", 1)) - 1)
    old_ex_avg = safe_float(ex.get("avg_pnl_percent"))
    ex_n = int(ex.get("closed_count", 1))
    ex["avg_pnl_percent"] = round(((old_ex_avg * old_ex_n) + pnl_percent) / max(1, ex_n), 4)

    _write_json_atomic(PAPER_DAILY_STATS_JSON, stats)


def calc_holding_seconds(opened_at: str, closed_at: str) -> int:
    try:
        a = datetime.strptime(str(opened_at), "%Y-%m-%d %H:%M:%S")
        b = datetime.strptime(str(closed_at), "%Y-%m-%d %H:%M:%S")
        return max(0, int((b - a).total_seconds()))
    except Exception:
        return 0


def paper_record_close(pos_id: str, pos: Dict[str, Any], status: str, current_edge: float, reason: str) -> None:
    """가상/실전 포지션 종료 결과 저장."""
    if not PAPER_TRADING_ENABLED:
        return

    entry_edge = safe_float(pos.get("entry_edge"))
    close_edge = safe_float(current_edge)
    entry_krw = int(safe_float(pos.get("amount_krw")))
    domestic_entry_krw = int(safe_float(pos.get("domestic_entry_krw"), entry_krw))
    foreign_entry_krw = int(safe_float(pos.get("foreign_entry_krw"), entry_krw))
    foreign_margin_krw = int(safe_float(pos.get("foreign_margin_krw"), calc_required_foreign_margin_krw(entry_krw)))

    # 양방 총수익은 진입 후 실제엣지가 줄어들수록 플러스.
    # V9.3.1 TEST_CAP_FEE: 펀딩비는 제외하고 국내/해외 왕복 수수료 예상치를 차감한 순손익으로 기록한다.
    gross_pnl_percent = entry_edge - close_edge
    gross_pnl_krw = entry_krw * gross_pnl_percent / 100.0
    fee_percent = calc_roundtrip_fee_percent() if TEST_CAP_FEE_MODE else 0.0
    fee_krw = entry_krw * fee_percent / 100.0
    funding_pnl_krw = 0.0
    pnl_percent = gross_pnl_percent - fee_percent
    pnl_krw = gross_pnl_krw - fee_krw + funding_pnl_krw

    opened_at = str(pos.get("opened_at") or "")
    closed_at = now_str()

    fieldnames = [
        "closed_at", "opened_at", "pos_id", "signal_id", "user_id",
        "coin", "domestic", "foreign", "domestic_market", "foreign_market",
        "entry_krw", "domestic_entry_krw", "foreign_entry_krw", "foreign_margin_krw", "futures_leverage",
        "domestic_actual_fill_krw", "foreign_actual_fill_krw", "fill_diff_krw", "fill_diff_percent",
        "entry_edge", "close_edge", "gross_pnl_percent", "gross_pnl_krw", "fee_percent", "fee_krw", "funding_pnl_krw", "entry_edge_bucket", "edge_ge_2", "edge_ge_3", "edge_ge_4", "edge_ge_5",
        "holding_sec", "pnl_percent", "pnl_krw", "status", "reason", "real_order"
    ]
    row = {
        "closed_at": closed_at,
        "opened_at": opened_at,
        "pos_id": pos_id,
        "signal_id": pos.get("signal_id"),
        "user_id": pos.get("user_id"),
        "coin": pos.get("coin"),
        "domestic": pos.get("domestic"),
        "foreign": pos.get("foreign"),
        "domestic_market": pos.get("domestic_market"),
        "foreign_market": pos.get("foreign_market"),
        "entry_krw": entry_krw,
        "domestic_entry_krw": domestic_entry_krw,
        "foreign_entry_krw": foreign_entry_krw,
        "foreign_margin_krw": foreign_margin_krw,
        "futures_leverage": safe_float(pos.get("futures_leverage"), PAPER_FUTURES_LEVERAGE),
        "entry_edge": round(entry_edge, 4),
        "close_edge": round(close_edge, 4),
        "gross_pnl_percent": round(gross_pnl_percent, 4),
        "gross_pnl_krw": round(gross_pnl_krw, 2),
        "fee_percent": round(fee_percent, 4),
        "fee_krw": round(fee_krw, 2),
        "funding_pnl_krw": round(funding_pnl_krw, 2),
        "entry_edge_bucket": get_entry_edge_bucket(entry_edge),
        "edge_ge_2": entry_edge >= 2.0,
        "edge_ge_3": entry_edge >= 3.0,
        "edge_ge_4": entry_edge >= 4.0,
        "edge_ge_5": entry_edge >= 5.0,
        "holding_sec": calc_holding_seconds(opened_at, closed_at),
        "pnl_percent": round(pnl_percent, 4),
        "pnl_krw": round(pnl_krw, 2),
        "status": status,
        "reason": reason,
        "real_order": pos.get("real_order", REAL_ORDER_ENABLED),
    }
    _csv_append(PAPER_RESULTS_CSV, fieldnames, row)
    _paper_update_daily_stats(row)
    print(
        f"[실전가상 기록] 결과 저장 {pos_id} / {row['coin']} / {row['foreign']} "
        f"/ 순수익 {row['pnl_percent']:+.2f}% / {fmt_man_krw(row['pnl_krw'])} "
        f"(수수료 {row.get('fee_percent', 0):.2f}%)"
    )




# ============================================================
# V9.3 저장 전용 워커 큐 모드
# - 스캔/청산 루프에서는 CSV/JSON을 직접 저장하지 않고 storage_queue.jsonl에 요청만 남긴다.
# - kedge_storage_worker_v93.py 1개가 실제 paper_entries/trade_results/daily_stats/api_speed_log 저장을 담당한다.
# - 목적: 4파일 동시 CSV 저장으로 인한 속도 저하/로그 도배/파일 충돌 방지.
# ============================================================
STORAGE_QUEUE_ENABLED = os.getenv("STORAGE_QUEUE_ENABLED", "true").lower() == "true"
STORAGE_QUEUE_PATH = os.path.join(PAPER_DATA_DIR, "storage_queue.jsonl")
STORAGE_QUEUE_VERBOSE = os.getenv("STORAGE_QUEUE_VERBOSE", "false").lower() == "true"

# 원본 함수 보관: 저장 워커를 끄고 단독 실행할 때만 직접 저장에 사용
_csv_append_direct = _csv_append
_paper_update_daily_stats_direct = _paper_update_daily_stats

_STORAGE_QUEUE_LOCK = threading.Lock()

def _storage_enqueue(op: str, payload: Dict[str, Any]) -> None:
    """저장 요청을 JSONL 큐에 남긴다. 각 스캔봇은 여기까지만 하고 즉시 다음 작업으로 넘어간다."""
    if not STORAGE_QUEUE_ENABLED:
        return
    try:
        _ensure_paper_data_dir()
        event = {
            "queued_at": now_str(),
            "op": op,
            "source_file": os.path.basename(__file__),
            "payload": payload,
        }
        line = json.dumps(event, ensure_ascii=False, default=str)
        # 프로세스별 append는 짧은 라인 기준 Windows에서도 실사용상 충분히 안정적.
        # 같은 프로세스 내 thread 충돌만 lock으로 방지.
        with _STORAGE_QUEUE_LOCK:
            with open(STORAGE_QUEUE_PATH, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        if STORAGE_QUEUE_VERBOSE:
            print(f"[저장큐 등록] {op}")
    except Exception as e:
        # 큐 등록 자체가 실패하면 데이터 유실 방지를 위해 직접 저장으로 fallback
        print(f"[저장큐 실패→직접저장 fallback] {op} / {e}")
        if op == "csv_append":
            p = payload
            _csv_append_direct(p.get("path", ""), p.get("fieldnames", []), p.get("row", {}))
        elif op == "daily_stats_update":
            _paper_update_daily_stats_direct(payload.get("result_row", {}))


def _csv_append(path: str, fieldnames: List[str], row: Dict[str, Any]) -> None:
    """V9.3: 저장 워커 큐 방식. STORAGE_QUEUE_ENABLED=false면 기존처럼 직접 저장."""
    if STORAGE_QUEUE_ENABLED:
        _storage_enqueue("csv_append", {
            "path": path,
            "fieldnames": fieldnames,
            "row": row,
        })
        return
    return _csv_append_direct(path, fieldnames, row)


def _paper_update_daily_stats(result_row: Dict[str, Any]) -> None:
    """V9.3: daily_stats.json 갱신도 저장 워커에서 처리."""
    if STORAGE_QUEUE_ENABLED:
        _storage_enqueue("daily_stats_update", {"result_row": result_row})
        return
    return _paper_update_daily_stats_direct(result_row)


# 거래소별/코인별 선물 최대 포지션 수동 보정표.
# 실제 API에서 못 가져오는 거래소/코인은 여기에 넣으면 가장 안전함.
# 예: FUTURES_MAX_POSITION_USDT_OVERRIDES = {"GATE": {"EDEN": 800}, "MEXC": {"ABC": 500}}
FUTURES_MAX_POSITION_USDT_OVERRIDES: Dict[str, Dict[str, float]] = {
    "MEXC": {},
    "GATE": {},
    "BITGET": {},
    "BINGX": {},
}

# API 조회 실패 시 거래소 기본 안전상한. 너무 크게 잡지 말고 보수적으로.
DEFAULT_FUTURES_MAX_POSITION_USDT_BY_EXCHANGE: Dict[str, float] = {
    "MEXC": 1_000.0,
    "GATE": 1_000.0,
    "BITGET": 1_000.0,
    "BINGX": 1_000.0,
}




def auto_git_push() -> None:
    """
    홈페이지 data/signals.json, data/stats.json 갱신 후 GitHub 자동 업로드.
    BASE_DIR 기준으로 git add / commit / push 실행.
    """
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

        if not status.stdout.strip():
            print("[홈페이지 자동 PUSH] 변경사항 없음")
            return

        subprocess.run(
            ["git", "add", "data/signals.json", "data/stats.json"],
            cwd=BASE_DIR,
            timeout=30,
            check=False,
        )

        commit_msg = f"auto live update {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        commit = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        combined = (commit.stdout + commit.stderr).lower()
        if commit.returncode != 0 and "nothing to commit" in combined:
            print("[홈페이지 자동 PUSH] 커밋할 변경사항 없음")
            return

        push = subprocess.run(
            ["git", "push"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )

        if push.returncode == 0:
            print("[홈페이지 자동 PUSH 완료]")
        else:
            print("[홈페이지 자동 PUSH 실패]", (push.stdout + push.stderr)[-500:])

    except Exception as e:
        print("[홈페이지 자동 PUSH 예외]", e)



# ============================================================
# 해외 거래소
# ============================================================

# 국내 현물 -> 해외 선물 전용 속도 모드
# 해외 현물은 심볼 매칭/계산에 필요 없으므로 로딩하지 않음.
SPOT_EXCHANGES = []

# 홈페이지 레퍼럴 연결 거래소만 사용
# 알림 품질/전환율을 위해 Binance / OKX / Bybit는 기본 제외
# 4파일 분리 속도 모드: 이 파일은 BITHUMB -> BITGET 만 검사
FUTURES_EXCHANGES = [
    ("BITGET", "bitget"),
]

CALLBACK_FUTURES_EXCHANGES = [
    ("MEXC", "mexc"),
    ("GATE", "gateio"),
    ("BITGET", "bitget"),
    ("BINGX", "bingx"),
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


def get_btc_baseline_for_source(
    btc_baseline_map: Dict[Tuple[str, str], float],
    source: str,
    future_ex_name: str,
) -> Tuple[Optional[float], str]:
    """
    국내 거래소별 BTC 기준 프리미엄 조회.
    업비트 BTC 기준이 비어 있으면 빗썸/코인원 기준으로 대체한다.
    return = (btc_basis, used_source)
    """
    source = str(source or "").upper()

    direct = btc_baseline_map.get((source, future_ex_name))
    if direct is not None:
        return direct, source

    # 업비트 BTC 기준이 수집 실패하는 경우가 있어, 국내 대표 BTC 기준으로 대체
    fallback_sources = []
    if source == "UPBIT":
        fallback_sources = ["BITHUMB", "COINONE"]
    else:
        fallback_sources = ["UPBIT", "BITHUMB", "COINONE"]

    for alt in fallback_sources:
        if alt == source:
            continue
        v = btc_baseline_map.get((alt, future_ex_name))
        if v is not None:
            return v, alt

    return None, ""


def fmt_krw(v: float) -> str:
    return f"{v:,.0f} KRW"


def fmt_usdt(v: float) -> str:
    return f"{v:,.2f} USDT"


def format_funding_rate(v: Optional[float]) -> str:
    if v is None:
        return "조회불가"
    return f"{v:+.4f}%"


def cooldown_ok(key: str) -> bool:
    t = time.time()
    old = last_alert_at.get(key, 0)
    if t - old >= ALERT_COOLDOWN_SEC:
        last_alert_at[key] = t
        return True
    return False


def build_support_message(
    event_type: str,
    symbol: str,
    locked: Dict[str, Any],
    current_edge: float,
    funding_rate_percent: Optional[float] = None,
) -> str:
    """진입 이후 변화가 생겼을 때만 보내는 VIP 이벤트형 서포트 메시지."""
    entry_edge = safe_float(locked.get("entry_percent"))
    stop_edge = safe_float(locked.get("stop_edge"))
    spot_source = locked.get("spot_source", "")
    future_source = locked.get("future_source", "")
    recovered = entry_edge - current_edge

    funding_text = "조회불가"
    if funding_rate_percent is not None:
        funding_text = f"{funding_rate_percent:+.4f}%"

    if event_type == "TAKE_PROFIT":
        title = "✅ 양방 종료 / 회귀 완료"
        desc = "예상 수익구간이 목표 구간까지 회귀했습니다."
        action = "청산 / 종료 검토"
    elif event_type == "STOP_LOSS":
        title = "⚠️ 양방 손절 기준 도달"
        desc = "진입 이후 남은 차익 구간이 손절 기준까지 확대되었습니다."
        action = "부분정리 또는 손절 검토"
    elif event_type == "FUNDING_WARN":
        title = "⚠️ 양방 펀딩비 주의"
        desc = "숏 포지션 보유 비용이 커질 수 있는 구간입니다."
        action = "펀딩 확인 후 유지/정리 판단"
    else:
        title = "📌 양방 서포트"
        desc = "상태 변화가 감지되었습니다."
        action = "확인"

    if event_type == "TAKE_PROFIT":
        return f"""{title}

코인: {symbol}

경로:
{spot_source} 현물
+
{future_source} 선물숏

진입 예상수익:
{entry_edge:+.2f}%

현재 남은 차익:
{current_edge:+.2f}%

회귀폭:
{recovered:.2f}%

청산 목표:
{POSITION_RELEASE_PERCENT:+.2f}% 이하

손절 기준:
{stop_edge:+.2f}% 이상

현재 펀딩비:
{funding_text}

권장 레버리지:
{RECOMMENDED_LEVERAGE_TEXT}

━━━━━━━━━━━━━━

결과

{desc}

회귀 완료폭:
{recovered:.2f}%

권장:
{action}

🕒 {now_str()}
"""

    return f"""{title}

코인: {symbol}
경로: {spot_source} 현물 + {future_source} 선물숏

진입 예상수익: {entry_edge:+.2f}%
현재 남은 차익: {current_edge:+.2f}%
청산 목표: {POSITION_RELEASE_PERCENT:+.2f}% 이하
손절 기준: {stop_edge:+.2f}% 이상

현재 펀딩비: {funding_text}
권장 레버리지: {RECOMMENDED_LEVERAGE_TEXT}

상태: {desc}
권장: {action}

🕒 {now_str()}
"""


def make_active_lock_key(symbol: str, spot_source: str = "", future_source: str = "") -> str:
    """같은 코인이라도 국내거래소+해외선물 조합별로 다른 기회로 본다."""
    return f"{normalize_symbol(symbol)}_{str(spot_source or '').upper()}_{str(future_source or '').upper()}"


def active_lock_check(symbol: str, spot_source: str, future_source: str, current_percent: float, funding_rate_percent: Optional[float] = None) -> bool:
    """
    알림 발생 = 해당 조합에 진입했다고 가정.
    같은 코인이라도 UPBIT/GATE, BITHUMB/GATE, UPBIT/MEXC는 따로 추적한다.
    """
    symbol = normalize_symbol(symbol)
    lock_key = make_active_lock_key(symbol, spot_source, future_source)
    locked = active_symbol_locks.get(lock_key)
    if not locked:
        return False

    entry_edge = safe_float(locked.get("entry_percent"))
    stop_edge = safe_float(locked.get("stop_edge"), entry_edge + STOP_EDGE_ADD_PERCENT)

    if current_percent <= POSITION_RELEASE_PERCENT:
        msg = build_support_message("TAKE_PROFIT", symbol, locked, current_percent, funding_rate_percent)
        print(msg)
        telegram_send(msg)
        active_symbol_locks.pop(lock_key, None)
        return False

    if current_percent >= stop_edge:
        msg = build_support_message("STOP_LOSS", symbol, locked, current_percent, funding_rate_percent)
        print(msg)
        telegram_send(msg)
        active_symbol_locks.pop(lock_key, None)
        return False

    if (
        funding_rate_percent is not None
        and funding_rate_percent >= FUNDING_SUPPORT_WARN_PERCENT
        and not locked.get("funding_warn_sent")
    ):
        msg = build_support_message("FUNDING_WARN", symbol, locked, current_percent, funding_rate_percent)
        print(msg)
        telegram_send(msg)
        locked["funding_warn_sent"] = True

    print(
        f"[진입가정 잠금중] {lock_key} "
        f"현재={current_percent:.2f}% / 청산={POSITION_RELEASE_PERCENT:.2f}% "
        f"/ 손절={stop_edge:.2f}% / 진입={entry_edge:.2f}%"
    )
    return True


def mark_active_lock(symbol: str, current_percent: float, spot_source: str, future_source: str) -> None:
    """알림을 보낸 조합은 청산/손절 이벤트 전까지 재알림 금지."""
    symbol = normalize_symbol(symbol)
    lock_key = make_active_lock_key(symbol, spot_source, future_source)
    active_symbol_locks[lock_key] = {
        "entry_percent": current_percent,
        "stop_edge": current_percent + STOP_EDGE_ADD_PERCENT,
        "spot_source": spot_source,
        "future_source": future_source,
        "locked_at": time.time(),
        "funding_warn_sent": False,
    }


def symbol_cooldown_ok(symbol: str, spot_source: str = "", future_source: str = "") -> bool:
    """같은 조합만 쿨다운. 빗썸 알림이 떠도 업비트 알림은 따로 살아난다."""
    t = time.time()
    cooldown_key = make_active_lock_key(symbol, spot_source, future_source)
    old = last_symbol_alert_at.get(cooldown_key, 0)
    if t - old >= SYMBOL_ALERT_COOLDOWN_SEC:
        last_symbol_alert_at[cooldown_key] = t
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



def _telegram_send_with_keyboard(token: str, chat_id: str, text: str, keyboard: List[List[Dict[str, str]]], label: str) -> bool:
    """인라인 버튼 포함 텔레그램 전송."""
    if not token or not chat_id:
        print(f"[{label} 텔레그램 미설정]\n", text)
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
            "reply_markup": json.dumps({"inline_keyboard": keyboard}, ensure_ascii=False),
        }
        r = session.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print(f"[{label} 버튼 텔레그램 전송 성공]")
            return True
        print(f"[{label} 버튼 텔레그램 전송 실패]", r.status_code, r.text[:300])
        return False
    except Exception as e:
        print(f"[{label} 버튼 텔레그램 예외]", e)
        return False


def telegram_answer_callback(callback_query_id: str, text: str, alert: bool = False) -> None:
    try:
        url = f"https://api.telegram.org/bot{SEMI_AUTO_BOT_TOKEN}/answerCallbackQuery"
        session.post(url, data={
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": "true" if alert else "false",
        }, timeout=5)
    except Exception:
        pass


def telegram_edit_message(chat_id: str, message_id: int, text: str, keyboard: List[List[Dict[str, str]]]) -> None:
    try:
        url = f"https://api.telegram.org/bot{SEMI_AUTO_BOT_TOKEN}/editMessageText"
        session.post(url, data={
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True,
            "reply_markup": json.dumps({"inline_keyboard": keyboard}, ensure_ascii=False),
        }, timeout=8)
    except Exception as e:
        print("[반자동 메시지 수정 실패]", e)


def _mask_token(token: str) -> str:
    token = str(token or "")
    if len(token) <= 16:
        return token
    return token[:10] + "..." + token[-6:]


def _telegram_get_me(token: str, label: str = "BOT") -> str:
    """현재 전송에 쓰는 봇이 어떤 봇인지 콘솔에 찍어서 토큰 불일치를 잡는다."""
    if not token:
        print(f"[{label} getMe] 토큰 없음")
        return ""
    try:
        url = f"https://api.telegram.org/bot{token}/getMe"
        r = session.get(url, timeout=8)
        print(f"[{label} getMe]", r.status_code, r.text[:300])
        if r.status_code == 200:
            data = r.json()
            result = data.get("result") or {}
            return str(result.get("username") or result.get("first_name") or "")
    except Exception as e:
        print(f"[{label} getMe 예외]", e)
    return ""


def telegram_send_private(chat_id: str, text: str) -> bool:
    """승인회원 개인 DM 전송.

    핵심 수정:
    - 기본 DM 토큰을 VIP 메인봇 TELEGRAM_BOT_TOKEN으로 고정
    - KEDGE_USER_DM_BOT_TOKEN을 따로 넣은 경우에만 별도 봇 사용
    - 403 발생 시 실제 사용한 봇 getMe 결과를 찍어서 /start 한 봇과 같은지 확인
    - 혹시 별도봇 실패 시 메인봇으로 1회 fallback
    """
    chat_id = str(chat_id or "").strip()

    # 테스트 강제 chat_id: Supabase의 tg_chat_id가 예전 봇/다른 계정으로 저장된 경우
    # 새 개인DM 봇 테스트가 바로 되도록 강제 전송한다.
    if FORCE_TEST_USER_DM_CHAT_ID:
        print(f"[승인회원DM 테스트강제] DB chat_id={chat_id} -> FORCE chat_id={FORCE_TEST_USER_DM_CHAT_ID}")
        chat_id = FORCE_TEST_USER_DM_CHAT_ID

    if not chat_id:
        print("[승인회원DM] chat_id 없음")
        return False

    tokens = []
    labels = []

    # 1순위: 현재 반자동 DM 토큰. 기본값은 VIP 메인봇.
    if SEMI_AUTO_BOT_TOKEN:
        tokens.append(SEMI_AUTO_BOT_TOKEN)
        labels.append("승인회원DM")

    # 2순위 fallback: VIP 메인봇. 중복 토큰이면 추가하지 않음.
    if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN not in tokens:
        tokens.append(TELEGRAM_BOT_TOKEN)
        labels.append("승인회원DM-VIPFallback")

    print("[승인회원DM 설정]", {
        "chat_id": chat_id,
        "semi_auto_token": _mask_token(SEMI_AUTO_BOT_TOKEN),
        "vip_token": _mask_token(TELEGRAM_BOT_TOKEN),
        "same_token": SEMI_AUTO_BOT_TOKEN == TELEGRAM_BOT_TOKEN,
        "force_test_chat_id": FORCE_TEST_USER_DM_CHAT_ID,
    })

    for token, label in zip(tokens, labels):
        _telegram_get_me(token, label)
        ok = _telegram_send_to(token, chat_id, text, label)
        if ok:
            return True

    return False


def fmt_man_krw(v: float) -> str:
    """한눈에 보기 좋은 만원 단위."""
    v = safe_float(v)
    if v >= 100_000_000:
        return f"{v / 100_000_000:.2f}억"
    if v >= 10_000:
        n = v / 10_000
        if abs(n - round(n)) < 0.01:
            return f"{int(round(n))}만"
        return f"{n:.1f}만"
    return f"{v:,.0f}원"


def calc_expected_profit_range(edge_percent: float) -> Tuple[float, float]:
    hi = safe_float(edge_percent)
    lo = max(0.0, hi - EXPECTED_PROFIT_DISCOUNT_PERCENT)
    return lo, hi


def calc_domestic_foreign_entry_amounts(signal: Dict[str, Any], amount_krw: int) -> Tuple[int, int, int]:
    """국내/해외 실제 진입 기준 금액 계산.

    V9.3.1 테스트 모드:
    - domestic_entry_krw: 국내 현물 진입금액
    - foreign_entry_krw: 해외 선물 명목 진입금액(국내와 동일 노출)
    - foreign_margin_krw는 별도 필드로 amount/레버리지 저장
    """
    amount = int(max(0, safe_float(amount_krw)))
    max_entry = int(max(0, safe_float(signal.get("max_entry_krw") or signal.get("final_entry_krw"))))
    remaining = int(max(0, safe_float(signal.get("remaining_entry_krw", max_entry))))

    candidates = [amount]
    if max_entry > 0:
        candidates.append(max_entry)
    if remaining > 0:
        candidates.append(remaining)

    final_entry = int(max(0, min(candidates))) if candidates else amount
    return final_entry, final_entry, final_entry


def make_signal_id(symbol: str, domestic: str, foreign: str) -> str:
    return f"{normalize_symbol(symbol)}_{domestic}_{foreign}_{int(time.time())}"


def supabase_headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def supabase_insert_signal(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """signals 테이블 저장. Supabase 환경변수가 없으면 스킵."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("[Supabase] 미설정 - signals 저장 스킵")
        return None
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_SIGNALS_TABLE}"
        r = session.post(url, headers=supabase_headers(), data=json.dumps(row, ensure_ascii=False), timeout=10)
        if r.status_code in (200, 201):
            data = r.json()
            if isinstance(data, list) and data:
                print("[Supabase] signals 저장 완료")
                return data[0]
            print("[Supabase] signals 저장 완료")
            return row
        print("[Supabase] signals 저장 실패", r.status_code, r.text[:300])
        return None
    except Exception as e:
        print("[Supabase] signals 저장 예외", e)
        return None


def get_member_chat_id(member: Dict[str, Any]) -> str:
    """Supabase 승인회원 row에서 텔레그램 chat_id를 안전하게 읽는다."""
    candidates = [
        SUPABASE_MEMBER_TELEGRAM_ID_COLUMN,
        "tg_chat_id",              # 실제 K-EDGE DB 컬럼
        "telegram_chat_id",
        "telegram_id",
        "telegram_user_id",
        "chat_id",
    ]
    for key in candidates:
        v = member.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def get_member_row_id(member: Dict[str, Any]) -> str:
    """회원 row 식별자. 없으면 chat_id로 대체."""
    return str(
        member.get("id")
        or member.get("request_id")
        or member.get("uid")
        or get_member_chat_id(member)
        or ""
    )


def supabase_get_approved_members_uncached() -> List[Dict[str, Any]]:
    """승인회원 DB 직접 조회. 일반 로직에서는 supabase_get_approved_members 캐시 함수를 사용."""
    print("[DM 설정 확인]", {"callback_poller": ENABLE_CALLBACK_POLLER, "state_path": SEMI_AUTO_STATE_PATH})
    print("[Supabase 설정]", {
        "url_set": bool(SUPABASE_URL),
        "key_set": bool(SUPABASE_SERVICE_KEY),
        "table": SUPABASE_MEMBERS_TABLE,
        "status_column": SUPABASE_MEMBER_STATUS_COLUMN,
        "status_value": SUPABASE_MEMBER_STATUS_VALUE,
        "chat_column": SUPABASE_MEMBER_TELEGRAM_ID_COLUMN,
    })

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("[Supabase] 미설정 - 승인회원 조회 스킵")
        print("[해결] CMD에서 set SUPABASE_URL=... / set SUPABASE_SERVICE_KEY=... 설정 후 같은 창에서 실행")
        return []
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_MEMBERS_TABLE}"
        params = {
            "select": "*",
            SUPABASE_MEMBER_STATUS_COLUMN: f"eq.{SUPABASE_MEMBER_STATUS_VALUE}",
        }
        print("[Supabase 조회]", url, params)
        r = session.get(url, headers=supabase_headers(), params=params, timeout=10)
        print("[Supabase 응답]", r.status_code, r.text[:500])
        if r.status_code == 200:
            rows = r.json()
            if isinstance(rows, list):
                print(f"[승인회원 조회 결과] {len(rows)}명")
                for row in rows[:5]:
                    print("[승인회원 row keys]", list(row.keys()))
                    print("[승인회원 chat_id 읽기]", get_member_chat_id(row))
                return rows
        print("[Supabase] 승인회원 조회 실패", r.status_code, r.text[:300])
        return []
    except Exception as e:
        print("[Supabase] 승인회원 조회 예외", e)
        return []


def supabase_get_approved_members(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """승인회원 캐시 조회.

    - 시작/최초 호출 시 DB 조회
    - 이후 5분 동안 메모리 캐시 사용
    - 신규 승인 반영은 최대 5분 내 반영
    """
    global _APPROVED_MEMBERS_CACHE, _APPROVED_MEMBERS_CACHE_AT
    now_ts = time.time()
    with _APPROVED_MEMBERS_CACHE_LOCK:
        if (
            not force_refresh
            and _APPROVED_MEMBERS_CACHE
            and now_ts - _APPROVED_MEMBERS_CACHE_AT < APPROVED_MEMBER_CACHE_TTL_SEC
        ):
            return list(_APPROVED_MEMBERS_CACHE)

        rows = supabase_get_approved_members_uncached()
        _APPROVED_MEMBERS_CACHE = rows if isinstance(rows, list) else []
        _APPROVED_MEMBERS_CACHE_AT = now_ts
        print(f"[승인회원 캐시 갱신] {len(_APPROVED_MEMBERS_CACHE)}명 / TTL {APPROVED_MEMBER_CACHE_TTL_SEC}s")
        return list(_APPROVED_MEMBERS_CACHE)




def _bool_from_any(v: Any, default: bool = False) -> bool:
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on", "enabled", "활성", "사용"):
        return True
    if s in ("0", "false", "no", "n", "off", "disabled", "비활성", "중지"):
        return False
    return default


def _setting_identity_keys(member: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    for k in ("user_id", "member_id", "request_id", "id", "uid", "telegram_id", "telegram_user_id", "tg_chat_id", "chat_id"):
        v = member.get(k)
        if v is not None and str(v).strip():
            keys.append(str(v).strip())
    chat_id = get_member_chat_id(member)
    if chat_id:
        keys.append(str(chat_id).strip())
    out: List[str] = []
    for x in keys:
        if x not in out:
            out.append(x)
    return out


def supabase_get_auto_settings_uncached() -> Dict[str, Dict[str, Any]]:
    """홈페이지 AUTO 설정 테이블을 읽어 user_id/tg_chat_id 기준으로 빠르게 찾을 수 있게 인덱싱."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY or not SUPABASE_AUTO_SETTINGS_TABLE:
        print("[auto_settings] Supabase 미설정 - 스킵")
        return {}
    try:
        url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{SUPABASE_AUTO_SETTINGS_TABLE}"
        r = session.get(url, headers=supabase_headers(), params={"select": "*"}, timeout=10)
        if r.status_code != 200:
            print("[auto_settings] 조회 실패", r.status_code, r.text[:300])
            return {}
        rows = r.json()
        if not isinstance(rows, list):
            return {}
        indexed: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            for k in ("user_id", "member_id", "request_id", "id", "uid", "telegram_id", "telegram_user_id", "tg_chat_id", "chat_id"):
                v = row.get(k)
                if v is not None and str(v).strip():
                    indexed[str(v).strip()] = row
        print(f"[auto_settings] 조회 완료 rows={len(rows)} / indexed={len(indexed)}")
        return indexed
    except Exception as e:
        print("[auto_settings] 조회 예외", e)
        return {}


def supabase_get_auto_settings(force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    global _AUTO_SETTINGS_CACHE, _AUTO_SETTINGS_CACHE_AT
    now_ts = time.time()
    with _AUTO_SETTINGS_CACHE_LOCK:
        if (not force_refresh) and _AUTO_SETTINGS_CACHE and now_ts - _AUTO_SETTINGS_CACHE_AT < AUTO_SETTINGS_CACHE_TTL_SEC:
            return dict(_AUTO_SETTINGS_CACHE)
        _AUTO_SETTINGS_CACHE = supabase_get_auto_settings_uncached()
        _AUTO_SETTINGS_CACHE_AT = now_ts
        return dict(_AUTO_SETTINGS_CACHE)


def get_auto_settings_for_member(member: Dict[str, Any]) -> Dict[str, Any]:
    settings_map = supabase_get_auto_settings()
    for key in _setting_identity_keys(member):
        row = settings_map.get(key)
        if isinstance(row, dict):
            return row
    return {}


def merge_member_auto_settings(member: Dict[str, Any]) -> Dict[str, Any]:
    """승인회원 row + auto_settings row 병합. auto_settings 값이 있으면 우선한다."""
    settings = get_auto_settings_for_member(member)
    merged = dict(member or {})
    if settings:
        merged.update(settings)
        merged["_auto_settings_found"] = True
    else:
        merged["_auto_settings_found"] = False
    return merged


def is_member_service_enabled(member: Dict[str, Any]) -> bool:
    # 기본값 True: 승인회원이면 알림 서비스는 켜진 것으로 본다.
    for k in ("service_enabled", "alarm_enabled", "alert_enabled", "alerts_enabled", "is_active"):
        if k in member:
            return _bool_from_any(member.get(k), True)
    return True


def is_member_auto_enabled(member: Dict[str, Any]) -> bool:
    # 기본값 False: 홈페이지에서 AUTO ON을 명시해야 자동진입한다.
    for k in ("auto_enabled", "auto_trading_enabled", "auto_trade_enabled", "auto_on"):
        if k in member:
            return _bool_from_any(member.get(k), False)
    return False


def get_member_capital_krw(member: Dict[str, Any]) -> int:
    for k in ("capital_krw", "operation_amount_krw", "operating_amount_krw", "total_capital_krw", "domestic_capital_krw"):
        v = member.get(k)
        if v is not None and safe_float(v) > 0:
            return int(safe_float(v))
    return int(PAPER_DOMESTIC_BASE_KRW)


def get_member_split_count(member: Dict[str, Any]) -> int:
    for k in ("split_count", "division_count", "entry_split_count", "max_entry_count"):
        v = member.get(k)
        if v is not None and safe_float(v) > 0:
            return max(1, int(safe_float(v)))
    return int(DOMESTIC_COMPOUND_DIVISOR)


def send_signal_alert_only_dm(tg_id: str, signal: Dict[str, Any], reason: str = "") -> None:
    msg = (
        "📡 K-EDGE AUTO 신호 감지\n\n"
        f"코인: {signal.get('coin')}\n"
        f"경로: {signal.get('domestic')} ↔ {signal.get('foreign')}\n"
        f"실제엣지: {safe_float(signal.get('real_edge')):+.2f}%\n"
        f"진입가능: {fmt_man_krw(signal.get('max_entry_krw'))}\n"
        f"남은가능: {fmt_man_krw(signal.get('remaining_entry_krw', signal.get('max_entry_krw')))}\n\n"
        "현재 AUTO 자동매매가 OFF라서 알림만 전송합니다.\n"
        "AUTO 설정에서 자동매매 ON으로 바꾸면 조건 통과 시 자동진입합니다."
    )
    if reason:
        msg += f"\n\n사유: {reason}"
    telegram_send_private(str(tg_id), msg)

def _semi_state_path_for_exchange(exchange_name: str) -> str:
    ex = str(exchange_name or "").upper()
    name_map = {
        "MEXC": "semi_auto_state_mexc.json",
        "GATE": "semi_auto_state_gate.json",
        "GATEIO": "semi_auto_state_gate.json",
        "BITGET": "semi_auto_state_bitget.json",
        "BINGX": "semi_auto_state_bitget.json",
    }
    return os.path.join(BASE_DIR, name_map.get(ex, os.path.basename(SEMI_AUTO_STATE_PATH)))


def _semi_state_known_paths() -> List[str]:
    paths = [
        SEMI_AUTO_STATE_PATH,
        os.path.join(BASE_DIR, "semi_auto_state_mexc.json"),
        os.path.join(BASE_DIR, "semi_auto_state_gate.json"),
        os.path.join(BASE_DIR, "semi_auto_state_bitget.json"),
        os.path.join(BASE_DIR, "semi_auto_state_bitget.json"),
    ]
    out = []
    for p in paths:
        if p not in out:
            out.append(p)
    return out


def _semi_state_path_from_signal_id(signal_id: str) -> str:
    s = str(signal_id or "").upper()
    for ex in ("MEXC", "GATE", "BITGET", "BINGX"):
        if f"_{ex}_" in s or s.endswith(f"_{ex}"):
            return _semi_state_path_for_exchange(ex)
    return SEMI_AUTO_STATE_PATH


def _read_state_file(path: str) -> Dict[str, Any]:
    state = _read_json(path, {"signals": {}, "users": {}, "positions": {}})
    if not isinstance(state, dict):
        state = {"signals": {}, "users": {}, "positions": {}}
    state.setdefault("signals", {})
    state.setdefault("users", {})
    state.setdefault("positions", {})
    return state


def _write_state_file(path: str, state: Dict[str, Any]) -> None:
    _write_json_atomic(path, state)


def _read_semi_state() -> Dict[str, Any]:
    return _read_state_file(SEMI_AUTO_STATE_PATH)


def _write_semi_state(state: Dict[str, Any]) -> None:
    _write_state_file(SEMI_AUTO_STATE_PATH, state)


def _read_signal_state_file(signal_id: str) -> Tuple[str, Dict[str, Any]]:
    preferred = _semi_state_path_from_signal_id(signal_id)
    paths = [preferred] + [p for p in _semi_state_known_paths() if p != preferred]
    for path in paths:
        state = _read_state_file(path)
        if signal_id in (state.get("signals") or {}):
            return path, state
    return preferred, _read_state_file(preferred)


def save_signal_state(signal_id: str, row: Dict[str, Any]) -> None:
    path = _semi_state_path_from_signal_id(signal_id)
    state = _read_state_file(path)
    row = dict(row or {})
    row.setdefault("used_entry_krw", 0)
    max_entry = int(safe_float(row.get("max_entry_krw") or row.get("final_entry_krw")))
    row.setdefault("remaining_entry_krw", max(0, max_entry - int(safe_float(row.get("used_entry_krw")))))
    state.setdefault("signals", {})[signal_id] = row
    _write_state_file(path, state)


def get_signal_state(signal_id: str) -> Optional[Dict[str, Any]]:
    _, state = _read_signal_state_file(signal_id)
    row = state.get("signals", {}).get(signal_id)
    return row if isinstance(row, dict) else None


def get_user_selected_amount(user_id: str, signal_id: str) -> int:
    _, state = _read_signal_state_file(signal_id)
    key = f"{user_id}:{signal_id}"
    return int(safe_float(state.get("users", {}).get(key, {}).get("selected_krw")))


def set_user_selected_amount(user_id: str, signal_id: str, amount_krw: int) -> int:
    # 4파일 분리 실행 안정화:
    # 어떤 파일의 callback poller가 버튼을 잡아도 signal_id의 거래소 상태파일에 저장한다.
    amount_krw = max(0, int(amount_krw))

    path, state = _read_signal_state_file(signal_id)
    key = f"{user_id}:{signal_id}"
    state.setdefault("users", {})[key] = {
        "selected_krw": amount_krw,
        "updated_at": now_str(),
    }
    _write_state_file(path, state)
    return amount_krw


def update_signal_usage(signal_id: str, add_used_krw: int = 0) -> Tuple[int, int]:
    """동시 진입 대비 signal 사용금액/남은금액 갱신.

    4파일 분리 실행에서는 callback을 어느 프로세스가 받아도
    signal_id에 포함된 거래소의 상태파일을 찾아 갱신한다.
    return = (used_entry_krw, remaining_entry_krw)
    """
    path, state = _read_signal_state_file(signal_id)
    sig = state.setdefault("signals", {}).get(signal_id) or {}
    max_entry = int(safe_float(sig.get("max_entry_krw") or sig.get("final_entry_krw")))
    used = int(safe_float(sig.get("used_entry_krw")))
    used = max(0, used + int(add_used_krw))
    remaining = max(0, max_entry - used)
    sig["used_entry_krw"] = used
    sig["remaining_entry_krw"] = remaining
    state["signals"][signal_id] = sig
    _write_state_file(path, state)
    return used, remaining


def get_signal_remaining_krw(signal_id: str) -> int:
    sig = get_signal_state(signal_id) or {}
    max_entry = int(safe_float(sig.get("max_entry_krw") or sig.get("final_entry_krw")))
    used = int(safe_float(sig.get("used_entry_krw")))
    remaining = sig.get("remaining_entry_krw")
    if remaining is None:
        return max(0, max_entry - used)
    return max(0, int(safe_float(remaining)))


def build_entry_keyboard(signal_id: str) -> List[List[Dict[str, str]]]:
    # 반자동 금액/진입 버튼 폐기. AUTO 전용에서는 정지/재시작만 제공한다.
    return build_stop_keyboard(signal_id)


def build_confirm_keyboard(signal_id: str, amount_krw: int) -> List[List[Dict[str, str]]]:
    return [
        [
            {"text": "최종 확인", "callback_data": f"CONFIRM|{signal_id}|{amount_krw}"},
            {"text": "취소", "callback_data": f"CANCEL|{signal_id}"},
        ],
        [
            {"text": "🛑 자동매매 정지", "callback_data": f"STOPREQ|{signal_id}"},
        ],
    ]


def build_member_dm_message(signal: Dict[str, Any], selected_krw: int = 0) -> str:
    funding = signal.get("funding_rate")
    funding_text = "조회불가" if funding is None else f"{safe_float(funding):+.4f}%"
    return f"""🤖 자동 양방 진입 후보

코인: {signal.get('coin')}
경로: {signal.get('domestic')} → {signal.get('foreign')}
모드: {AUTO_ENTRY_MODE_LABEL}
실제주문: OFF / 실전가상 저장: ON

━━━━━━━━━━━━━━

실제엣지: {safe_float(signal.get('real_edge')):+.2f}%
최소보존엣지: {safe_float(signal.get('min_retain_edge_percent'), MIN_RETAIN_EDGE_PERCENT):+.2f}%
허용슬리피지: {safe_float(signal.get('allowed_slippage_percent')):.2f}%

자동진입 목표금액: 홈페이지 AUTO 운용금액 / 분할수
테스트 자금: 국내 200만 / 해외 거래소별 50만 / 4배
수수료 차감: 국내왕복 {DOMESTIC_BUY_FEE_PERCENT + DOMESTIC_SELL_FEE_PERCENT:.2f}% + 해외왕복 {FUTURES_ENTRY_FEE_PERCENT + FUTURES_EXIT_FEE_PERCENT:.2f}% = 총 {calc_roundtrip_fee_percent():.2f}%
펀딩비: 제외
최종 진입가능: {fmt_man_krw(signal.get('max_entry_krw'))}
남은 가능금액: {fmt_man_krw(signal.get('remaining_entry_krw', signal.get('max_entry_krw')))}

국내 최종벽: {fmt_man_krw(signal.get('spot_wall_krw'))}
해외 최종벽: {fmt_man_krw(signal.get('futures_wall_krw'))}
거래소 MAX: {fmt_man_krw(signal.get('futures_position_limit_krw'))}
펀딩: {funding_text}

체결범위별 가능금액
{signal.get('slippage_tiers_text', '계산 없음')}

━━━━━━━━━━━━━━

상태: 조건 통과 시 버튼 없이 AUTO 설정 금액으로 가상진입 저장
저장: paper_trading_data/paper_entries.csv

※ 🛑 자동매매 정지를 누르면 신규 자동진입이 중단되고 현재 보유 포지션도 모두 종료 처리됩니다.
"""


def build_compact_vip_message_from_signal(signal: Dict[str, Any]) -> str:
    funding = signal.get("funding_rate")
    funding_text = "조회불가" if funding is None else f"{safe_float(funding):+.4f}%"
    return f"""⚖️ {signal.get('coin')}

예상 {safe_float(signal.get('expected_profit_min')):+.2f}%~{safe_float(signal.get('expected_profit_max')):+.2f}%

진입 {fmt_man_krw(signal.get('max_entry_krw'))}

유지엣지 {safe_float(signal.get('min_retain_edge_percent'), MIN_RETAIN_EDGE_PERCENT):+.2f}%
허용슬리피지 {safe_float(signal.get('allowed_slippage_percent')):.2f}%

체결범위
{signal.get('slippage_tiers_text', '계산 없음')}

국내최종벽 {fmt_man_krw(signal.get('spot_wall_krw'))}
해외최종벽 {fmt_man_krw(signal.get('futures_wall_krw'))}
거래소최대 {fmt_man_krw(signal.get('futures_position_limit_krw'))}

{signal.get('domestic')} ↔ {signal.get('foreign')}
펀딩 {funding_text}

※ 수수료 / 슬리피지 / 실제 체결가에 따라 달라질 수 있음

🕒 {now_str()}
"""


def build_compact_free_message_from_signal(signal: Dict[str, Any]) -> str:
    return f"""⚖️ 양방 후보

{signal.get('coin')}
{signal.get('domestic')} ↔ {signal.get('foreign')}

예상 {safe_float(signal.get('expected_profit_min')):+.2f}%~{safe_float(signal.get('expected_profit_max')):+.2f}%

🕒 {now_str()}
"""


def member_has_active_coin_position(member: Dict[str, Any], signal: Dict[str, Any]) -> bool:
    """해당 회원이 같은 코인의 ACTIVE 반자동 포지션을 이미 보유 중인지 확인.

    핵심 정책:
    - 코인별 유저 잠금이다.
    - EDEN 포지션을 보유한 유저에게는 EDEN 신규 진입 알림을 다시 보내지 않는다.
    - 다만 그 유저는 자동익절/경고/손절 등 포지션 관리 알림은 계속 받는다.
    - EDEN 미진입 유저에게는 다음 사이클 EDEN 알림도 정상 전송한다.
    """
    tg_id = str(get_member_chat_id(member) or "")
    coin = normalize_symbol(signal.get("coin") or "")
    if not tg_id or not coin:
        return False

    state = _read_semi_state()
    for _, pos in (state.get("positions") or {}).items():
        if not isinstance(pos, dict):
            continue
        if str(pos.get("status", "")).upper() != "ACTIVE":
            continue
        if str(pos.get("user_id") or "") != tg_id:
            continue
        if normalize_symbol(pos.get("coin") or "") == coin:
            return True
    return False


def notify_approved_members(signal: Dict[str, Any]) -> None:
    """V8.4: 완전 자동모드에서는 반자동 후보/금액 버튼 DM을 전송하지 않는다."""
    print(f"[반자동 후보DM 차단] {signal.get('coin')} / {signal.get('domestic')} -> {signal.get('foreign')} / 자동진입 전용")
    return


def fetch_futures_position_limit_krw(future_ex_name: str, fex: Any, market: str, symbol: str, usd_krw: float, best_bid: float) -> Tuple[float, str]:
    """
    선물 최대 포지션 한도 KRW.
    1순위: 수동 보정표
    2순위: ccxt market limits.amount.max * 가격
    3순위: 거래소 기본 안전상한
    """
    ex_name = str(future_ex_name).upper()
    base = normalize_symbol(symbol)

    override = safe_float((FUTURES_MAX_POSITION_USDT_OVERRIDES.get(ex_name) or {}).get(base))
    if override > 0:
        return override * usd_krw, "override"

    try:
        m = fex.markets.get(market) or {}
        amount_max = safe_float(((m.get("limits") or {}).get("amount") or {}).get("max"))
        contract_size = safe_float(m.get("contractSize"), 1.0) or 1.0
        if amount_max > 0 and best_bid > 0:
            # ccxt amount 단위가 계약수/코인수 거래소별로 다를 수 있어 보수적으로 계산.
            limit_usdt = amount_max * contract_size * best_bid
            if limit_usdt > 0:
                return limit_usdt * usd_krw, "ccxt_market_limits"
    except Exception:
        pass

    default_usdt = safe_float(DEFAULT_FUTURES_MAX_POSITION_USDT_BY_EXCHANGE.get(ex_name), 1_000.0)
    return default_usdt * usd_krw, "default_safe_limit"


def build_user_exchange_from_member(member: Dict[str, Any], exchange_name: str, market_type: str):
    """
    승인회원별 API 키로 거래소 객체 생성.
    Supabase 컬럼 예시:
      upbit_api_key / upbit_secret_key
      bithumb_api_key / bithumb_secret_key
      gate_api_key / gate_secret_key
      mexc_api_key / mexc_secret_key
      bitget_api_key / bitget_secret_key / bitget_password
      bingx_api_key / bingx_secret_key
    """
    if ccxt is None:
        return None

    name = str(exchange_name).lower()
    ccxt_map = {
        "upbit": "upbit",
        "bithumb": "bithumb",
        "mexc": "mexc",
        "gate": "gateio",
        "gateio": "gateio",
        "bitget": "bitget",
        "bingx": "bingx",
    }
    ccxt_id = ccxt_map.get(name)
    if not ccxt_id:
        return None

    prefix = "gate" if name in ("gate", "gateio") else name
    api_key = member.get(f"{prefix}_api_key") or member.get(f"{prefix}_access_key")
    secret = member.get(f"{prefix}_secret_key") or member.get(f"{prefix}_secret")
    password = member.get(f"{prefix}_password") or member.get(f"{prefix}_passphrase")

    if not api_key or not secret:
        return None

    klass = getattr(ccxt, ccxt_id, None)
    if klass is None:
        return None

    params = {
        "apiKey": api_key,
        "secret": secret,
        "enableRateLimit": True,
        "timeout": 10000,
        "options": {"defaultType": "swap" if market_type == "future" else "spot"},
    }
    if password:
        params["password"] = password
    return klass(params)


def find_member_by_telegram_id(user_id: str) -> Optional[Dict[str, Any]]:
    for member in supabase_get_approved_members():
        tg_id = get_member_chat_id(member)
        if str(tg_id) == str(user_id):
            return member
    return None


def fetch_current_domestic_book_for_signal(signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """진입 직전 국내 현물 현재 호가 재조회. 현재 파일은 UPBIT/BITHUMB 중심."""
    source = str(signal.get("domestic") or signal.get("domestic_exchange") or "").upper()
    coin = normalize_symbol(signal.get("coin") or "")
    market = str(signal.get("domestic_market") or "")
    try:
        if source == "UPBIT":
            upbit_market = market if market.startswith("KRW-") else f"KRW-{coin}"
            ob = session.get("https://api.upbit.com/v1/orderbook", params={"markets": upbit_market}, timeout=4).json()
            units = (ob[0] or {}).get("orderbook_units") or []
            bids = [[safe_float(x.get("bid_price")), safe_float(x.get("bid_size"))] for x in units]
            asks = [[safe_float(x.get("ask_price")), safe_float(x.get("ask_size"))] for x in units]
        elif source == "BITHUMB":
            base = coin
            ob = session.get(f"https://api.bithumb.com/public/orderbook/{base}_KRW", params={"count": 30}, timeout=4).json()
            od = ob.get("data") or {}
            bids = [[safe_float(x.get("price")), safe_float(x.get("quantity"))] for x in od.get("bids", [])]
            asks = [[safe_float(x.get("price")), safe_float(x.get("quantity"))] for x in od.get("asks", [])]
        else:
            return None
        bids = [x for x in bids if x[0] > 0 and x[1] > 0]
        asks = [x for x in asks if x[0] > 0 and x[1] > 0]
        bids.sort(key=lambda x: x[0], reverse=True)
        asks.sort(key=lambda x: x[0])
        if not bids or not asks:
            return None
        return {"best_bid": bids[0][0], "best_ask": asks[0][0], "bids": bids, "asks": asks}
    except Exception as e:
        print("[진입직전 국내호가 재조회 실패]", e)
        return None


def fetch_current_btc_spot_for_source(source: str) -> Optional[Dict[str, Any]]:
    return fetch_current_domestic_book_for_signal({"domestic": source, "coin": "BTC", "domestic_market": "KRW-BTC" if str(source).upper() == "UPBIT" else "BTC_KRW"})


def realtime_entry_recheck(signal: Dict[str, Any], amount_krw: int) -> Tuple[bool, str]:
    """진입 직전 핵심 조건만 재검사.

    성능을 위해 거래소MAX/BTC 전체맵 재계산은 하지 않고,
    현재 코인 호가 + BTC 기준 + 0.5% 벽 + signal 남은금액만 재조회/확인한다.
    """
    signal_id = str(signal.get("signal_id") or "")
    if not signal_id:
        return False, "❌ 진입 취소\n\n사유: signal_id 없음"

    max_entry = int(safe_float(signal.get("max_entry_krw") or signal.get("final_entry_krw")))
    remaining = get_signal_remaining_krw(signal_id)
    if amount_krw > max_entry > 0:
        return False, (
            "❌ 진입 불가\n\n"
            "사유: 최종 진입가능 금액 초과\n\n"
            f"선택금액: {fmt_man_krw(amount_krw)}\n"
            f"최종 진입가능: {fmt_man_krw(max_entry)}\n"
            f"거래소 최대: {fmt_man_krw(signal.get('futures_position_limit_krw'))}"
        )
    if remaining > 0 and amount_krw > remaining:
        return False, (
            "❌ 진입 불가\n\n"
            "사유: 남은 진입 가능금액 부족\n\n"
            f"선택금액: {fmt_man_krw(amount_krw)}\n"
            f"현재 남음: {fmt_man_krw(remaining)}\n"
            f"이미 사용: {fmt_man_krw(signal.get('used_entry_krw'))}"
        )

    usd_krw = safe_float(signal.get("usd_krw"), FALLBACK_USD_KRW)
    source = str(signal.get("domestic") or signal.get("domestic_exchange") or "").upper()
    future_name = str(signal.get("foreign") or signal.get("foreign_exchange") or "").upper()
    coin = normalize_symbol(signal.get("coin") or "")

    spot = fetch_current_domestic_book_for_signal(signal)
    if not spot:
        return False, "❌ 진입 취소\n\n사유: 국내 현물 현재 호가 재조회 실패"
    spot_ask_usdt = safe_float(spot.get("best_ask")) / usd_krw

    fex = GLOBAL_FUTURE_EXS.get(future_name)
    if not fex:
        return False, f"❌ 진입 취소\n\n사유: 해외 선물 거래소 객체 없음 ({future_name})\n\n확인: 반자동 재검사용 선물 객체={list(GLOBAL_FUTURE_EXS.keys())}"
    fmarket = signal.get("foreign_market") or find_future_market(fex, coin)
    future = fetch_ccxt_book(fex, fmarket, is_future=True) if fmarket else None
    if not future:
        return False, "❌ 진입 취소\n\n사유: 해외 선물 현재 호가 재조회 실패"

    basis_now = calc_basis_percent(future["best_bid"], spot_ask_usdt)

    # BTC 기준 프리미엄 현재 재계산
    btc_spot = fetch_current_btc_spot_for_source(source)
    btc_basis_now = safe_float(signal.get("btc_gap"))
    if btc_spot:
        btc_market = find_future_market(fex, "BTC")
        btc_future = fetch_ccxt_book(fex, btc_market, is_future=True) if btc_market else None
        if btc_future:
            btc_spot_ask_usdt = safe_float(btc_spot.get("best_ask")) / usd_krw
            btc_basis_now = calc_basis_percent(btc_future["best_bid"], btc_spot_ask_usdt)

    edge_now = basis_now - btc_basis_now
    if edge_now < MIN_RETAIN_EDGE_PERCENT:
        return False, (
            "❌ 진입 취소\n\n"
            "사유: 현재 실제엣지 부족\n\n"
            f"알림 당시: {safe_float(signal.get('real_edge')):+.2f}%\n"
            f"현재: {edge_now:+.2f}%\n"
            f"최소 유지엣지: +{MIN_RETAIN_EDGE_PERCENT:.2f}% 이상"
        )

    allowed_slippage = calc_allowed_slippage_percent(edge_now)
    tiers_text, spot_wall_krw, future_wall_krw, live_fill_krw = build_dynamic_slippage_tiers_text(
        spot.get("asks") or [],
        safe_float(spot.get("best_ask")),
        future.get("bids") or [],
        future["best_bid"],
        usd_krw,
        allowed_slippage,
        safe_float(signal.get("futures_position_limit_krw"), 10**18),
        spot.get("quote", "KRW"),
    )

    if amount_krw > live_fill_krw:
        return False, (
            "❌ 진입 취소\n\n"
            "사유: 엣지 2% 유지 가능금액 부족 / 동적 슬리피지 초과\n\n"
            f"선택금액: {fmt_man_krw(amount_krw)}\n"
            f"현재 실제엣지: {edge_now:+.2f}%\n"
            f"최소 유지엣지: +{MIN_RETAIN_EDGE_PERCENT:.2f}%\n"
            f"허용 슬리피지: {allowed_slippage:.2f}%\n"
            f"현재 가능: {fmt_man_krw(live_fill_krw)}\n\n"
            f"체결범위별 가능금액\n{tiers_text}"
        )

    return True, (
        "진입 직전 재검사 통과\n\n"
        f"현재 실제엣지: {edge_now:+.2f}%\n"
        f"최소 유지엣지: +{MIN_RETAIN_EDGE_PERCENT:.2f}%\n"
        f"허용 슬리피지: {allowed_slippage:.2f}%\n"
        f"현재 가능: {fmt_man_krw(live_fill_krw)}\n"
        f"남은 가능: {fmt_man_krw(remaining)}\n\n"
        f"체결범위별 가능금액\n{tiers_text}"
    )


def check_entry_balances(user_id: str, signal: Dict[str, Any], amount_krw: int) -> Tuple[bool, str]:
    """
    진입 실행 전 최종 검사.
    1) 현재 실제엣지/0.5%벽/남은금액 재검사
    2) API/잔고 검사
    """
    ok_live, live_reason = realtime_entry_recheck(signal, amount_krw)
    if not ok_live:
        return False, live_reason

    # 실전가상 모드:
    # 실제 주문을 내지 않으므로 유저 API/잔고 검사는 하지 않는다.
    # 현재 엣지/엣지2% 유지 체결범위/거래소MAX/남은금액 재검사만 통과하면 가상진입 허용.
    if PAPER_TRADING_ENABLED and not REAL_ORDER_ENABLED:
        return True, (
            live_reason + "\n\n"
            "✅ 실전가상 모드 통과\n"
            "실제 주문 OFF / API·잔고 검사 SKIP\n"
            "가상 진입 데이터만 저장합니다."
        )

    member = find_member_by_telegram_id(user_id)
    if not member:
        return False, "승인회원 정보를 찾지 못했습니다."

    domestic = str(signal.get("domestic", "")).lower()
    foreign = str(signal.get("foreign", "")).lower()
    usd_krw = safe_float(signal.get("usd_krw"), FALLBACK_USD_KRW)
    leverage = safe_float(member.get("semi_auto_leverage"), 1.0)
    if leverage <= 0:
        leverage = 1.0

    need_krw = amount_krw * (1.0 + BALANCE_SAFETY_BUFFER_PERCENT / 100.0)
    need_usdt = (amount_krw / usd_krw / leverage) * (1.0 + BALANCE_SAFETY_BUFFER_PERCENT / 100.0)

    domestic_ex = build_user_exchange_from_member(member, domestic, "spot")
    foreign_ex = build_user_exchange_from_member(member, foreign, "future")

    if domestic_ex is None:
        return False, (
            "❌ 국내 API 미등록\n\n"
            f"{signal.get('domestic')} API 등록 후 사용 가능합니다.\n"
            "홈페이지 AUTO 신청/설정에서 국내 거래소 API를 먼저 등록해주세요."
        )
    if foreign_ex is None:
        return False, (
            "❌ 해외 API 미등록\n\n"
            f"{signal.get('foreign')} 선물 API 등록 후 사용 가능합니다.\n"
            "홈페이지 AUTO 신청/설정에서 해외 선물 API를 먼저 등록해주세요."
        )

    try:
        domestic_balance = domestic_ex.fetch_balance()
        krw_free = safe_float((domestic_balance.get("free") or {}).get("KRW"))
    except Exception as e:
        return False, f"❌ 국내 잔고 조회 실패\n\n{signal.get('domestic')} API 권한 또는 키를 확인해주세요.\n오류: {e}"

    try:
        foreign_balance = foreign_ex.fetch_balance()
        usdt_free = safe_float((foreign_balance.get("free") or {}).get("USDT"))
        if usdt_free <= 0:
            usdt_free = safe_float((foreign_balance.get("total") or {}).get("USDT"))
    except Exception as e:
        return False, f"❌ 해외 잔고 조회 실패\n\n{signal.get('foreign')} 선물 API 권한 또는 키를 확인해주세요.\n오류: {e}"

    if krw_free < need_krw:
        return False, (
            "❌ 진입 불가\n\n사유: 국내 현물 KRW 잔고 부족\n\n"
            f"선택금액: {fmt_man_krw(amount_krw)}\n"
            f"필요 KRW: {fmt_man_krw(need_krw)}\n"
            f"현재 KRW: {fmt_man_krw(krw_free)}"
        )

    if usdt_free < need_usdt:
        return False, (
            "❌ 진입 불가\n\n사유: 해외 선물 USDT 잔고 부족\n\n"
            f"선택금액: {fmt_man_krw(amount_krw)}\n"
            f"레버리지: x{leverage:g}\n"
            f"필요 USDT: {need_usdt:,.2f}\n"
            f"현재 USDT: {usdt_free:,.2f}"
        )

    return True, (
        live_reason + "\n\n" +
        "잔고 확인 완료\n\n"
        f"선택금액: {fmt_man_krw(amount_krw)}\n"
        f"국내 KRW: {fmt_man_krw(krw_free)}\n"
        f"해외 USDT: {usdt_free:,.2f}\n"
        f"필요 USDT: {need_usdt:,.2f}"
    )


def register_semi_auto_position(user_id: str, signal: Dict[str, Any], amount_krw: int) -> str:
    """진입 성공 후 자동청산 감시 대상으로 등록한다."""
    signal_id_for_path = str(signal.get("signal_id") or "")
    path, state = _read_signal_state_file(signal_id_for_path)
    pos_id = f"POS_{signal.get('signal_id')}_{user_id}_{int(time.time())}"
    entry_edge = safe_float(signal.get("real_edge"))
    domestic_entry_krw, foreign_entry_krw, final_entry_krw = calc_domestic_foreign_entry_amounts(signal, amount_krw)
    state.setdefault("positions", {})[pos_id] = {
        "pos_id": pos_id,
        "user_id": str(user_id),
        "signal_id": str(signal.get("signal_id")),
        "coin": signal.get("coin"),
        "domestic": signal.get("domestic"),
        "foreign": signal.get("foreign"),
        "domestic_market": signal.get("domestic_market"),
        "foreign_market": signal.get("foreign_market"),
        "amount_krw": int(final_entry_krw),
        "domestic_entry_krw": int(domestic_entry_krw),
        "foreign_entry_krw": int(foreign_entry_krw),
        "entry_edge": entry_edge,
        "take_profit_edge": AUTO_TAKE_PROFIT_EDGE_PERCENT,
        "take_profit_force_edge": AUTO_TAKE_PROFIT_FORCE_EDGE_PERCENT,
        "warn_edge": entry_edge + AUTO_WARN_EDGE_ADD_PERCENT,
        "strong_warn_edge": entry_edge + AUTO_STRONG_WARN_EDGE_ADD_PERCENT,
        "stop_watch_edge": entry_edge + AUTO_STOP_WATCH_EDGE_ADD_PERCENT,
        "stop_watch_started_at": None,
        "warn_sent": False,
        "strong_warn_sent": False,
        "status": "ACTIVE",
        "opened_at": now_str(),
        "real_order": REAL_ORDER_ENABLED,
    }
    _write_state_file(path, state)

    # V8.1 저장 보강:
    # 실전가상/페이퍼 모드에서는 진입 성공 즉시 CSV 기록을 강제로 남긴다.
    try:
        paper_record_entry(pos_id, user_id, signal, int(final_entry_krw))
    except Exception as e:
        print(f"[실전가상 기록 실패] 진입 CSV 저장 실패 {pos_id}: {e}")

    return pos_id


def get_active_positions_for_market(symbol: str, domestic: str, foreign: str) -> List[Tuple[str, Dict[str, Any]]]:
    """현재 스캔 중인 코인/거래소 조합과 일치하는 활성 반자동 포지션 조회."""
    state = _read_semi_state()
    positions = state.get("positions", {})
    out = []
    for pos_id, pos in positions.items():
        if not isinstance(pos, dict):
            continue
        if str(pos.get("status")) != "ACTIVE":
            continue
        if normalize_symbol(pos.get("coin")) != normalize_symbol(symbol):
            continue
        if str(pos.get("domestic", "")).upper() != str(domestic or "").upper():
            continue
        if str(pos.get("foreign", "")).upper() != str(foreign or "").upper():
            continue
        out.append((pos_id, pos))
    return out


def mark_position_closed(pos_id: str, status: str, current_edge: float, reason: str) -> None:
    state = _read_semi_state()
    pos = state.setdefault("positions", {}).get(pos_id)
    if isinstance(pos, dict):
        before_close = dict(pos)
        pos["status"] = status
        pos["closed_at"] = now_str()
        pos["close_edge"] = round(current_edge, 4)
        pos["close_reason"] = reason
        _write_semi_state(state)
        paper_record_close(pos_id, before_close, status, current_edge, reason)


def execute_auto_close_orders(pos: Dict[str, Any], current_edge: float) -> Tuple[bool, str]:
    """
    자동청산 주문 실행 자리.
    실제 주문 API를 연결하기 전에는 REAL_ORDER_ENABLED=False라 주문을 내지 않는다.
    실제 연결 시 여기에서 국내 현물 매도 + 해외 선물 숏 청산(reduceOnly buy)을 실행하면 된다.
    """
    if not REAL_ORDER_ENABLED:
        return True, "테스트 모드: 실제 청산 주문은 OFF, 자동청산 조건만 감지했습니다."

    # TODO: 실제 주문 연결
    # 1) 승인회원 API 조회
    # 2) 국내 현물 보유수량 매도
    # 3) 해외 선물 숏 reduceOnly 시장가 청산
    # 4) 체결 결과 저장
    return False, "REAL_ORDER_ENABLED=True 이지만 실제 청산 주문 함수가 아직 연결되지 않았습니다."


def _update_position_fields(pos_id: str, fields: Dict[str, Any]) -> None:
    state = _read_semi_state()
    pos = state.setdefault("positions", {}).get(pos_id)
    if isinstance(pos, dict):
        pos.update(fields)
        _write_semi_state(state)


def check_semi_auto_auto_close(symbol: str, domestic: str, foreign: str, current_edge: float, funding_rate_percent: Optional[float] = None) -> None:
    """활성 반자동 포지션 자동익절/경고/자동손절 감시.

    익절:
      - 현재 실제엣지 <= +0.5%: 유연 청산 시도
      - +0.3% 이하: 더 강한 익절권으로 간주

    손절:
      - 진입엣지 +4%: 1차 경고
      - 진입엣지 +6%: 2차 강경고
      - 진입엣지 +8% 이상이 15분 동안 계속 유지될 때만 자동손절
      - 중간에 +8% 아래로 내려오면 손절 감시 타이머 해제
    """
    if not AUTO_CLOSE_ENABLED:
        return

    positions = get_active_positions_for_market(symbol, domestic, foreign)
    if not positions:
        return

    now_ts = time.time()

    for pos_id, pos in positions:
        entry_edge = safe_float(pos.get("entry_edge"))
        take_profit_edge = safe_float(pos.get("take_profit_edge"), AUTO_TAKE_PROFIT_EDGE_PERCENT)
        take_profit_force_edge = safe_float(pos.get("take_profit_force_edge"), AUTO_TAKE_PROFIT_FORCE_EDGE_PERCENT)
        warn_edge = safe_float(pos.get("warn_edge"), entry_edge + AUTO_WARN_EDGE_ADD_PERCENT)
        strong_warn_edge = safe_float(pos.get("strong_warn_edge"), entry_edge + AUTO_STRONG_WARN_EDGE_ADD_PERCENT)
        stop_watch_edge = safe_float(pos.get("stop_watch_edge"), entry_edge + AUTO_STOP_WATCH_EDGE_ADD_PERCENT)
        user_id = str(pos.get("user_id") or "")
        funding_text = "조회불가" if funding_rate_percent is None else f"{funding_rate_percent:+.4f}%"

        def send_pos_msg(title: str, body: str, vip: bool = False) -> None:
            msg = f"""{title}

코인: {pos.get('coin')}
경로: {pos.get('domestic')} 현물 + {pos.get('foreign')} 선물숏
금액: {fmt_man_krw(pos.get('amount_krw'))}

진입 실제엣지: {entry_edge:+.2f}%
현재 실제엣지: {current_edge:+.2f}%
익절 기준: {take_profit_edge:+.2f}% 이하
1차 경고: {warn_edge:+.2f}% 이상
2차 경고: {strong_warn_edge:+.2f}% 이상
손절 감시: {stop_watch_edge:+.2f}% 이상 15분 유지
펀딩: {funding_text}

{body}

🕒 {now_str()}"""
            if user_id:
                telegram_send_private(user_id, msg)
            if vip:
                telegram_send(msg)

        # 1) 익절: 유연 청산. 정확히 0.5에 맞추기보다 0.5~0.3 구간에서 체결 우선.
        if current_edge <= take_profit_edge:
            ok, detail = execute_auto_close_orders(pos, current_edge)
            status = "AUTO_CLOSED" if ok else "CLOSE_FAILED"
            mark_position_closed(pos_id, status, current_edge, detail)
            force_text = "\n강한 익절권(+0.3% 이하) 도달" if current_edge <= take_profit_force_edge else ""
            send_pos_msg(
                "✅ 자동익절 조건 도달",
                f"결과:\n{detail}{force_text}",
                vip=True,
            )
            continue

        # 2) 1차 경고
        if current_edge >= warn_edge and not bool(pos.get("warn_sent")):
            _update_position_fields(pos_id, {"warn_sent": True, "warn_sent_at": now_str()})
            send_pos_msg(
                "⚠️ 자동청산 1차 경고",
                "진입 대비 실제엣지가 +4% 이상 악화되었습니다.\n급등/급락 윗꼬리 회귀 가능성이 있어 즉시 손절은 하지 않고 감시합니다.",
            )

        # 3) 2차 강경고
        if current_edge >= strong_warn_edge and not bool(pos.get("strong_warn_sent")):
            _update_position_fields(pos_id, {"strong_warn_sent": True, "strong_warn_sent_at": now_str()})
            send_pos_msg(
                "🚨 자동청산 2차 강경고",
                "진입 대비 실제엣지가 +6% 이상 악화되었습니다.\n아직 자동손절은 아니며, +8% 이상이 15분 유지될 때만 손절합니다.",
                vip=True,
            )

        # 4) +8% 이상이면 손절 감시 타이머 시작/유지
        if current_edge >= stop_watch_edge:
            started = safe_float(pos.get("stop_watch_started_ts"), 0.0)
            if started <= 0:
                _update_position_fields(pos_id, {
                    "stop_watch_started_ts": now_ts,
                    "stop_watch_started_at": now_str(),
                })
                send_pos_msg(
                    "⏱ 자동손절 감시 시작",
                    f"진입 대비 +8% 이상 악화되었습니다.\n이 상태가 {AUTO_STOP_HOLD_SEC // 60}분 동안 계속 유지되면 자동손절합니다.\n중간에 +8% 아래로 내려오면 감시가 해제됩니다.",
                    vip=True,
                )
                continue

            hold_sec = now_ts - started
            if hold_sec >= AUTO_STOP_HOLD_SEC:
                ok, detail = execute_auto_close_orders(pos, current_edge)
                status = "AUTO_STOPPED" if ok else "STOP_FAILED"
                mark_position_closed(pos_id, status, current_edge, detail)
                send_pos_msg(
                    "❌ 자동손절 실행",
                    f"진입 대비 +8% 이상 악화가 {AUTO_STOP_HOLD_SEC // 60}분 이상 유지되었습니다.\n\n결과:\n{detail}",
                    vip=True,
                )
            else:
                remain = max(0, int(AUTO_STOP_HOLD_SEC - hold_sec))
                # 도배 방지: 상태 메시지는 5분 간격으로만
                last_notice = safe_float(pos.get("stop_watch_last_notice_ts"), 0.0)
                if now_ts - last_notice >= 300:
                    _update_position_fields(pos_id, {"stop_watch_last_notice_ts": now_ts})
                    send_pos_msg(
                        "⏱ 자동손절 감시 유지",
                        f"+8% 이상 악화 상태가 유지 중입니다.\n남은 감시시간: 약 {remain // 60}분 {remain % 60}초",
                    )
            continue

        # 5) +8% 아래로 내려오면 손절 감시 해제
        if safe_float(pos.get("stop_watch_started_ts"), 0.0) > 0:
            _update_position_fields(pos_id, {
                "stop_watch_started_ts": 0,
                "stop_watch_started_at": None,
                "stop_watch_last_notice_ts": 0,
            })
            send_pos_msg(
                "✅ 자동손절 감시 해제",
                "실제엣지가 손절 감시 기준(+8%) 아래로 회귀했습니다.\n포지션은 유지됩니다.",
            )

def process_text_direct_amount(message: Dict[str, Any]) -> None:
    # 직접입력 기능은 속도/안정성을 위해 제거. 일반 메시지는 무시한다.
    return



# ============================================================
# V8.2 자동진입 / 최종확인 LOCK / 정지 버튼
# ============================================================
_PROCESSING_LOCK = threading.Lock()


def _read_auto_control() -> Dict[str, Any]:
    data = _read_json(AUTO_CONTROL_PATH, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("auto_entry_enabled", AUTO_ENTRY_ENABLED)
    data.setdefault("stopped", False)
    data.setdefault("updated_at", now_str())
    return data


def _write_auto_control(data: Dict[str, Any]) -> None:
    data = dict(data or {})
    data["updated_at"] = now_str()
    _write_json_atomic(AUTO_CONTROL_PATH, data)


def is_auto_entry_currently_enabled() -> bool:
    ctl = _read_auto_control()
    if bool(ctl.get("stopped")):
        return False
    return bool(ctl.get("auto_entry_enabled", AUTO_ENTRY_ENABLED))


def set_auto_trading_stopped(stopped: bool, reason: str = "") -> None:
    ctl = _read_auto_control()
    ctl["stopped"] = bool(stopped)
    ctl["auto_entry_enabled"] = False if stopped else AUTO_ENTRY_ENABLED
    ctl["reason"] = reason
    ctl["changed_at"] = now_str()
    _write_auto_control(ctl)


def make_processing_key(user_id: str, signal_id: str) -> str:
    return f"{user_id}:{signal_id}"


def acquire_processing_lock(user_id: str, signal_id: str, action: str = "ENTRY") -> Tuple[bool, str]:
    """최종확인/자동진입 중복 실행 방지. 같은 유저+신호는 1회만 처리."""
    path, state = _read_signal_state_file(signal_id)
    key = make_processing_key(user_id, signal_id)
    with _PROCESSING_LOCK:
        processing = state.setdefault("processing", {})
        existing = processing.get(key)
        if isinstance(existing, dict) and existing.get("status") == "PROCESSING":
            return False, "이미 처리 중입니다. 중복 진입을 막기 위해 차단했습니다."
        if isinstance(existing, dict) and existing.get("status") == "DONE":
            return False, "이미 처리 완료된 신호입니다. 중복 진입을 막기 위해 차단했습니다."
        processing[key] = {
            "status": "PROCESSING",
            "action": action,
            "started_at": now_str(),
            "started_ts": time.time(),
        }
        _write_state_file(path, state)
    return True, ""


def finish_processing_lock(user_id: str, signal_id: str, status: str = "DONE", reason: str = "") -> None:
    path, state = _read_signal_state_file(signal_id)
    key = make_processing_key(user_id, signal_id)
    with _PROCESSING_LOCK:
        processing = state.setdefault("processing", {})
        processing[key] = {
            "status": status,
            "reason": reason,
            "finished_at": now_str(),
            "finished_ts": time.time(),
        }
        _write_state_file(path, state)


def release_processing_lock_on_failure(user_id: str, signal_id: str, reason: str = "") -> None:
    # 실패는 재시도 가능해야 하므로 FAILED로 표시하고 금액은 기존 로직처럼 0원 초기화.
    finish_processing_lock(user_id, signal_id, "FAILED", reason)


def build_stop_keyboard(signal_id: str = "") -> List[List[Dict[str, str]]]:
    return [
        [{"text": "🛑 자동매매 정지", "callback_data": f"STOPREQ|{signal_id or 'GLOBAL'}"}],
        [{"text": "▶️ 자동매매 재시작", "callback_data": f"STARTREQ|{signal_id or 'GLOBAL'}"}],
    ]


def append_stop_button(keyboard: List[List[Dict[str, str]]], signal_id: str = "") -> List[List[Dict[str, str]]]:
    out = list(keyboard or [])
    out.extend(build_stop_keyboard(signal_id))
    return out


def build_stop_confirm_keyboard(signal_id: str = "") -> List[List[Dict[str, str]]]:
    sid = signal_id or "GLOBAL"
    return [
        [{"text": "✅ 신규진입 정지", "callback_data": f"STOPCONFIRM|{sid}"}],
        [{"text": "❌ 취소", "callback_data": f"STOPCANCEL|{sid}"}],
    ]


def build_stop_warning_text() -> str:
    return """⚠️ 자동매매 신규진입을 정지할까요?

정지 시:
- 신규 자동진입만 중단
- 현재 OPEN 포지션 감시는 계속 유지
- 익절/손절 감시는 계속 작동
- 포지션 강제종료는 하지 않음

정말 정지하시겠습니까?"""


def get_active_positions_all_files() -> List[Dict[str, Any]]:
    positions = []
    seen = set()
    for path in _semi_state_known_paths():
        state = _read_state_file(path)
        for pos_id, pos in (state.get("positions") or {}).items():
            if not isinstance(pos, dict):
                continue
            if str(pos.get("status", "")).upper() != "ACTIVE":
                continue
            if pos_id in seen:
                continue
            seen.add(pos_id)
            item = dict(pos)
            item["_state_path"] = path
            positions.append(item)
    return positions


def emergency_close_all_positions(request_user_id: str = "", current_edge: float = 0.0) -> Tuple[int, List[str]]:
    """정지 버튼용 전체 종료. 실전가상은 기록상 종료, 실전은 execute_auto_close_orders 자리에서 실제 청산 연결."""
    positions = get_active_positions_all_files()
    details = []
    closed = 0
    for pos in positions:
        pos_id = str(pos.get("pos_id") or "")
        try:
            ok, detail = execute_auto_close_orders(pos, current_edge)
            status = "MANUAL_STOP_CLOSED" if ok else "MANUAL_STOP_CLOSE_FAILED"
            mark_position_closed(pos_id, status, current_edge, "정지 버튼 전체 종료: " + str(detail))
            closed += 1 if ok else 0
            details.append(f"{pos.get('coin')} {pos.get('domestic')}↔{pos.get('foreign')} / {status}")
        except Exception as e:
            details.append(f"{pos.get('coin')} / 종료 실패: {e}")
    return closed, details


def _read_csv_rows_safe(path: str) -> List[Dict[str, Any]]:
    try:
        if not os.path.exists(path):
            return []
        with open(path, "r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception as e:
        print(f"[CSV 읽기 실패] {path} / {e}")
        return []


def get_closed_pos_ids_from_results() -> set:
    rows = _read_csv_rows_safe(PAPER_RESULTS_CSV)
    return {str(r.get("pos_id") or "").strip() for r in rows if str(r.get("pos_id") or "").strip()}


def get_open_domestic_entry_sum_from_entries_csv() -> int:
    """paper_entries.csv 기준 OPEN 국내진입금액 합계. 종료 결과가 있는 pos_id는 제외한다."""
    closed = get_closed_pos_ids_from_results()
    total = 0.0
    for r in _read_csv_rows_safe(PAPER_ENTRIES_CSV):
        pos_id = str(r.get("pos_id") or "").strip()
        if pos_id and pos_id in closed:
            continue
        status = str(r.get("status") or "").upper().strip()
        if status and status not in OPEN_ENTRY_STATUSES:
            continue
        total += safe_float(r.get("domestic_entry_krw") or r.get("entry_krw"))
    return int(total)


def get_open_foreign_margin_sum_from_entries_csv(foreign_exchange: str) -> int:
    """거래소별 OPEN 해외 증거금 사용액 합계.

    신규 V9.3.1 행은 foreign_margin_krw를 사용하고,
    구버전 행은 foreign_entry_krw / PAPER_FUTURES_LEVERAGE로 보수 계산한다.
    """
    closed = get_closed_pos_ids_from_results()
    target = str(foreign_exchange or "").upper().strip()
    total = 0.0
    for r in _read_csv_rows_safe(PAPER_ENTRIES_CSV):
        pos_id = str(r.get("pos_id") or "").strip()
        if pos_id and pos_id in closed:
            continue
        status = str(r.get("status") or "").upper().strip()
        if status and status not in OPEN_ENTRY_STATUSES:
            continue
        foreign = str(r.get("foreign") or r.get("foreign_exchange") or "").upper().strip()
        if target and foreign != target:
            continue
        margin = safe_float(r.get("foreign_margin_krw"))
        if margin <= 0:
            margin = safe_float(r.get("foreign_entry_krw") or r.get("entry_krw")) / max(1.0, safe_float(PAPER_FUTURES_LEVERAGE, 4.0))
        total += margin
    return int(total)

def get_foreign_margin_remaining_krw(foreign_exchange: str) -> int:
    foreign = str(foreign_exchange or "").upper().strip()
    cap = int(PAPER_FOREIGN_MARGIN_BASE_KRW_BY_EXCHANGE.get(foreign, 0))
    if cap <= 0:
        return 0
    used = get_open_foreign_margin_sum_from_entries_csv(foreign)
    return int(max(0, cap - used))


def get_realized_pnl_from_results_csv() -> float:
    return sum(safe_float(r.get("pnl_krw")) for r in _read_csv_rows_safe(PAPER_RESULTS_CSV))


def get_paper_domestic_total_asset_krw() -> int:
    """실전가상 총운용자산 = 초기 국내운용금 + 실현손익.

    사용자가 정한 공식(국내잔고 + OPEN 국내진입금액)과 동일하게 맞추면,
    국내잔고 = 초기금 + 실현손익 - OPEN 이므로 합계는 초기금 + 실현손익이 된다.
    """
    total = PAPER_DOMESTIC_BASE_KRW + get_realized_pnl_from_results_csv()
    return int(max(AUTO_ENTRY_MIN_KRW, total))


def calc_domestic_compound_entry_krw() -> int:
    if not DOMESTIC_COMPOUND_ENABLED:
        return int(AUTO_ENTRY_DEFAULT_KRW)
    divisor = max(1, int(DOMESTIC_COMPOUND_DIVISOR))
    total_asset = get_paper_domestic_total_asset_krw()
    amount = int(total_asset / divisor)
    # 만원 단위 절삭. 너무 자잘한 주문금액 변동 방지.
    amount = max(AUTO_ENTRY_MIN_KRW, (amount // 10_000) * 10_000)
    return int(amount)


def calc_auto_entry_amount_for_member(member: Dict[str, Any], signal: Dict[str, Any]) -> int:
    """V9.2 자동진입 금액 계산.

    기존 고정 10만원 대신 국내 복리 /20을 적용한다.
    신규 진입마다 국내 총운용자산(국내 잔고 + OPEN 국내진입금액)을 재계산하는 구조다.
    PAPER 모드에서는 실제 잔고 API 대신 초기 국내운용금 + 실현손익으로 계산한다.
    """
    capital_krw = get_member_capital_krw(member)
    split_count = get_member_split_count(member)
    target = int(max(AUTO_ENTRY_MIN_KRW, (capital_krw / max(1, split_count)) // 10000 * 10000))
    max_entry = int(safe_float(signal.get("max_entry_krw") or signal.get("final_entry_krw")))
    remaining = int(safe_float(signal.get("remaining_entry_krw", max_entry)))

    limits = [target]
    if max_entry > 0:
        limits.append(max_entry)
    if remaining > 0:
        limits.append(remaining)
    if MAX_USER_ENTRY_KRW > 0:
        limits.append(MAX_USER_ENTRY_KRW)

    amount = int(max(0, min(limits)))

    # V9.3.1: 해외 거래소별 증거금 50만 / 레버리지 4배 한도 적용.
    # 해외 필요 증거금 = 국내 진입금액 / 레버리지.
    foreign = str(signal.get("foreign") or signal.get("foreign_exchange") or "").upper().strip()
    if TEST_CAP_FEE_MODE and foreign:
        remaining_margin = get_foreign_margin_remaining_krw(foreign)
        max_domestic_by_margin = int(remaining_margin * max(1.0, safe_float(PAPER_FUTURES_LEVERAGE, 4.0)))
        amount = min(amount, max_domestic_by_margin)

    if amount < AUTO_ENTRY_MIN_KRW:
        return 0
    return amount


def check_entry_for_auto_fast_paper(user_id: str, signal: Dict[str, Any], amount_krw: int) -> Tuple[bool, str, float]:
    """V8.8 자동진입 전용 초고속 재검사.

    PAPER_TRADING_ENABLED=True / REAL_ORDER_ENABLED=False에서는 실제 주문이 아니므로
    국내/해외 API 잔고 조회를 하지 않는다. 텔레그램 전송도 재검사 후 결과만 보낸다.
    return = (ok, message, elapsed_sec)
    """
    t0 = time.time()
    try:
        ok, msg = realtime_entry_recheck(signal, amount_krw)
        elapsed = time.time() - t0
        if elapsed > MAX_AUTO_RECHECK_DELAY_SEC:
            return False, (
                "❌ 진입 취소\n\n"
                "사유: 최종 재검사 지연\n\n"
                f"재검사 소요: {elapsed:.2f}초\n"
                f"허용: {MAX_AUTO_RECHECK_DELAY_SEC:.2f}초\n"
                "빠른 양방 자동진입 기준상 시간이 지나 엣지 훼손 가능성이 큽니다."
            ), elapsed
        return ok, msg + f"\n\n재검사 소요: {elapsed:.2f}초", elapsed
    except Exception as e:
        elapsed = time.time() - t0
        return False, f"❌ 진입 취소\n\n사유: 자동진입 초고속 재검사 예외\n{e}\n\n재검사 소요: {elapsed:.2f}초", elapsed

def perform_auto_entry_for_member(member: Dict[str, Any], signal: Dict[str, Any]) -> Tuple[bool, str]:
    """신호 발생 즉시 승인회원별 자동진입. 현재는 REAL_ORDER_ENABLED=False면 실전가상 저장."""
    tg_id = str(get_member_chat_id(member) or "").strip()
    if not tg_id:
        return False, "tg_chat_id 없음"

    signal_id = str(signal.get("signal_id") or "")
    if not signal_id:
        return False, "signal_id 없음"

    if member_has_active_coin_position(member, signal):
        return False, f"{signal.get('coin')} ACTIVE 포지션 보유중"

    if not is_auto_entry_currently_enabled():
        return False, "자동진입 정지 상태"

    amount = calc_auto_entry_amount_for_member(member, signal)
    if amount < AUTO_ENTRY_MIN_KRW:
        reason = f"자동진입 금액 부족: {fmt_man_krw(amount)}"
        paper_record_auto_attempt(tg_id, signal, amount, "SKIP_AMOUNT", reason)
        send_auto_entry_attempt_dm(tg_id, signal, "❌ 자동진입 미진입", reason, amount)
        return False, reason

    print(
        f"[자동진입 후보] tg={tg_id} / {signal.get('coin')} / "
        f"{signal.get('domestic')}->{signal.get('foreign')} / "
        f"감지엣지={safe_float(signal.get('real_edge')):+.2f}% / 금액={fmt_man_krw(amount)}"
    )
    paper_record_auto_attempt(tg_id, signal, amount, "CANDIDATE", "최종 재검사 시작")

    got_lock, lock_reason = acquire_processing_lock(tg_id, signal_id, "AUTO_ENTRY")
    if not got_lock:
        paper_record_auto_attempt(tg_id, signal, amount, "SKIP_LOCK", lock_reason)
        send_auto_entry_attempt_dm(tg_id, signal, "❌ 자동진입 미진입", "사유: 중복 실행 LOCK\n" + str(lock_reason), amount)
        return False, lock_reason

    try:
        recheck_started_at = time.time()
        if PAPER_TRADING_ENABLED and not REAL_ORDER_ENABLED and PAPER_FAST_RECHECK_ONLY:
            ok, reason, recheck_elapsed = check_entry_for_auto_fast_paper(tg_id, signal, amount)
        else:
            ok, reason = check_entry_balances(tg_id, signal, amount)
            recheck_elapsed = time.time() - recheck_started_at
        if not ok:
            set_user_selected_amount(tg_id, signal_id, 0)
            release_processing_lock_on_failure(tg_id, signal_id, reason)
            paper_record_auto_attempt(tg_id, signal, amount, "FAIL_FAST_RECHECK", str(reason) + f"\n재검사소요={recheck_elapsed:.2f}초")
            send_auto_entry_attempt_dm(tg_id, signal, "❌ 자동진입 미진입", reason, amount)
            return False, reason

        remaining_before = get_signal_remaining_krw(signal_id)
        if amount > remaining_before > 0:
            set_user_selected_amount(tg_id, signal_id, 0)
            msg = f"남은 진입 가능금액 부족 / 선택 {fmt_man_krw(amount)} / 남음 {fmt_man_krw(remaining_before)}"
            release_processing_lock_on_failure(tg_id, signal_id, msg)
            paper_record_auto_attempt(tg_id, signal, amount, "FAIL_REMAINING", msg)
            send_auto_entry_attempt_dm(tg_id, signal, "❌ 자동진입 미진입", msg, amount)
            return False, msg

        signal = get_signal_state(signal_id) or signal
        domestic_entry_krw, foreign_entry_krw, final_entry_krw = calc_domestic_foreign_entry_amounts(signal, amount)
        used_after, remaining_after = update_signal_usage(signal_id, final_entry_krw)

        # 실제 주문 ON이면 이 지점에 국내 현물 매수 + 해외 선물 숏 동시 실행을 연결한다.
        # 현재 파일은 주문 함수가 아직 없으므로 REAL_ORDER_ENABLED=False 실전가상 저장을 안전 기본값으로 둔다.
        pos_id = register_semi_auto_position(tg_id, signal, final_entry_krw)
        finish_processing_lock(tg_id, signal_id, "DONE", pos_id)
        paper_record_auto_attempt(tg_id, signal, final_entry_krw, "SUCCESS", f"pos_id={pos_id}")

        if AUTO_ENTRY_SEND_DM_RESULT:
            telegram_send_private(
                tg_id,
                (
                    "✅ 실전가상 자동진입 완료 - 국내복리 /20\n\n" if not REAL_ORDER_ENABLED else "✅ 실전 자동진입 완료\n\n"
                )
                + f"코인: {signal.get('coin')}\n"
                + f"경로: {signal.get('domestic')} ↔ {signal.get('foreign')}\n\n"
                + f"국내 진입: {fmt_man_krw(domestic_entry_krw)}\n"
                + f"해외 선물 명목: {fmt_man_krw(foreign_entry_krw)}\n"
                + f"해외 증거금(4배): {fmt_man_krw(calc_required_foreign_margin_krw(domestic_entry_krw))}\n"
                + f"최종 기준금액: {fmt_man_krw(final_entry_krw)}\n\n"
                + f"진입 실제엣지: {safe_float(signal.get('real_edge')):+.2f}%\n"
                + f"최소 유지엣지: {safe_float(signal.get('min_retain_edge_percent'), MIN_RETAIN_EDGE_PERCENT):+.2f}%\n"
                + f"허용 슬리피지: {safe_float(signal.get('allowed_slippage_percent')):.2f}%\n"
                + f"국내 최종벽: {fmt_man_krw(signal.get('spot_wall_krw'))}\n"
                + f"해외 최종벽: {fmt_man_krw(signal.get('futures_wall_krw'))}\n"
                + f"거래소MAX: {fmt_man_krw(signal.get('futures_position_limit_krw'))}\n"
                + f"남은 가능금액: {fmt_man_krw(remaining_after)}\n"
                + f"재검사 소요: {recheck_elapsed:.2f}초\n"
                + f"포지션ID: {pos_id}\n\n"
                + "※ 자동진입은 신호별 1회 LOCK 처리되어 중복 실행을 차단합니다.\n"
                + ("실제 주문 OFF / 가상 진입 데이터 저장 완료" if not REAL_ORDER_ENABLED else "실제 주문 ON")
            )
        return True, pos_id

    except Exception as e:
        release_processing_lock_on_failure(tg_id, signal_id, str(e))
        reason = f"자동진입 예외: {e}"
        paper_record_auto_attempt(tg_id, signal, amount if 'amount' in locals() else 0, "EXCEPTION", reason)
        send_auto_entry_attempt_dm(tg_id, signal, "❌ 자동진입 미진입", reason, amount if 'amount' in locals() else 0)
        return False, reason


def auto_entry_approved_members(signal: Dict[str, Any]) -> None:
    """AUTO 전용: 승인회원 + auto_settings를 읽어 알림/자동진입을 분기한다."""
    if not AUTO_ENTRY_ENABLED:
        print("[AUTO] AUTO_ENTRY_ENABLED=False")
        return
    if not is_auto_entry_currently_enabled():
        print("[AUTO] 전체 정지 상태 - 신규 자동진입 스킵")
        return

    members = supabase_get_approved_members()
    if not members:
        print("[AUTO] 승인회원 없음")
        return

    ok_count = 0
    fail_count = 0
    alert_only_count = 0
    seen_tg_ids = set()
    for raw_member in members:
        member = merge_member_auto_settings(raw_member)
        tg_id = str(get_member_chat_id(member) or "").strip()
        if not tg_id:
            continue
        if tg_id in seen_tg_ids:
            print(f"[AUTO SKIP] 중복 tg_chat_id {tg_id}")
            continue
        seen_tg_ids.add(tg_id)

        if not is_member_service_enabled(member):
            print(f"[AUTO SKIP] service_enabled OFF tg={tg_id}")
            continue

        if not is_member_auto_enabled(member):
            alert_only_count += 1
            print(f"[AUTO 알림만] auto_enabled OFF tg={tg_id} / {signal.get('coin')}")
            send_signal_alert_only_dm(tg_id, signal, "auto_enabled=OFF")
            continue

        ok, detail = perform_auto_entry_for_member(member, signal)
        if ok:
            ok_count += 1
            print(f"[AUTO 진입 성공] tg={tg_id} / {signal.get('coin')} / {detail}")
        else:
            fail_count += 1
            print(f"[AUTO 진입 스킵/실패] tg={tg_id} / {signal.get('coin')} / {detail}")

    print(f"[AUTO 결과] 진입성공 {ok_count} / 실패·스킵 {fail_count} / 알림만 {alert_only_count} / {signal.get('coin')} {signal.get('foreign')}")


def process_callback_query(cb: Dict[str, Any]) -> None:
    cb_id = cb.get("id")
    msg = cb.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id") or "")
    message_id = msg.get("message_id")
    user_id = str((cb.get("from") or {}).get("id") or chat_id)
    data = str(cb.get("data") or "")

    parts = data.split("|")
    action = parts[0] if parts else ""
    signal_id = parts[1] if len(parts) >= 2 else ""

    if action == "STOPREQ":
        telegram_answer_callback(cb_id, "정지 확인 필요")
        telegram_edit_message(chat_id, message_id, build_stop_warning_text(), build_stop_confirm_keyboard(signal_id))
        return

    if action == "STARTREQ":
        set_auto_trading_stopped(False, f"텔레그램 재시작 버튼 / user={user_id}")
        msg = "▶️ 자동매매 재시작 완료\n\n신규 자동진입: 재개\nOPEN 포지션 감시: 유지\n\n🕒 " + now_str()
        telegram_answer_callback(cb_id, "자동매매 재시작 완료")
        telegram_edit_message(chat_id, message_id, msg, build_stop_keyboard(signal_id))
        telegram_send(msg)
        return

    if action == "STOPCANCEL":
        telegram_answer_callback(cb_id, "취소 완료")
        signal = get_signal_state(signal_id)
        if signal:
            selected = get_user_selected_amount(user_id, signal_id)
            telegram_edit_message(chat_id, message_id, build_member_dm_message(signal, selected), build_entry_keyboard(signal_id))
        else:
            telegram_edit_message(chat_id, message_id, "정지 취소 완료", [])
        return

    if action == "STOPCONFIRM":
        telegram_answer_callback(cb_id, "자동매매 신규진입 정지 완료")
        set_auto_trading_stopped(True, f"텔레그램 정지 버튼 / user={user_id}")
        msg = (
            "🛑 자동매매 신규진입 정지 완료\n\n"
            "신규 자동진입: 중단\n"
            "OPEN 포지션 감시: 유지\n"
            "익절/손절 감시: 유지\n\n"
            "다시 켜려면 재시작 버튼을 누르세요.\n\n"
            "🕒 " + now_str()
        )
        telegram_edit_message(chat_id, message_id, msg, build_stop_keyboard(signal_id))
        telegram_send_private(chat_id, msg)
        return

    if action in ("AMT", "RESET", "MAX", "RUN", "CONFIRM", "CANCEL"):
        telegram_answer_callback(cb_id, "AUTO 정지 버튼은 폐기되었습니다. AUTO 설정에서 제어해주세요.", True)
        return

    signal = get_signal_state(signal_id)

    if not signal:
        telegram_answer_callback(cb_id, "만료되었거나 없는 신호입니다.", True)
        return

    selected = get_user_selected_amount(user_id, signal_id)
    max_entry = int(safe_float(signal.get("max_entry_krw") or signal.get("final_entry_krw")))

    if action == "AMT" and len(parts) >= 3:
        add = int(safe_float(parts[2]))
        selected = set_user_selected_amount(user_id, signal_id, selected + add)
        if max_entry > 0 and selected > max_entry:
            telegram_answer_callback(cb_id, f"현재 선택: {fmt_man_krw(selected)} / 최대초과")
        else:
            telegram_answer_callback(cb_id, f"현재 선택: {fmt_man_krw(selected)}")
        telegram_edit_message(chat_id, message_id, build_member_dm_message(signal, selected), build_entry_keyboard(signal_id))
        return

    if action == "RESET":
        selected = set_user_selected_amount(user_id, signal_id, 0)
        telegram_answer_callback(cb_id, "초기화 완료")
        telegram_edit_message(chat_id, message_id, build_member_dm_message(signal, selected), build_entry_keyboard(signal_id))
        return

    if action == "MAX":
        selected = set_user_selected_amount(user_id, signal_id, max_entry)
        telegram_answer_callback(cb_id, f"최대 선택: {fmt_man_krw(selected)}")
        telegram_edit_message(chat_id, message_id, build_member_dm_message(signal, selected), build_entry_keyboard(signal_id))
        return

    if action == "RUN":
        # 버튼 로딩(물결)을 먼저 멈춘 뒤 최대금액/잔고/API 검사를 진행한다.
        if selected <= 0:
            telegram_answer_callback(cb_id, "먼저 금액을 선택하세요.", True)
            return

        telegram_answer_callback(cb_id, "잔고 확인 중...")
        ok, reason = check_entry_balances(user_id, signal, selected)
        if not ok:
            # 진입 실행 실패 시 선택금액 초기화.
            # 실패 후 기존 금액이 남아 있으면 다음 신호/재시도 때 실수로 과금액 진입할 수 있음.
            selected = set_user_selected_amount(user_id, signal_id, 0)
            fail_text = reason if str(reason).lstrip().startswith("❌") else "❌ 진입 불가\n\n" + reason
            reset_text = "\n\n선택금액은 0원으로 초기화되었습니다."
            telegram_answer_callback(cb_id, "진입 불가 - 금액 초기화", True)
            telegram_edit_message(chat_id, message_id, build_member_dm_message(signal, selected) + "\n" + fail_text + reset_text, build_entry_keyboard(signal_id))
            return

        confirm_text = f"""✅ 진입 전 확인

코인: {signal.get('coin')}
금액: {fmt_man_krw(selected)}

현물:
{signal.get('domestic')} 매수

선물:
{signal.get('foreign')} 숏

예상:
{safe_float(signal.get('expected_profit_min')):+.2f}% ~ {safe_float(signal.get('expected_profit_max')):+.2f}%

{reason}

아래 [최종 확인]을 눌러야 주문 단계로 넘어갑니다.
"""
        telegram_answer_callback(cb_id, "잔고 확인 완료")
        telegram_edit_message(chat_id, message_id, confirm_text, build_confirm_keyboard(signal_id, selected))
        return

    if action == "CONFIRM":
        amount = int(safe_float(parts[2])) if len(parts) >= 3 else selected
        got_lock, lock_reason = acquire_processing_lock(user_id, signal_id, "MANUAL_CONFIRM")
        if not got_lock:
            telegram_answer_callback(cb_id, lock_reason, True)
            return
        telegram_answer_callback(cb_id, "최종 잔고 재확인 중...")
        ok, reason = check_entry_balances(user_id, signal, amount)
        if not ok:
            # 최종 확인 실패 시에도 선택금액 초기화.
            selected = set_user_selected_amount(user_id, signal_id, 0)
            fail_text = reason if str(reason).lstrip().startswith("❌") else "❌ 진입 불가\n\n" + reason
            reset_text = "\n\n선택금액은 0원으로 초기화되었습니다."
            telegram_answer_callback(cb_id, "진입 불가 - 금액 초기화", True)
            release_processing_lock_on_failure(user_id, signal_id, fail_text)
            telegram_edit_message(chat_id, message_id, build_member_dm_message(signal, selected) + "\n" + fail_text + reset_text, build_entry_keyboard(signal_id))
            return

        remaining_before = get_signal_remaining_krw(signal_id)
        if amount > remaining_before > 0:
            selected = set_user_selected_amount(user_id, signal_id, 0)
            telegram_answer_callback(cb_id, "남은금액 부족 - 금액 초기화", True)
            fail_text = (
                "❌ 진입 불가\n\n"
                "사유: 남은 진입 가능금액 부족\n\n"
                f"선택금액: {fmt_man_krw(amount)}\n"
                f"현재 남음: {fmt_man_krw(remaining_before)}"
            )
            reset_text = "\n\n선택금액은 0원으로 초기화되었습니다."
            release_processing_lock_on_failure(user_id, signal_id, fail_text)
            telegram_edit_message(chat_id, message_id, build_member_dm_message(signal, selected) + "\n" + fail_text + reset_text, build_entry_keyboard(signal_id))
            return

        # 최신 signal 상태를 다시 읽어 화면에 남은 금액 반영
        signal = get_signal_state(signal_id) or signal
        domestic_entry_krw, foreign_entry_krw, final_entry_krw = calc_domestic_foreign_entry_amounts(signal, amount)

        # 최종 기준금액만큼 사용 처리
        used_after, remaining_after = update_signal_usage(signal_id, final_entry_krw)

        pos_id = register_semi_auto_position(user_id, signal, final_entry_krw)
        finish_processing_lock(user_id, signal_id, "DONE", pos_id)
        telegram_answer_callback(cb_id, "자동청산 감시 등록")
        telegram_send_private(
            user_id,
            (
                "✅ 실전가상 진입 감시 등록\n\n" if not REAL_ORDER_ENABLED else "✅ 반자동 진입 감시 등록\n\n"
            )
            + f"코인: {signal.get('coin')}\n"
            + f"경로: {signal.get('domestic')} ↔ {signal.get('foreign')}\n\n"
            + f"국내 진입: {fmt_man_krw(domestic_entry_krw)}\n"
            + f"해외 선물 진입: {fmt_man_krw(foreign_entry_krw)}\n"
            + f"최종 기준금액: {fmt_man_krw(final_entry_krw)}\n\n"
            + f"진입 실제엣지: {safe_float(signal.get('real_edge')):+.2f}%\n"
            + f"최소 유지엣지: {safe_float(signal.get('min_retain_edge_percent'), MIN_RETAIN_EDGE_PERCENT):+.2f}%\n"
            + f"허용 슬리피지: {safe_float(signal.get('allowed_slippage_percent')):.2f}%\n"
            + f"국내 최종벽: {fmt_man_krw(signal.get('spot_wall_krw'))}\n"
            + f"해외 최종벽: {fmt_man_krw(signal.get('futures_wall_krw'))}\n"
            + f"거래소MAX: {fmt_man_krw(signal.get('futures_position_limit_krw'))}\n"
            + f"남은 가능금액: {fmt_man_krw(remaining_after)}\n"
            + f"포지션ID: {pos_id}\n\n"
            + f"자동익절: 실제엣지 {AUTO_TAKE_PROFIT_EDGE_PERCENT:+.2f}% 이하 유연 청산\n"
            + f"1차 경고: 진입엣지 +{AUTO_WARN_EDGE_ADD_PERCENT:.2f}%p\n"
            + f"2차 강경고: 진입엣지 +{AUTO_STRONG_WARN_EDGE_ADD_PERCENT:.2f}%p\n"
            + f"자동손절: 진입엣지 +{AUTO_STOP_WATCH_EDGE_ADD_PERCENT:.2f}%p 이상 {AUTO_STOP_HOLD_SEC // 60}분 유지\n\n"
            + "※ 이 코인을 보유 중인 동안 같은 코인의 신규 진입 알림은 받지 않고, 청산/경고 알림만 받습니다.\n"
            + (
                "실제 주문 OFF / API·잔고 검사 SKIP\n"
                "가상 진입 데이터가 저장되었습니다."
                if not REAL_ORDER_ENABLED else
                "실제 주문 함수 연결 후 이 단계에서 현물 매수 + 선물 숏 진입이 실행됩니다."
            )
        )
        return

    if action == "CANCEL":
        telegram_answer_callback(cb_id, "취소 완료")
        telegram_edit_message(chat_id, message_id, build_member_dm_message(signal, selected), build_entry_keyboard(signal_id))
        return




def send_startup_test_dm_to_approved_members() -> None:
    """테스트용 실행 시작 알림.

    목적:
    - 양방 후보가 실제로 뜰 때까지 기다리지 않아도, 승인회원 DM 통로가 살아있는지 바로 확인한다.
    - 기존 연결완료 DM의 connected_members 중복방지와 완전히 분리한다.
    - 실시간 신호/청산/알림 엔진은 건드리지 않는다.
    """
    if not SEND_STARTUP_TEST_DM:
        print("[자동모드시작DM] 비활성화")
        return

    members = supabase_get_approved_members(force_refresh=True)
    if not members:
        print("[자동모드시작DM] 대상 없음 또는 Supabase 미설정")
        return

    sent_tg_ids = set()
    ok_count = 0
    fail_count = 0
    skip_count = 0

    text = f"""🤖 K-EDGE V8.8 감지즉시 자동진입 가상테스트 실행

봇이 정상 실행되었습니다.

현재 모드:
- 자동진입: ON
- 실제주문: OFF
- 실전가상 저장: ON
- 자동진입 금액: 10만원 고정

이 메시지가 오면:
- Supabase 승인회원 조회 정상
- tg_chat_id 읽기 정상
- 개인 DM 봇 전송 정상

실시간 양방 신호가 조건을 통과하면
버튼 선택 없이 자동으로 10만원 가상진입 저장됩니다.

저장 위치:
paper_trading_data/paper_entries.csv

⚠️ 아래 🛑 자동매매 정지를 누르면:
- 신규 자동진입 중단
- 현재 ACTIVE 포지션 전체 종료 처리
- 가상테스트에서는 종료 기록만 저장

🕒 {now_str()}"""

    for member in members:
        tg_id = get_member_chat_id(member)
        if not tg_id:
            print("[자동모드시작DM SKIP] tg_chat_id/chat_id 없음", member.get("id"), member.get("email"))
            skip_count += 1
            continue
        tg_id = str(tg_id).strip()
        if tg_id in sent_tg_ids:
            print(f"[자동모드시작DM SKIP] 중복 tg_chat_id {tg_id}")
            skip_count += 1
            continue
        sent_tg_ids.add(tg_id)

        ok = _telegram_send_with_keyboard(SEMI_AUTO_BOT_TOKEN, tg_id, text, build_stop_keyboard("GLOBAL"), "자동모드시작DM")
        if ok:
            ok_count += 1
        else:
            fail_count += 1

    print(f"[자동모드시작DM 결과] 성공={ok_count} / 실패={fail_count} / 스킵={skip_count}")

def sync_approved_member_telegram_connection() -> None:
    """
    관리자 페이지에서 승인된 회원을 Supabase에서 읽어와
    최초 1회 개인 텔레그램 DM으로 연결 완료/테스트 메시지를 보낸다.

    동작 조건:
    - 홈페이지 관리자 승인 버튼이 Supabase 회원 테이블의 status=approved 로 변경
    - 해당 row에 telegram_id 또는 telegram_user_id 또는 chat_id 존재
    - 사용자가 봇에게 /start 를 한 번 눌러 DM 수신 가능 상태
    """
    members = supabase_get_approved_members()
    if not members:
        return

    state = _read_semi_state()
    connected = state.setdefault("connected_members", {})
    changed = False

    for member in members:
        tg_id = get_member_chat_id(member)
        if not tg_id:
            print("[승인회원 SKIP] tg_chat_id/chat_id 없음", member)
            continue

        tg_id = str(tg_id)
        if connected.get(tg_id) and not FORCE_APPROVAL_DM_EVERY_START:
            print(f"[승인회원 이미 연결됨 - 스킵] telegram_id={tg_id}")
            continue
        elif connected.get(tg_id) and FORCE_APPROVAL_DM_EVERY_START:
            print(f"[승인회원 재전송 테스트] telegram_id={tg_id}")

        name = member.get("name") or member.get("nickname") or member.get("display_name") or "승인회원"
        plan = "AUTO-PAPER-100K"  # V8.5: SEMI 등 기존 상품명 대신 자동가상테스트 라벨 고정

        text = f"""✅ K-EDGE 완전자동 연결 완료

{name}님 승인 확인되었습니다.
상품: {plan}

현재 모드:
- 자동진입 ON
- 실제주문 OFF
- 실전가상 저장 ON
- 자동진입 금액 10만원 고정

양방 조건이 뜨면 이 개인 텔레그램으로
금액 선택 없이 자동 재검사 후 진입 결과가 전송됩니다.

※ 안내
@Kedge0203bot /start가 되어 있어야 개인 알림과 정지 버튼이 작동합니다.

버튼:
🛑 자동매매 정지

정지 시:
- 신규 자동진입 중단
- 현재 보유 중인 가상 포지션 전체 종료 처리
- 실전 전환 시에는 국내 현물 매도 + 해외 선물 청산 대상

반자동 금액버튼 / [진입 실행] 버튼은 사용하지 않습니다.

🕒 {now_str()}"""

        ok = _telegram_send_with_keyboard(SEMI_AUTO_BOT_TOKEN, tg_id, text, build_stop_keyboard("GLOBAL"), "완전자동연결DM")
        if ok:
            connected[tg_id] = {
                "connected_at": now_str(),
                "telegram_id": tg_id,
                "plan": plan,
            }
            changed = True
            print(f"[승인회원 연결 완료] telegram_id={tg_id}")
        else:
            print(f"[승인회원 연결 실패] telegram_id={tg_id} - 사용자가 봇 /start 필요 가능")

    if changed:
        _write_semi_state(state)

def poll_semi_auto_updates() -> None:
    """텔레그램 버튼(callback_query)을 빠르게 처리한다."""
    global last_update_id
    if not SEMI_AUTO_BOT_TOKEN:
        return

    try:
        url = f"https://api.telegram.org/bot{SEMI_AUTO_BOT_TOKEN}/getUpdates"
        params = {
            "offset": last_update_id + 1 if last_update_id else None,
            "timeout": 1,
            "allowed_updates": json.dumps(["callback_query"]),
        }
        r = session.get(url, params={k: v for k, v in params.items() if v is not None}, timeout=5)
        data = r.json()
        if not data.get("ok"):
            return

        for upd in data.get("result", []):
            last_update_id = max(last_update_id, int(upd.get("update_id", 0)))
            if "callback_query" in upd:
                process_callback_query(upd["callback_query"])
    except Exception as e:
        print("[반자동 업데이트 처리 예외]", e)


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
    funding_rate_percent: Optional[float] = None,
) -> str:
    """
    무료방용 요약 알림.
    FREE는 유입용이므로 후보/국내/해외/예상 수익구간만 제공한다.
    펀딩/벽/실체결/손절/종료 정보는 VIP 전용.
    """
    return f"""⚖️ 양방 후보

코인: {spot['symbol']}

국내: {spot['source']}
해외: {future_ex_name}

예상 수익구간:
{edge_percent:+.2f}%

🕒 {now_str()}
"""


# USD/KRW 환율 캐시 - 국내 USDT/KRW는 김프/역프가 섞일 수 있어서 사용하지 않음.
USD_KRW_CACHE_TTL_SEC = int(os.getenv("USD_KRW_CACHE_TTL_SEC", "30"))
_USD_KRW_CACHE_VALUE: float = 0.0
_USD_KRW_CACHE_AT: float = 0.0
_USD_KRW_CACHE_SOURCE: str = ""


def get_usd_krw_source() -> str:
    return _USD_KRW_CACHE_SOURCE or "unknown"


def _read_fx_file_cache(now_ts: Optional[float] = None) -> Optional[float]:
    global _USD_KRW_CACHE_SOURCE
    now_ts = now_ts or time.time()
    try:
        data = _read_json(FX_CACHE_PATH, {})
        value = safe_float(data.get("usd_krw"))
        ts = safe_float(data.get("ts"))
        if 1000 <= value <= 2500 and now_ts - ts < FX_FILE_CACHE_TTL_SEC:
            _USD_KRW_CACHE_SOURCE = "file_cache:" + str(data.get("source") or "unknown")
            return value
    except Exception:
        pass
    return None


def _write_fx_file_cache(value: float, source: str) -> None:
    try:
        _write_json_atomic(FX_CACHE_PATH, {"usd_krw": float(value), "source": source, "ts": time.time(), "updated_at": now_str()})
    except Exception as e:
        print("[환율 파일캐시 저장 실패]", e)


def _acquire_fx_lock() -> bool:
    try:
        if os.path.exists(FX_CACHE_LOCK_PATH):
            age = time.time() - os.path.getmtime(FX_CACHE_LOCK_PATH)
            if age < FX_LOCK_STALE_SEC:
                return False
            try:
                os.remove(FX_CACHE_LOCK_PATH)
            except Exception:
                pass
        fd = os.open(FX_CACHE_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def _release_fx_lock() -> None:
    try:
        if os.path.exists(FX_CACHE_LOCK_PATH):
            os.remove(FX_CACHE_LOCK_PATH)
    except Exception:
        pass


def fetch_usd_krw() -> float:
    """
    V9.2 환율 캐시락:
    - 4파일 동시 실행 시 fx_cache.json을 먼저 읽는다.
    - 캐시가 없고 lock 획득한 파일만 Yahoo Finance 호출.
    - lock 미획득 파일은 잠깐 대기 후 파일캐시/마지막성공/fallback 순서 사용.
    """
    global _USD_KRW_CACHE_VALUE, _USD_KRW_CACHE_AT, _USD_KRW_CACHE_SOURCE

    now_ts = time.time()

    if _USD_KRW_CACHE_VALUE > 1000 and now_ts - _USD_KRW_CACHE_AT < USD_KRW_CACHE_TTL_SEC:
        base_source = _USD_KRW_CACHE_SOURCE.replace("cache:", "").replace("last_success:", "")
        _USD_KRW_CACHE_SOURCE = f"cache:{base_source}"
        return _USD_KRW_CACHE_VALUE

    file_cached = _read_fx_file_cache(now_ts)
    if file_cached:
        _USD_KRW_CACHE_VALUE = file_cached
        _USD_KRW_CACHE_AT = now_ts
        return file_cached

    got_lock = _acquire_fx_lock()
    if not got_lock:
        # 다른 파일이 Yahoo 호출 중. 1.2초만 기다린 뒤 파일캐시 재확인.
        time.sleep(1.2)
        file_cached = _read_fx_file_cache(time.time())
        if file_cached:
            _USD_KRW_CACHE_VALUE = file_cached
            _USD_KRW_CACHE_AT = time.time()
            return file_cached
        if _USD_KRW_CACHE_VALUE > 1000:
            _USD_KRW_CACHE_SOURCE = "last_success:memory_wait_lock"
            return _USD_KRW_CACHE_VALUE
        fallback = safe_float(globals().get("MANUAL_USD_KRW", FALLBACK_USD_KRW), FALLBACK_USD_KRW)
        _USD_KRW_CACHE_SOURCE = "manual_fallback:lock_wait"
        return fallback

    try:
        if yf is None:
            raise RuntimeError("yfinance 미설치 또는 import 실패")
        ticker = yf.Ticker("USDKRW=X")
        data = ticker.history(period="1d", interval="1m")
        if data is not None and len(data) > 0:
            krw = safe_float(data["Close"].iloc[-1])
            if 1000 <= krw <= 2500:
                _USD_KRW_CACHE_VALUE = krw
                _USD_KRW_CACHE_AT = time.time()
                _USD_KRW_CACHE_SOURCE = "yahoo:USDKRW=X"
                _write_fx_file_cache(krw, _USD_KRW_CACHE_SOURCE)
                return krw
            print("[환율API Yahoo 비정상값]", krw)
        else:
            print("[환율API Yahoo 응답 없음] USDKRW=X")
    except Exception as e:
        print("[환율API Yahoo 실패]", e)
    finally:
        _release_fx_lock()

    file_cached = _read_fx_file_cache(time.time())
    if file_cached:
        _USD_KRW_CACHE_VALUE = file_cached
        _USD_KRW_CACHE_AT = time.time()
        return file_cached
    if _USD_KRW_CACHE_VALUE > 1000:
        base_source = _USD_KRW_CACHE_SOURCE.replace("cache:", "").replace("last_success:", "")
        _USD_KRW_CACHE_SOURCE = f"last_success:{base_source}"
        return _USD_KRW_CACHE_VALUE
    fallback = safe_float(globals().get("MANUAL_USD_KRW", FALLBACK_USD_KRW), FALLBACK_USD_KRW)
    _USD_KRW_CACHE_SOURCE = "manual_fallback"
    return fallback


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



def calc_allowed_slippage_percent(edge_percent: float) -> float:
    """현재 실제엣지가 최소 유지엣지 1.5% 이상 남도록 허용 가능한 슬리피지."""
    return max(0.0, safe_float(edge_percent) - safe_float(MIN_RETAIN_EDGE_PERCENT))


def build_slippage_ranges(allowed_pct: float) -> List[float]:
    """0.5%, 1.0% ... 허용 슬리피지까지 표시. 2.1%면 0.1%만 표시."""
    allowed = round(max(0.0, safe_float(allowed_pct)), 4)
    if allowed <= 0:
        return []
    step = max(0.1, safe_float(DYNAMIC_SLIPPAGE_STEP_PERCENT, 0.5))
    vals: List[float] = []
    cur = step
    while cur < allowed - 1e-9:
        vals.append(round(cur, 4))
        cur += step
    # 허용값이 0.5 단위와 정확히 같지 않으면 마지막에 정확한 허용값 표시
    if not vals or abs(vals[-1] - allowed) > 1e-9:
        vals.append(round(allowed, 4))
    return vals


def build_dynamic_slippage_tiers_text(
    spot_asks: List[List[float]],
    spot_best_ask: float,
    futures_bids: List[List[float]],
    futures_best_bid: float,
    usd_krw: float,
    allowed_pct: float,
    futures_position_limit_krw: float,
    spot_quote: str = "KRW",
) -> Tuple[str, float, float, float]:
    """허용 슬리피지 구간별 국내/해외 체결 가능금액 표시용 텍스트 생성."""
    ranges = build_slippage_ranges(allowed_pct)
    if not ranges:
        return "허용 슬리피지 없음", 0.0, 0.0, 0.0

    lines = []
    last_spot_krw = 0.0
    last_future_krw = 0.0
    last_final_krw = 0.0

    for r in ranges:
        spot_wall = sum_ask_wall_quote(spot_asks, spot_best_ask, r)
        spot_wall_krw = spot_wall if str(spot_quote).upper() == "KRW" else spot_wall * usd_krw
        future_wall_krw = sum_bid_wall_quote(futures_bids, futures_best_bid, r) * usd_krw
        final_krw = min(
            safe_float(spot_wall_krw),
            safe_float(future_wall_krw),
            safe_float(futures_position_limit_krw, 10**18),
        )
        last_spot_krw = spot_wall_krw
        last_future_krw = future_wall_krw
        last_final_krw = final_krw
        lines.append(
            f"{r:.2f}%: 국내 {fmt_man_krw(spot_wall_krw)} / 해외 {fmt_man_krw(future_wall_krw)} / 최종 {fmt_man_krw(final_krw)}"
        )

    return "\n".join(lines), last_spot_krw, last_future_krw, last_final_krw


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

    print("[해외 현물 등록] 스킵 - 국내 현물 -> 해외 선물 전용")

    for name, ccxt_id in FUTURES_EXCHANGES:
        try:
            # 대부분 swap이 USDT 무기한 선물
            ex = init_exchange(name, ccxt_id, "swap")
            future_exs[name] = ex
            print(f"[해외 선물 등록] {name} / 마켓 {len(ex.markets)}개")
        except Exception as e:
            print(f"[해외 선물 등록 실패] {name}: {e}")

    return spot_exs, future_exs


def init_callback_future_exs(scan_future_exs: Dict[str, Any]) -> Dict[str, Any]:
    """AUTO 정지 버튼 진입 재검사용 선물 객체.

    4파일 모드에서는 버튼 callback poller를 MEXC 파일 1개만 켠다.
    따라서 MEXC 파일이 BINGX/GATE/BITGET 신호 버튼도 처리할 수 있어야 한다.
    스캔은 각 파일의 단일 거래소만 유지하고, callback 재검사용 객체만 4개를 모두 로딩한다.
    """
    out = dict(scan_future_exs or {})
    if not ENABLE_CALLBACK_POLLER:
        return out

    for name, ccxt_id in CALLBACK_FUTURES_EXCHANGES:
        if name in out:
            continue
        try:
            ex = init_exchange(name, ccxt_id, "swap")
            out[name] = ex
            print(f"[반자동 재검사용 선물 등록] {name} / 마켓 {len(ex.markets)}개")
        except Exception as e:
            print(f"[반자동 재검사용 선물 등록 실패] {name}: {e}")

    print("[반자동 재검사용 선물 객체]", sorted(out.keys()))
    return out


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


def _record_api_speed(exchange_name: str, market: str, elapsed: float, ok: bool, error: str = "") -> None:
    """거래소 API 속도 기록.

    V9.2.1 수정:
    - 정상/빠른 호출은 기본 저장하지 않는다.
    - 느린 호출 또는 실패만 api_speed_log.csv에 조용히 저장한다.
    - _csv_append를 쓰지 않아 [CSV 저장 성공] 로그 도배가 발생하지 않는다.
    - 모든 호출 저장이 필요하면 CMD에서 set API_SPEED_LOG_SAVE_NORMAL=true 로 켠다.
    """
    if not API_SPEED_LOG_ENABLED:
        return

    slow_or_fail = (elapsed >= API_SLOW_WARN_SEC) or (not ok)
    if API_SPEED_LOG_ONLY_SLOW and not slow_or_fail and not API_SPEED_LOG_SAVE_NORMAL:
        return

    try:
        if slow_or_fail:
            print(f"[API속도] {exchange_name} {market} {elapsed:.2f}s ok={ok} {error[:120]}")

        _ensure_paper_data_dir()
        exists = os.path.exists(API_SPEED_CSV)
        fieldnames = ["time", "exchange", "market", "elapsed_sec", "ok", "error"]
        with open(API_SPEED_CSV, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow({
                "time": now_str(),
                "exchange": exchange_name,
                "market": market,
                "elapsed_sec": round(elapsed, 4),
                "ok": ok,
                "error": str(error or "")[:500],
            })
    except Exception:
        pass


def fetch_ccxt_book(ex: Any, market: str, is_future: bool = False) -> Optional[Dict[str, Any]]:
    t0 = time.time()
    ex_name = str(getattr(ex, "id", "UNKNOWN")).upper()
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

        funding_rate_percent = None
        next_funding_time = None
        if is_future:
            try:
                fr = ex.fetch_funding_rate(market)
                raw_rate = fr.get("fundingRate")
                if raw_rate is not None:
                    funding_rate_percent = safe_float(raw_rate) * 100.0
                next_funding_time = fr.get("fundingDatetime") or fr.get("nextFundingDatetime")
            except Exception:
                funding_rate_percent = None

        elapsed = time.time() - t0
        _record_api_speed(ex_name, market, elapsed, True)
        return {
            "market": market,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "volume_usdt": volume_usdt,
            "funding_rate_percent": funding_rate_percent,
            "next_funding_time": next_funding_time,
            "bids": bids,
            "asks": asks,
        }
    except Exception as e:
        _record_api_speed(ex_name, market, time.time() - t0, False, str(e))
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
    ]

    all_items = []
    for fn, limit in funcs:
        if int(limit) <= 0:
            print(f"[국내 현물] {fn.__name__}: SKIP / 검사 0개")
            continue
        items = fn()
        items.sort(key=lambda x: x.get("volume_krw", 0), reverse=True)
        limited = items[:limit]
        print(f"[국내 현물] {fn.__name__}: {len(items)}개 → 검사 {len(limited)}개")
        all_items.extend(limited)

    # 업비트가 대형주 위주라 거래대금 단순 정렬에서 밀리면 알람이 거의 안 뜰 수 있음.
    # 업비트 우선 → 빗썸 → 코인원 순서로 보되, 각 거래소 안에서는 거래대금 높은 순.
    source_rank = {"UPBIT": 0, "BITHUMB": 1}
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
        spot_price_text = f"{spot['best_ask']:,.8f} KRW"
        spot_wall_text = fmt_krw(spot_wall_krw)
        spot_volume_text = fmt_krw(spot.get("volume_krw", 0))
    else:
        spot_price_text = f"{spot['best_ask']:,.8f} USDT / {spot['best_ask'] * usd_krw:,.8f} KRW"
        spot_wall_text = f"{fmt_usdt(spot_wall_krw / usd_krw)} / {fmt_krw(spot_wall_krw)}"
        spot_volume_text = f"{fmt_usdt(spot.get('volume_quote', 0))} / {fmt_krw(spot.get('volume_krw', 0))}"

    future_price_krw = future["best_bid"] * usd_krw
    btc_source_suffix = f" ({future.get('btc_basis_source')} 기준 대체)" if future.get("btc_basis_source") else ""

    text = f"""⚖️ 현물-선물 양방 후보

코인: {symbol}
전략: 현물 매수 + 선물 숏

━━━━━━━━━━━━━━

현물

거래소: {spot['source']}
마켓: {spot['market']}

매수 기준:
{spot_price_text}

스프레드:
{spot['spread']:.2f}%

24h 거래대금:
{spot_volume_text}

━━━━━━━━━━━━━━

선물

거래소: {future_ex_name}
마켓: {future['market']}

숏 기준:
{future['best_bid']:.8f} USDT / {future_price_krw:,.8f} KRW

스프레드:
{future['spread']:.2f}%

24h 거래대금:
{fmt_usdt(future.get('volume_usdt', 0))}

펀딩비:
{format_funding_rate(future.get('funding_rate_percent'))}

━━━━━━━━━━━━━━

괴리율:
{basis_percent:+.2f}%

BTC 기준 프리미엄:
{btc_basis_percent:+.2f}%{btc_source_suffix}

💰 예상 수익구간:
{edge_percent:+.2f}%

현물벽:
{spot_wall_text}

선물벽:
{fmt_usdt(future_wall_krw / usd_krw)} / {fmt_krw(future_wall_krw)}

실체결 가능금액:
{fmt_usdt(real_fill_krw / usd_krw)} / {fmt_krw(real_fill_krw)}

━━━━━━━━━━━━━━

권장 레버리지

{RECOMMENDED_LEVERAGE_TEXT}

손절 기준

예상 수익구간 +{STOP_EDGE_ADD_PERCENT:.1f}%

예상 손절구간:
{edge_percent + STOP_EDGE_ADD_PERCENT:+.2f}%

━━━━━━━━━━━━━━

📌 해석

선물이 현물보다 높게 거래 중입니다.

BTC 프리미엄 차감 후
실제 수익 가능 구간 기준으로 선별했습니다.

주의:
수수료 / 슬리피지 / 입출금 가능 여부 /
실제 주문 가능 수량에 따라 결과는 달라질 수 있습니다.

레버리지는 x1 기본,
공격적으로 잡아도 x2까지만 권장합니다.

🕒 {now_str()}
"""
    return text



# ============================================================
# V8.5 초고속 병렬 스캔
# - 140개를 4개 워커로 분할 검사
# - 후보 발견 즉시 자동진입 먼저 호출
# - 반자동 후보/금액버튼 DM 완전 차단 유지
# ============================================================
def scan_once(spot_exs: Dict[str, Any], future_exs: Dict[str, Any]) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    usd_krw = fetch_usd_krw()
    print(f"[국제환율] USD/KRW = {usd_krw:.2f} / source={get_usd_krw_source()} / ttl={USD_KRW_CACHE_TTL_SEC}s")

    domestic_spots = fetch_all_domestic_spots()
    domestic_symbols = sorted(set(x["symbol"] for x in domestic_spots))
    print(f"[국내 심볼] {len(domestic_symbols)}개")
    print("[해외 현물] 완전 제외 - 국내 현물 -> 해외 선물만 검사")

    source_rank = {"UPBIT": 0, "BITHUMB": 1}
    all_spots = list(domestic_spots)
    all_spots.sort(key=lambda x: (source_rank.get(x.get("source", ""), 99), -x.get("volume_krw", 0)))
    all_spots = all_spots[:MAX_SPOT_ITEMS]
    print(f"[최종 검사 현물] {len(all_spots)}개")

    btc_baseline_map = build_btc_baseline_map(domestic_spots, future_exs, usd_krw)

    workers = int(os.getenv("KEDGE_FAST_SCAN_WORKERS", "4"))
    workers = max(1, min(workers, 12))
    print(f"[V8.8 병렬스캔] workers={workers} / 대상={len(all_spots)}개 / 자동진입금액={fmt_man_krw(AUTO_ENTRY_DEFAULT_KRW)}")

    dispatch_lock = threading.Lock()
    stats_lock = threading.Lock()
    cut_stats: Dict[str, int] = {
        "전체대상": len(all_spots),
        "선물마켓없음": 0,
        "동일거래소제외": 0,
        "호가조회실패": 0,
        "심볼불일치": 0,
        "해외거래량부족": 0,
        "BTC기준없음": 0,
        "실제엣지부족": 0,
        "펀딩초과": 0,
        "이상괴리": 0,
        "허용슬리피지없음": 0,
        "현물벽부족": 0,
        "선물벽부족": 0,
        "실체결부족": 0,
        "최종진입금액부족": 0,
        "쿨다운": 0,
        "동일조합쿨다운": 0,
        "정밀검사": 0,
        "알림": 0,
    }
    edge_top: List[Tuple[float, str, str, str, float, float]] = []

    def cut(reason: str, n: int = 1) -> None:
        with stats_lock:
            cut_stats[reason] = int(cut_stats.get(reason, 0)) + int(n)

    def record_edge(edge: float, base: str, domestic: str, foreign: str, basis: float, btc_basis: float) -> None:
        # 2%에 못 미쳐도 가장 가까운 후보를 보기 위한 TOP 로그
        with stats_lock:
            edge_top.append((float(edge), str(base), str(domestic), str(foreign), float(basis), float(btc_basis)))
            edge_top.sort(key=lambda x: x[0], reverse=True)
            del edge_top[10:]

    def process_one_spot(spot: Dict[str, Any]) -> Tuple[int, int]:
        checked_local = 0
        alerts_local = 0
        base = spot.get("symbol", "")
        try:
            if spot.get("quote") == "KRW":
                spot_ask_usdt = spot.get("best_ask", 0) / usd_krw
            else:
                spot_ask_usdt = spot.get("best_ask", 0)
            if spot_ask_usdt <= 0:
                return checked_local, alerts_local

            for future_ex_name, fex in future_exs.items():
                try:
                    fmarket = find_future_market(fex, base)
                    if not fmarket:
                        cut("선물마켓없음")
                        continue
                    if not ALLOW_SAME_EXCHANGE_BASIS and spot.get("source") == future_ex_name:
                        cut("동일거래소제외")
                        continue

                    future = fetch_ccxt_book(fex, fmarket, is_future=True)
                    if not future:
                        cut("호가조회실패")
                        continue
                    if not strict_same_base(spot, fmarket, fex):
                        cut("심볼불일치")
                        print(f"[심볼불일치 제외] spot={spot.get('source')} {spot.get('market')} / future={future_ex_name} {fmarket}")
                        continue
                    if future.get("volume_usdt") and future.get("volume_usdt") < MIN_FOREIGN_VOLUME_USDT:
                        cut("해외거래량부족")
                        continue

                    checked_local += 1
                    cut("정밀검사")
                    basis = calc_basis_percent(future["best_bid"], spot_ask_usdt)
                    btc_basis, btc_basis_source = get_btc_baseline_for_source(
                        btc_baseline_map, spot.get("source", ""), future_ex_name
                    )
                    if btc_basis is None:
                        if REQUIRE_BTC_BASELINE:
                            cut("BTC기준없음")
                            continue
                        btc_basis = 0.0
                        btc_basis_source = "NONE"
                    if btc_basis_source and btc_basis_source != spot.get("source"):
                        future["btc_basis_source"] = btc_basis_source

                    edge = basis - btc_basis
                    funding_rate_percent = future.get("funding_rate_percent")

                    # 기존 ACTIVE 포지션 청산/손절 감시는 유지
                    try:
                        check_semi_auto_auto_close(base, spot.get("source", ""), future_ex_name, edge, funding_rate_percent)
                    except Exception:
                        pass

                    lock_key = make_active_lock_key(base, spot.get("source", ""), future_ex_name)
                    if active_symbol_locks.get(lock_key):
                        active_lock_check(base, spot.get("source", ""), future_ex_name, edge, funding_rate_percent)
                        continue

                    record_edge(edge, base, spot.get("source", ""), future_ex_name, basis, btc_basis)
                    if edge < MIN_EDGE_PERCENT:
                        cut("실제엣지부족")
                        continue
                    if funding_rate_percent is not None and funding_rate_percent >= MAX_FUNDING_RATE_PERCENT:
                        cut("펀딩초과")
                        print(f"[펀딩과열 제외] {spot.get('source')} {base} -> {future_ex_name} funding={funding_rate_percent:+.4f}% / 기준={MAX_FUNDING_RATE_PERCENT:+.4f}%")
                        continue
                    if basis > MAX_REASONABLE_BASIS_PERCENT:
                        cut("이상괴리")
                        print(f"[이상괴리 제외] {spot.get('source')} {base} -> {future_ex_name} basis={basis:.2f}% edge={edge:.2f}%")
                        continue

                    futures_position_limit_krw, limit_source = fetch_futures_position_limit_krw(
                        future_ex_name=future_ex_name,
                        fex=fex,
                        market=fmarket,
                        symbol=base,
                        usd_krw=usd_krw,
                        best_bid=future["best_bid"],
                    )

                    allowed_slippage = calc_allowed_slippage_percent(edge)
                    slippage_tiers_text, spot_wall_krw, future_wall_krw, dynamic_fill_krw = build_dynamic_slippage_tiers_text(
                        spot["asks"], spot["best_ask"], future["bids"], future["best_bid"], usd_krw,
                        allowed_slippage, futures_position_limit_krw, spot.get("quote", "KRW")
                    )

                    real_fill_krw = min(spot_wall_krw, future_wall_krw)
                    final_entry_krw = min(dynamic_fill_krw, futures_position_limit_krw)
                    if MAX_USER_ENTRY_KRW > 0:
                        final_entry_krw = min(final_entry_krw, MAX_USER_ENTRY_KRW)

                    if allowed_slippage <= 0:
                        cut("허용슬리피지없음")
                        continue
                    if spot_wall_krw < MIN_SPOT_WALL_KRW:
                        cut("현물벽부족")
                        continue
                    if future_wall_krw < MIN_FUTURES_WALL_KRW:
                        cut("선물벽부족")
                        continue
                    if real_fill_krw < MIN_REAL_FILL_KRW:
                        cut("실체결부족")
                        continue
                    if final_entry_krw < MIN_REAL_FILL_KRW:
                        cut("최종진입금액부족")
                        print(f"[최종진입금액 부족 제외] {spot.get('source')} {base} -> {future_ex_name} final={fmt_krw(final_entry_krw)} / 허용슬리피지={allowed_slippage:.2f}% / max_limit_source={limit_source}")
                        continue

                    key = f"BASIS:{spot.get('source')}:{spot.get('market')}:{future_ex_name}:{fmarket}"
                    # 쿨다운/전송/저장은 동시에 여러 워커가 들어오면 꼬일 수 있으므로 잠금 안에서 처리
                    with dispatch_lock:
                        if not cooldown_ok(key):
                            cut("쿨다운")
                            continue
                        if not symbol_cooldown_ok(base, spot.get("source", ""), future_ex_name):
                            cut("동일조합쿨다운")
                            print(f"[동일조합 쿨다운 제외] {base} / {spot.get('source')} -> {future_ex_name}")
                            continue

                        expected_min, expected_max = calc_expected_profit_range(edge)
                        signal_id = make_signal_id(base, spot.get("source", ""), future_ex_name)
                        signal_row = {
                            "signal_id": signal_id,
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
                            "expected_profit_min": round(expected_min, 2),
                            "expected_profit_max": round(expected_max, 2),
                            "funding_rate": None if future.get("funding_rate_percent") is None else round(future.get("funding_rate_percent"), 4),
                            "recommended_leverage": RECOMMENDED_LEVERAGE_TEXT,
                            "stop_edge": round(edge + STOP_EDGE_ADD_PERCENT, 2),
                            "spot_wall_krw": round(spot_wall_krw),
                            "futures_wall_krw": round(future_wall_krw),
                            "real_fill_krw": round(real_fill_krw),
                            "futures_position_limit_krw": round(futures_position_limit_krw),
                            "futures_position_limit_source": limit_source,
                            "min_retain_edge_percent": round(MIN_RETAIN_EDGE_PERCENT, 2),
                            "allowed_slippage_percent": round(allowed_slippage, 2),
                            "slippage_tiers_text": slippage_tiers_text,
                            "max_user_entry_krw": MAX_USER_ENTRY_KRW,
                            "paper_domestic_base_krw": PAPER_DOMESTIC_BASE_KRW,
                            "paper_foreign_margin_base_krw": PAPER_FOREIGN_MARGIN_BASE_KRW_BY_EXCHANGE.get(future_ex_name, 0),
                            "paper_futures_leverage": PAPER_FUTURES_LEVERAGE,
                            "roundtrip_fee_percent": calc_roundtrip_fee_percent(),
                            "funding_simulation_enabled": FUNDING_SIMULATION_ENABLED,
                            "max_entry_krw": round(final_entry_krw),
                            "final_entry_krw": round(final_entry_krw),
                            "used_entry_krw": 0,
                            "remaining_entry_krw": round(final_entry_krw),
                            "wall_range_percent": round(allowed_slippage, 4),
                            "executable_krw": round(final_entry_krw),
                            "krw": round(final_entry_krw),
                            "usd_krw": round(usd_krw, 4),
                            "entry_status": "READY",
                            "status": "V8.8_FAST_PAPER_ENTRY",
                        }

                        msg = build_compact_vip_message_from_signal(signal_row)
                        print(msg)
                        save_signal_state(signal_id, signal_row)
                        print(f"[V8.8 감지즉시 자동진입 호출] {base} / {spot.get('source')} -> {future_ex_name} / signal_id={signal_id}")
                        auto_entry_approved_members(signal_row)

                        vip_sent = telegram_send(msg)
                        if vip_sent:
                            mark_active_lock(base, edge, spot.get("source", ""), future_ex_name)
                            free_msg = build_compact_free_message_from_signal(signal_row)
                            telegram_send_free(free_msg)
                        else:
                            print("[주의] VIP 텔레그램 전송 실패 - 그래도 자동진입/로컬저장은 계속 진행")

                        save_web_signal(signal_row)
                        print(f"[AUTO 후보 버튼DM 차단 완료] {base} / {spot.get('source')} -> {future_ex_name} / signal_id={signal_id}")
                        print("[홈페이지 자동 PUSH] 4파일 분리 테스트 모드 - 스킵")
                        alerts_local += 1
                        cut("알림")

                except Exception as e:
                    # 워커 하나 오류가 전체 스캔을 죽이지 않게 한다.
                    continue
        except Exception:
            return checked_local, alerts_local
        return checked_local, alerts_local

    checked = 0
    alerts = 0
    started_at = time.time()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_one_spot, spot) for spot in all_spots]
        for fut in as_completed(futures):
            try:
                c, a = fut.result()
                checked += c
                alerts += a
            except Exception:
                continue

    elapsed = time.time() - started_at

    with stats_lock:
        stats_snapshot = dict(cut_stats)
        top_snapshot = list(edge_top)

    print("[V8.7 컷통계]")
    print(
        f"전체 {stats_snapshot.get('전체대상', 0)} / "
        f"정밀검사 {stats_snapshot.get('정밀검사', 0)} / "
        f"알림 {stats_snapshot.get('알림', 0)}"
    )
    print(
        f"선물마켓없음 {stats_snapshot.get('선물마켓없음', 0)} / "
        f"호가실패 {stats_snapshot.get('호가조회실패', 0)} / "
        f"심볼불일치 {stats_snapshot.get('심볼불일치', 0)} / "
        f"해외거래량부족 {stats_snapshot.get('해외거래량부족', 0)}"
    )
    print(
        f"BTC기준없음 {stats_snapshot.get('BTC기준없음', 0)} / "
        f"실제엣지부족 {stats_snapshot.get('실제엣지부족', 0)} / "
        f"펀딩초과 {stats_snapshot.get('펀딩초과', 0)} / "
        f"이상괴리 {stats_snapshot.get('이상괴리', 0)}"
    )
    print(
        f"허용슬리피지없음 {stats_snapshot.get('허용슬리피지없음', 0)} / "
        f"현물벽부족 {stats_snapshot.get('현물벽부족', 0)} / "
        f"선물벽부족 {stats_snapshot.get('선물벽부족', 0)} / "
        f"실체결부족 {stats_snapshot.get('실체결부족', 0)} / "
        f"최종진입금액부족 {stats_snapshot.get('최종진입금액부족', 0)}"
    )
    print(
        f"쿨다운 {stats_snapshot.get('쿨다운', 0)} / "
        f"동일조합쿨다운 {stats_snapshot.get('동일조합쿨다운', 0)}"
    )

    if top_snapshot:
        print("[실제엣지 TOP 후보]")
        for i, (edge, sym, dom, foreign, basis, btc_basis) in enumerate(top_snapshot[:5], 1):
            print(f"TOP{i} {sym} {dom}->{foreign} 실제엣지 {edge:+.2f}% / 코인괴리 {basis:+.2f}% / BTC {btc_basis:+.2f}%")
    else:
        print("[실제엣지 TOP 후보] 없음 - BTC기준/호가/마켓 단계에서 대부분 제외")

    print(f"[스캔 완료] 검사 {checked}개 / 알림 {alerts}개 / 소요 {elapsed:.1f}초 / {now_str()}")

def boot_message() -> None:
    msg = f"""✅ 국내 현물 → 해외 선물 괴리 감시봇 - 빠른 테스트 모드 시작

전략:
현물 매수 + 선물 숏 전용

국내 현물:
BITHUMB 전용
속도 모드: 빗썸 140개 / 업비트 제외

해외 현물:
완전 제외

해외 선물:
BINGX 전용
4파일 분리 속도 테스트 모드

기준:
BTC 기준 실제 엣지 +{MIN_EDGE_PERCENT:.1f}% 이상
기존 절대괴리 참고값 +{MIN_BASIS_PERCENT:.1f}%
0.5% 현물벽 {fmt_krw(MIN_SPOT_WALL_KRW)} 이상\n0.5% 선물벽 {fmt_krw(MIN_FUTURES_WALL_KRW)} 이상\n실체결 가능금액 {fmt_krw(MIN_REAL_FILL_KRW)} 이상
국내 거래대금 {fmt_krw(MIN_DOMESTIC_VOLUME_KRW)} 이상
국제 USD/KRW 환율 사용
펀딩비 신규진입 필터: +{MAX_FUNDING_RATE_PERCENT:.4f}% 미만
이벤트형 서포트: 청산 / 손절 / 펀딩주의 발생 시만 알림
완전자동: AUTO 정지 버튼 제거 / 후보 발견 즉시 자동진입 / 고정 10만원 / 가상 저장
자동진입: {"ON" if AUTO_ENTRY_ENABLED else "OFF"} / 복리금액 {fmt_man_krw(calc_domestic_compound_entry_krw())} / 모드 {AUTO_ENTRY_MODE_LABEL}
정지버튼: DM에 표시 / 신규 자동진입 중단 + 현재 포지션 전체 종료 안내 포함 / 반자동 금액버튼 없음
권장 레버리지: {RECOMMENDED_LEVERAGE_TEXT}

🕒 {now_str()}
"""
    telegram_send(msg)
    telegram_send_free("✅ K-EDGE FREE 양방 감시 알림 시작\n\n무료방은 양방 후보와 예상 수익구간만 제공됩니다.\n펀딩 / 실체결 / 벽 / 손절 / 종료 알림은 VIP 전용입니다.\n\n🕒 " + now_str())




def semi_auto_callback_poller_loop() -> None:
    """자동 정지 버튼(callback_query)을 처리한다. V8.3에서는 금액 버튼 없이 정지 버튼만 사용."""
    print("[자동 정지 버튼 폴러] 시작 - STOP 버튼 처리 모드")
    while True:
        try:
            poll_semi_auto_updates()
        except Exception as e:
            print("[자동정지 버튼 폴러 예외]", e)
        time.sleep(0.25)


def start_semi_auto_callback_poller() -> None:
    if not SEMI_AUTO_BOT_TOKEN:
        print("[자동정지 버튼 폴러] SEMI_AUTO_BOT_TOKEN 없음")
        return
    if not ENABLE_CALLBACK_POLLER:
        print("[자동정지 버튼 폴러] 비활성화 - 4파일 모드에서는 MEXC 파일 1개만 STOP 처리")
        return
    th = threading.Thread(target=semi_auto_callback_poller_loop, daemon=True)
    th.start()

def recover_open_positions_from_paper_entries() -> Tuple[int, int]:
    """V9.2 재실행 OPEN 포지션 복구.

    paper_entries.csv의 OPEN/VIRTUAL_OPEN/REAL_OPEN 중 trade_results.csv에 종료 기록이 없는 항목을
    semi_auto_state_*.json positions에 ACTIVE로 재구성한다.
    """
    rows = _read_csv_rows_safe(PAPER_ENTRIES_CSV)
    closed = get_closed_pos_ids_from_results()
    recovered = 0
    skipped = 0
    for r in rows:
        pos_id = str(r.get("pos_id") or "").strip()
        if not pos_id or pos_id in closed:
            skipped += 1
            continue
        status = str(r.get("status") or "").upper().strip()
        if status and status not in OPEN_ENTRY_STATUSES:
            skipped += 1
            continue
        signal_id = str(r.get("signal_id") or "")
        path = _semi_state_path_for_exchange(str(r.get("foreign") or ""))
        state = _read_state_file(path)
        positions = state.setdefault("positions", {})
        if pos_id in positions and str(positions[pos_id].get("status")) == "ACTIVE":
            skipped += 1
            continue
        positions[pos_id] = {
            "pos_id": pos_id,
            "user_id": str(r.get("user_id") or ""),
            "signal_id": signal_id,
            "coin": r.get("coin"),
            "domestic": r.get("domestic"),
            "foreign": r.get("foreign"),
            "domestic_market": r.get("domestic_market"),
            "foreign_market": r.get("foreign_market"),
            "amount_krw": int(safe_float(r.get("entry_krw"))),
            "domestic_entry_krw": int(safe_float(r.get("domestic_entry_krw") or r.get("entry_krw"))),
            "foreign_entry_krw": int(safe_float(r.get("foreign_entry_krw") or r.get("entry_krw"))),
            "entry_edge": safe_float(r.get("entry_edge")),
            "take_profit_edge": AUTO_TAKE_PROFIT_EDGE_PERCENT,
            "take_profit_force_edge": AUTO_TAKE_PROFIT_FORCE_EDGE_PERCENT,
            "warn_edge": safe_float(r.get("entry_edge")) + AUTO_WARN_EDGE_ADD_PERCENT,
            "strong_warn_edge": safe_float(r.get("entry_edge")) + AUTO_STRONG_WARN_EDGE_ADD_PERCENT,
            "stop_watch_edge": safe_float(r.get("entry_edge")) + AUTO_STOP_WATCH_EDGE_ADD_PERCENT,
            "stop_watch_started_at": None,
            "warn_sent": False,
            "strong_warn_sent": False,
            "status": "ACTIVE",
            "opened_at": str(r.get("event_time") or now_str()),
            "real_order": str(r.get("real_order")).lower() == "true",
            "recovered_from_csv": True,
            "recovered_at": now_str(),
        }
        _write_state_file(path, state)
        recovered += 1
    print(f"[V9.2 OPEN복구] recovered={recovered} / skipped={skipped} / open_domestic_sum={fmt_man_krw(get_open_domestic_entry_sum_from_entries_csv())}")
    return recovered, skipped


def main() -> None:
    print("=" * 70)
    print("국내 현물 → 해외 선물 괴리 감시봇 - BITHUMB->BITGET 전용 4파일 속도 모드")
    print("중지: Ctrl + C")
    print("=" * 70)

    if ccxt is None:
        print("ccxt 미설치: py -m pip install ccxt")
        return

    spot_exs, future_exs = init_ccxt_all()
    global GLOBAL_FUTURE_EXS
    GLOBAL_FUTURE_EXS = init_callback_future_exs(future_exs)

    if not future_exs:
        print("선물 거래소 등록 실패")
        return

    recover_open_positions_from_paper_entries()
    boot_message()
    start_semi_auto_callback_poller()
    # V8.5: 초기 DM은 "완전자동 연결 완료" 1개만 보낸다.
    # 기존 자동모드시작DM + 연결완료DM 2중 전송 방지.
    sync_approved_member_telegram_connection()

    while True:
        try:
            # V8.5: 승인회원 연결 DM은 시작 시 1회만 처리한다. 루프 중 반복 DM/반자동 문구 방지.
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
