@echo off
chcp 65001 >nul
title K-EDGE AUTO V9.4.1 COMMON BOT
cd /d "%~dp0"

echo ============================================================
echo K-EDGE AUTO V9.4.1 COMMON BOT START
echo 5 processes: STORAGE + BINGX + BITGET + GATE + MEXC CALLBACK
echo Common Telegram bot sends DM to approved users by tg_chat_id.
echo ============================================================

start "KEDGE_STORAGE_WORKER" cmd /k "py kedge_storage_worker_v931_test_cap_fee.py"
start "KEDGE_BINGX_AUTO" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_3_1_BITHUMB_TO_BINGX_AUTO_PAPER_TEST_CAP_FEE.py"
start "KEDGE_BITGET_AUTO" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_3_1_BITHUMB_TO_BITGET_AUTO_PAPER_TEST_CAP_FEE.py"
start "KEDGE_GATE_AUTO" cmd /k "set ENABLE_CALLBACK_POLLER=false&& py kedge_v9_3_1_BITHUMB_TO_GATE_AUTO_PAPER_TEST_CAP_FEE.py"
start "KEDGE_MEXC_AUTO_CALLBACK" cmd /k "set ENABLE_CALLBACK_POLLER=true&& py kedge_v9_3_2_BITHUMB_TO_MEXC_AUTO_PAPER_TEST_CAP_FEE_SLOW.py"

echo.
echo ALL 5 PROCESS STARTED.
pause
