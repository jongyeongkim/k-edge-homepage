@echo off
cd /d %~dp0

set SUPABASE_AUTO_SETTINGS_TABLE=auto_settings
set AUTO_SETTINGS_CACHE_TTL_SEC=20
set APPROVED_MEMBER_CACHE_TTL_SEC=300

set MEXC_MAX_BITHUMB_ITEMS=70
set MEXC_MAX_SPOT_ITEMS=70

start "KEDGE_MEXC" cmd /k "set ENABLE_CALLBACK_POLLER=true&& py kedge_v9_4_4_REAL_ORDER_MEXC.py"
timeout /t 2 /nobreak >nul

start "KEDGE_GATE" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_GATE.py"
timeout /t 2 /nobreak >nul

start "KEDGE_BITGET" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_BITGET.py"
timeout /t 2 /nobreak >nul

start "KEDGE_BINGX" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_4_4_REAL_ORDER_BINGX.py"

pause
