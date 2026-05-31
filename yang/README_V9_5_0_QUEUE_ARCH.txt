K-EDGE V9.5.0 QUEUE ARCH - STEP 1

구조:
1) kedge_v9_5_0_SCAN_QUEUE_MEXC/GATE/BITGET/BINGX.py
   - 기존 4개 봇 기반
   - 실제 주문/자동청산 실행 안 함
   - 후보 감지 시 order_queue.jsonl 저장만 함

2) kedge_order_worker_v9_5_0.py
   - order_queue.jsonl 즉시 감시
   - 승인회원/AUTO 설정 확인
   - 전역 LOCK/재검사
   - 해외 숏 주문 -> 성공 확인 -> 빗썸 매수
   - ACTIVE 저장/DM

3) kedge_close_worker_v9_5_0.py
   - 이번 1차는 중앙 청산봇 뼈대/ACTIVE 확인용
   - 다음 패치에서 현재엣지 감시 + 해외우선 청산 + 유령/부분청산 정리를 붙인다.

실행:
- 기존 봇은 끄고 압축을 yang 폴더에 푼다.
- run_all_v9_5_0_queue_arch.bat 실행

주의:
- 실거래 REAL_ORDER_ENABLED=True 상태를 유지한다.
- 먼저 소액으로 order_worker가 queue를 정상 처리하는지 확인한다.
