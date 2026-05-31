@echo off
chcp 65001 > nul
cd /d "%~dp0"
py kedge_telegram_menu_worker.py
pause
