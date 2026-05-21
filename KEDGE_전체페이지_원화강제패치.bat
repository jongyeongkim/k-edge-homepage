@echo off
chcp 65001 >nul
title K-EDGE 전체 페이지 원화 강제 패치
cd /d "%~dp0"
py kedge_force_krw_patch.py
pause
