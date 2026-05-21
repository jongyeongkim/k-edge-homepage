사용법

1. 이 압축 안의 두 파일을 홈페이지 폴더에 넣기
   C:\Users\pc1\Desktop\k-edge-homepage

2. KEDGE_원화가격_자동수정.bat 더블클릭

3. 끝나면 CMD에서 아래 실행
   git add .
   git commit -m "fix krw pricing all pages"
   git push

수정 내용:
- 월 26 USD → 월 35,000원
- 월 49 USD → 월 70,000원
- 월 70 USD → 월 100,000원
- $26/$49/$70 도 원화로 변경
- 레퍼럴 20% 할인 가격 문구도 원화로 보강
