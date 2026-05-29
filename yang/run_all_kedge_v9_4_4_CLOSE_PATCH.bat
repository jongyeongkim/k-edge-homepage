@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo K-EDGE V9.4.4 CLOSE PATCH START
echo - MEXC / GATE / BITGET / BINGX 4 files
echo - Only close logic patched: foreign short close + Bithumb spot sell

echo ========================================

start "KEDGE_MEXC" py kedge_v9_4_4_REAL_ORDER_MEXC.py
start "KEDGE_GATE" py kedge_v9_4_4_REAL_ORDER_GATE.py
start "KEDGE_BITGET" py kedge_v9_4_4_REAL_ORDER_BITGET.py
start "KEDGE_BINGX" py kedge_v9_4_4_REAL_ORDER_BINGX.py

echo All 4 K-EDGE files launched.
pause
