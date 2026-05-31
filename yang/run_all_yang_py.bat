@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ========================================
echo K-EDGE YANG PYTHON AUTO RUNNER
echo ========================================

for %%F in (*.py) do (
    echo [RUN] %%F
    start "%%~nF" py "%%F"
)

echo.
echo All Python files started.
pause
