@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo K-EDGE Supabase DB Bridge 설치
echo ========================================

if not exist payment.html (
  echo [오류] payment.html 이 없습니다. k-edge-homepage 폴더에서 실행하세요.
  pause
  exit /b
)

copy /Y kedge-supabase-db.js .\kedge-supabase-db.js >nul

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$files=@('payment.html','admin.html','mypage.html');" ^
  "$tag='<script src=""./kedge-supabase-db.js?v=20260523""></script>';" ^
  "foreach($f in $files){" ^
  " if(Test-Path $f){" ^
  "  $t=Get-Content $f -Raw -Encoding UTF8;" ^
  "  if($t -notmatch 'kedge-supabase-db\.js'){" ^
  "   $t=$t -replace '(<script src=""\./script\.js(?:\?[^""]*)?""></script>)', ('$1' + [Environment]::NewLine + $tag);" ^
  "   Set-Content $f $t -Encoding UTF8;" ^
  "   Write-Host ('[수정] ' + $f);" ^
  "  } else { Write-Host ('[건너뜀] ' + $f + ' 이미 설치됨'); }" ^
  " }" ^
  "}"

echo.
echo 설치 완료.
echo 다음 명령어 실행:
echo git add payment.html admin.html mypage.html kedge-supabase-db.js
echo git commit -m "connect requests to supabase"
echo git push origin main
echo.
pause
