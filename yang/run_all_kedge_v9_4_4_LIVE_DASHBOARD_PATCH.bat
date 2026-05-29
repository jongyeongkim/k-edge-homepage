@echo off
chcp 65001 >nul
title K-EDGE V9.4.4 LIVE DASHBOARD PATCH
cd /d "%~dp0"
start "KEDGE MEXC LIVE" py kedge_v9_4_4_REAL_ORDER_MEXC.py
start "KEDGE GATE LIVE" py kedge_v9_4_4_REAL_ORDER_GATE.py
start "KEDGE BITGET LIVE" py kedge_v9_4_4_REAL_ORDER_BITGET.py
start "KEDGE BINGX LIVE" py kedge_v9_4_4_REAL_ORDER_BINGX.py
echo K-EDGE LIVE dashboard patched engines started.
pause
