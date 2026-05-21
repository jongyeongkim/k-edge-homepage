@echo off
cd /d %~dp0
git add .
git commit -m "fix PWA install"
git push
pause
