@echo off
chcp 65001 >nul
cd /d C:\Users\pc1\Desktop\k-edge-homepage\yang

echo ==========================================
echo K-EDGE 4 SCANNERS START
echo LIVE PUSH FINAL FIX
echo ==========================================

start "KEDGE MEXC SCANNER" cmd /k py kedge_v9_5_2_SCAN_QUEUE_MEXC.py
timeout /t 2 >nul
start "KEDGE GATE SCANNER" cmd /k py kedge_v9_5_2_SCAN_QUEUE_GATE.py
timeout /t 2 >nul
start "KEDGE BITGET SCANNER" cmd /k py kedge_v9_5_2_SCAN_QUEUE_BITGET.py
timeout /t 2 >nul
start "KEDGE BINGX SCANNER" cmd /k py kedge_v9_5_2_SCAN_QUEUE_BINGX.py

echo.
echo 4 scanner windows started.
pause
