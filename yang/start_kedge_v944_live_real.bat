@echo off
chcp 65001 >nul
cd /d %~dp0

echo ========================================
echo K-EDGE V9.4.4 REAL ORDER + LIVE DASHBOARD
echo 4개 거래소 AUTO 파일과 저장워커를 실행합니다.
echo ========================================

echo [1/5] Storage Worker 시작
start "KEDGE_STORAGE_WORKER" cmd /k py kedge_storage_worker_v931_test_cap_fee.py

timeout /t 2 >nul

echo [2/5] MEXC AUTO 시작 - callback poller ON
start "KEDGE_AUTO_MEXC" cmd /k set ENABLE_CALLBACK_POLLER=true ^& set LIVE_DASHBOARD_ENABLED=true ^& py kedge_v9_4_4_REAL_ORDER_MEXC.py

echo [3/5] GATE AUTO 시작 - callback poller OFF
start "KEDGE_AUTO_GATE" cmd /k set ENABLE_CALLBACK_POLLER=false ^& set LIVE_DASHBOARD_ENABLED=true ^& py kedge_v9_4_4_REAL_ORDER_GATE.py

echo [4/5] BITGET AUTO 시작 - callback poller OFF
start "KEDGE_AUTO_BITGET" cmd /k set ENABLE_CALLBACK_POLLER=false ^& set LIVE_DASHBOARD_ENABLED=true ^& py kedge_v9_4_4_REAL_ORDER_BITGET.py

echo [5/5] BINGX AUTO 시작 - callback poller OFF
start "KEDGE_AUTO_BINGX" cmd /k set ENABLE_CALLBACK_POLLER=false ^& set LIVE_DASHBOARD_ENABLED=true ^& py kedge_v9_4_4_REAL_ORDER_BINGX.py

echo.
echo 실행 완료. 각 CMD 창에서 오류 로그를 확인하세요.
echo 홈페이지 LIVE DASHBOARD는 Supabase kedge_live_events / kedge_live_summary를 읽습니다.
pause
