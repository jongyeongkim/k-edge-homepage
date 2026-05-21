K-EDGE 안전 원화 수정

1. 아래 2개 파일을 홈페이지 폴더에 넣기
   C:\Users\pc1\Desktop\k-edge-homepage

- kedge_safe_krw_fix.py
- RUN_KRW_FIX.bat

2. RUN_KRW_FIX.bat 더블클릭

3. 성공 후 CMD:
   git status
   git add .
   git commit -m "fix all krw prices safely"
   git push

수정:
정상가
26 USD -> 35,000원
49 USD -> 70,000원
70 USD -> 100,000원

레퍼럴가
21 USD -> 28,000원
39 USD -> 56,000원
56 USD -> 80,000원

주의:
PowerShell 방식 아님.
UTF-8 파일만 수정하고, 수정 전 자동 백업 폴더를 만듭니다.
