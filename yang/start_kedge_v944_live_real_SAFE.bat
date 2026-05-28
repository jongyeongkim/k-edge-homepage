@echo off
chcp 65001 >nul
pushd "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py"
) else (
    set "PY_CMD=python"
)

echo ========================================
echo K-EDGE V9.4.4 LIVE REAL START
echo Folder: %cd%
echo Python: %PY_CMD%
echo ========================================
echo.

if not exist "kedge_storage_worker_v931_test_cap_fee.py" (
    echo [ERROR] kedge_storage_worker_v931_test_cap_fee.py not found.
    pause
    exit /b 1
)
if not exist "kedge_v9_4_4_REAL_ORDER_MEXC.py" (
    echo [ERROR] kedge_v9_4_4_REAL_ORDER_MEXC.py not found.
    pause
    exit /b 1
)
if not exist "kedge_v9_4_4_REAL_ORDER_GATE.py" (
    echo [ERROR] kedge_v9_4_4_REAL_ORDER_GATE.py not found.
    pause
    exit /b 1
)
if not exist "kedge_v9_4_4_REAL_ORDER_BITGET.py" (
    echo [ERROR] kedge_v9_4_4_REAL_ORDER_BITGET.py not found.
    pause
    exit /b 1
)
if not exist "kedge_v9_4_4_REAL_ORDER_BINGX.py" (
    echo [ERROR] kedge_v9_4_4_REAL_ORDER_BINGX.py not found.
    pause
    exit /b 1
)

echo [1/5] Start storage worker
start "KEDGE_STORAGE_WORKER" cmd /k "cd /d "%~dp0" && %PY_CMD% kedge_storage_worker_v931_test_cap_fee.py"

timeout /t 2 /nobreak >nul

echo [2/5] Start MEXC - callback poller ON
start "KEDGE_AUTO_MEXC" cmd /k "cd /d "%~dp0" && set ENABLE_CALLBACK_POLLER=true&& set LIVE_DASHBOARD_ENABLED=true&& %PY_CMD% kedge_v9_4_4_REAL_ORDER_MEXC.py"

echo [3/5] Start GATE - callback poller OFF
start "KEDGE_AUTO_GATE" cmd /k "cd /d "%~dp0" && set ENABLE_CALLBACK_POLLER=false&& set LIVE_DASHBOARD_ENABLED=true&& %PY_CMD% kedge_v9_4_4_REAL_ORDER_GATE.py"

echo [4/5] Start BITGET - callback poller OFF
start "KEDGE_AUTO_BITGET" cmd /k "cd /d "%~dp0" && set ENABLE_CALLBACK_POLLER=false&& set LIVE_DASHBOARD_ENABLED=true&& %PY_CMD% kedge_v9_4_4_REAL_ORDER_BITGET.py"

echo [5/5] Start BINGX - callback poller OFF
start "KEDGE_AUTO_BINGX" cmd /k "cd /d "%~dp0" && set ENABLE_CALLBACK_POLLER=false&& set LIVE_DASHBOARD_ENABLED=true&& %PY_CMD% kedge_v9_4_4_REAL_ORDER_BINGX.py"

echo.
echo DONE. Check each opened CMD window.
echo Only MEXC has ENABLE_CALLBACK_POLLER=true.
echo.
pause
popd
