@echo off
cd /d "%~dp0"

set SUPABASE_URL=https://qakhbihueonefzifrmct.supabase.co
set SUPABASE_SERVICE_KEY=sb_publishable_XboBFueAITcieSL75B2S5g_qlm4XmOm

REM V8.1 실전가상 저장 보강 버전
REM V8 동적 슬리피지 유지
REM 진입 성공 시 paper_trading_data\paper_entries.csv 강제 저장
REM CMD에 [실전가상 기록 준비], [CSV 저장 성공] 로그가 떠야 정상

set REAL_ORDER_ENABLED=false
set PAPER_TRADING_ENABLED=true
set MIN_RETAIN_EDGE_PERCENT=2.0

start "BITHUMB-MEXC-CALLBACK-V81-PAPER" cmd /k "set ENABLE_CALLBACK_POLLER=true&& py domestic_spot_to_foreign_futures_bot_BITHUMB_TO_MEXC_ONLY_SPEED_TEST_DM_STATE_SAFE_SINGLE_CALLBACK_V81_SAVE_FIX.py"
start "BITHUMB-GATE-V81-PAPER" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py domestic_spot_to_foreign_futures_bot_BITHUMB_TO_GATE_ONLY_SPEED_TEST_DM_STATE_SAFE_SINGLE_CALLBACK_V81_SAVE_FIX.py"
start "BITHUMB-BITGET-V81-PAPER" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py domestic_spot_to_foreign_futures_bot_BITHUMB_TO_BITGET_ONLY_SPEED_TEST_DM_STATE_SAFE_SINGLE_CALLBACK_V81_SAVE_FIX.py"
start "BITHUMB-BINGX-V81-PAPER" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py domestic_spot_to_foreign_futures_bot_BITHUMB_TO_BINGX_ONLY_SPEED_TEST_DM_STATE_SAFE_SINGLE_CALLBACK_V81_SAVE_FIX.py"

pause
