@echo off
chcp 65001 >nul
title K-EDGE 레퍼럴가 원화 수정
cd /d "%~dp0"
py kedge_referral_krw_fix.py
pause
