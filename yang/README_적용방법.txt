K-EDGE V9.4.4 LIVE DASHBOARD PATCH

포함 파일:
- kedge_v9_4_4_REAL_ORDER_MEXC.py
- kedge_v9_4_4_REAL_ORDER_GATE.py
- kedge_v9_4_4_REAL_ORDER_BITGET.py
- kedge_v9_4_4_REAL_ORDER_BINGX.py
- run_all_kedge_v9_4_4_LIVE_DASHBOARD_PATCH.bat
- index.html / script.js / style.css / kedge-live-dashboard.js

수정 내용:
1) AUTO 봇이 Supabase kedge_live_events에 이벤트 저장
   - CANDIDATE
   - ENTRY_SUCCESS
   - ENTRY_FAIL
   - TP_SUCCESS
   - TP_FAIL
   - SL_WARNING
   - SL_STRONG_WARNING

2) kedge_live_summary 업데이트
   - bot_status = 가동중
   - today_entries 증가
   - today_tp 증가
   - updated_at 갱신

3) 홈페이지 kedge-live-dashboard.js 버전 갱신

주의:
- 빗썸 API 조회/잔고/현물매수, 해외 잔고조회/선물숏 진입 로직은 건드리지 않음.
- Supabase 테이블/RLS는 이미 존재한다는 기준.
