@echo off
setlocal
chcp 65001 >nul

title K-EDGE AUTO V9.4 FIXED
cd /d "%~dp0"

echo ========================================
echo K-EDGE AUTO V9.4 START
echo Folder: %CD%
echo ========================================
echo.

set "PYTHON=py"
where py >nul 2>nul
if errorlevel 1 set "PYTHON=python"

if not exist "kedge_v9_3_2_BITHUMB_TO_MEXC_AUTO_PAPER_TEST_CAP_FEE_SLOW.py" goto missing
if not exist "kedge_v9_3_1_BITHUMB_TO_GATE_AUTO_PAPER_TEST_CAP_FEE.py" goto missing
if not exist "kedge_v9_3_1_BITHUMB_TO_BITGET_AUTO_PAPER_TEST_CAP_FEE.py" goto missing
if not exist "kedge_v9_3_1_BITHUMB_TO_BINGX_AUTO_PAPER_TEST_CAP_FEE.py" goto missing
if not exist "kedge_storage_worker_v931_test_cap_fee.py" goto missing

start "KEDGE MEXC CALLBACK" cmd /k "%PYTHON% ""kedge_v9_3_2_BITHUMB_TO_MEXC_AUTO_PAPER_TEST_CAP_FEE_SLOW.py"""
timeout /t 2 /nobreak >nul
start "KEDGE GATE" cmd /k "%PYTHON% ""kedge_v9_3_1_BITHUMB_TO_GATE_AUTO_PAPER_TEST_CAP_FEE.py"""
timeout /t 2 /nobreak >nul
start "KEDGE BITGET" cmd /k "%PYTHON% ""kedge_v9_3_1_BITHUMB_TO_BITGET_AUTO_PAPER_TEST_CAP_FEE.py"""
timeout /t 2 /nobreak >nul
start "KEDGE BINGX" cmd /k "%PYTHON% ""kedge_v9_3_1_BITHUMB_TO_BINGX_AUTO_PAPER_TEST_CAP_FEE.py"""
timeout /t 2 /nobreak >nul
start "KEDGE STORAGE" cmd /k "%PYTHON% ""kedge_storage_worker_v931_test_cap_fee.py"""

echo.
echo ALL 5 PROCESS STARTED.
echo MEXC window handles Telegram stop/restart callbacks.
echo.
pause
exit /b 0

:missing
echo.
echo ERROR: Required .py file was not found in this folder.
echo Current folder: %CD%
echo.
echo Make sure this .bat file is inside the same folder as the 5 Python files.
echo.
dir /b *.py
echo.
pause
exit /b 1
