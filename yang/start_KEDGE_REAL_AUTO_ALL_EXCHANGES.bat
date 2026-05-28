@echo off
title K-EDGE REAL AUTO ALL EXCHANGES
chcp 65001 >nul

cd /d "%~dp0"

echo ==========================================
echo K-EDGE REAL AUTO ALL EXCHANGES
echo MEXC / GATE / BITGET / BINGX
echo ==========================================

REM 공통 실거래 설정
set REAL_ORDER_ENABLED=true
set PAPER_TRADING_ENABLED=false
set STORAGE_QUEUE_ENABLED=true

REM MEXC 510 완화용. 너무 느리면 0.40, 너무 510 많으면 0.60으로 조절
set MEXC_REQUEST_INTERVAL_SEC=0.50
set MEXC_RATE_LIMIT_COOLDOWN_SEC=8
set MEXC_MAX_BITHUMB_ITEMS=70

REM MEXC 파일만 텔레그램 STOP/START 버튼 폴러 ON
start "KEDGE MEXC REAL AUTO" cmd /k "set ENABLE_CALLBACK_POLLER=true&& py kedge_v9_4_4_REAL_ORDER_MEXC.py"

timeout /t 2 >nul

REM 나머지 거래소는 중복 버튼 처리 방지용 폴러 OFF
start "KEDGE GATE REAL AUTO" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_GATE.py"
timeout /t 2 >nul
start "KEDGE BITGET REAL AUTO" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_BITGET.py"
timeout /t 2 >nul
start "KEDGE BINGX REAL AUTO" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_BINGX.py"

echo.
echo [OK] 4개 거래소 실행 명령 완료.
echo 이 창은 닫아도 됩니다. 각 거래소 CMD 창은 따로 유지됩니다.
pause
