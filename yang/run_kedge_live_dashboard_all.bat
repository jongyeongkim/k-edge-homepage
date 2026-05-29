@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo =========================================
echo K-EDGE V9.4.4 LIVE DASHBOARD PATCH RUN
echo MEXC만 STOP/callback poller ON
echo GATE/BITGET/BINGX는 callback poller OFF
echo =========================================

start "KEDGE MEXC LIVE" cmd /k "set ENABLE_CALLBACK_POLLER=true&& py kedge_v9_4_4_REAL_ORDER_MEXC.py"
timeout /t 2 >nul
start "KEDGE GATE LIVE" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_GATE.py"
timeout /t 2 >nul
start "KEDGE BITGET LIVE" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_BITGET.py"
timeout /t 2 >nul
start "KEDGE BINGX LIVE" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_BINGX.py"

echo 실행 완료. 각 CMD 창 로그를 확인하세요.
pause
