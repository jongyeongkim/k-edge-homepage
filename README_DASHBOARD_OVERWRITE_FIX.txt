K-EDGE dashboard overwrite fix

문제:
- script.js의 기존 loadLiveDashboard()가 10초마다 data/stats.json 값을 읽어 상단 카드를 다시 덮어씀.
- 그래서 새로고침 직후에는 정상인데 시간이 지나면 예전 숫자로 돌아감.

수정:
- script.js의 기존 JSON 데모 대시보드 함수를 no-op으로 비활성화.
- 실제 대시보드는 kedge-live-dashboard.js가 Supabase에서 갱신.

적용 파일:
- script.js
- kedge-live-dashboard.js
