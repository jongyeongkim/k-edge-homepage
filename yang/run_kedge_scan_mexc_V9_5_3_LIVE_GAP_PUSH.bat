@echo off
chcp 65001 >nul
title K-EDGE SCAN MEXC V9.5.3 LIVE GAP PUSH
cd /d "%~dp0"
py kedge_v9_5_2_SCAN_QUEUE_MEXC.py
pause
