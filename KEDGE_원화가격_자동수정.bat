@echo off
chcp 65001 >nul
title K-EDGE 원화 가격 자동 수정
cd /d "%~dp0"
py kedge_fix_krw_all.py
pause
