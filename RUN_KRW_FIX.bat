@echo off
chcp 65001 >nul
title K-EDGE SAFE KRW FIX
cd /d "%~dp0"
py kedge_safe_krw_fix.py
pause
