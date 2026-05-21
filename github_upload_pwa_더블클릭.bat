@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo K-EDGE PWA GitHub 업로드 시작
echo ========================================
git add .
git commit -m "fix pwa install"
git push
echo.
echo ========================================
echo 끝났습니다. 이 창을 닫아도 됩니다.
echo ========================================
pause
