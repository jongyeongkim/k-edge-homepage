@echo off
chcp 65001 >nul
title K-EDGE V9.5.0 CLOSE SAVE FIX

echo ============================================================
echo K-EDGE V9.5.0 CLOSE SAVE FIX
echo - BITHUMB existing API/order logic preserved
echo - AUTO close: foreign short close + domestic spot sell
echo - Real OPEN immediate CSV save
echo - real_order=True only recovery
echo ============================================================
echo.

cd /d "%~dp0"

start "KEDGE MEXC" cmd /k py kedge_v9_5_0_CLOSE_SAVE_FIX_REAL_ORDER_MEXC.py
timeout /t 2 >nul
start "KEDGE GATE" cmd /k py kedge_v9_5_0_CLOSE_SAVE_FIX_REAL_ORDER_GATE.py
timeout /t 2 >nul
start "KEDGE BITGET" cmd /k py kedge_v9_5_0_CLOSE_SAVE_FIX_REAL_ORDER_BITGET.py
timeout /t 2 >nul
start "KEDGE BINGX" cmd /k py kedge_v9_5_0_CLOSE_SAVE_FIX_REAL_ORDER_BINGX.py

echo.
echo 실행 완료. 각 창 로그에서 아래 문구 확인:
echo [OPEN 직접저장 성공]
echo [자동청산 해외숏 성공]
echo [자동청산 국내매도 성공]
echo.
pause
