K-EDGE V9.5.2 SPEED PATCH

적용 파일:
- kedge_v9_5_2_SCAN_QUEUE_MEXC_SPEEDPATCH.py
- run_kedge_v9_5_2_mexc_speedpatch.bat

핵심 변경:
1. 1.5% 엣지 기준 유지
2. realtime_entry_recheck 유지: 국내호가/해외호가/BTC 기준/슬리피지 실시간 검사
3. check_entry_balances 속도 개선
   - ORDER WORKER에서 받은 member 재사용
   - API 객체 300초 캐시
   - 국내/해외 잔고 10초 캐시
4. telegram_send_private getMe 매번 호출 제거
   - 기본 최초 1회만 확인
   - 필요 시 set KEDGE_DEBUG_GETME_EVERY_DM=true
5. 속도 로그 추가
   [SPEED CHECK_ENTRY] total=... recheck=... dom_balance=...(cache/fresh) fut_balance=...(cache/fresh)

주의:
- 이 파일은 MEXC route core용 속도패치본이다.
- GATE/BITGET/BINGX 파일에도 같은 패치를 적용하려면 각 route 파일 기준으로 동일 패치가 필요하다.
- 정확도를 위해 최종 호가 재검사는 제거하지 않았다.
