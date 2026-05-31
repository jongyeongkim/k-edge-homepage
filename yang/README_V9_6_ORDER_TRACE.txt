K-EDGE V9.6 주문번호 기반 포지션 추적 패키지

파일:
1. kedge_order_trace_utils_v9_6.py
   - 신규 진입 성공 시 order_trace 생성/부착용 유틸
   - ORDER WORKER/core에서 import해서 사용

2. kedge_position_audit_worker_v9_6_order_trace.py
   - order_trace 있으면 주문번호 기반 우선 판정
   - 없으면 route/해외포지션 fallback
   - 실제 매도/청산 없음
   - 상태값만 정리 가능

3. run_order_trace_audit_view_v9_6.bat
   - 조회만

4. run_order_trace_route_cleanup_v9_6.bat
   - ROUTE_GHOST_CLOSED / DOMESTIC_ONLY 등 상태값만 변경
   - 실제 주문 없음

주의:
- 기존 과거 포지션에는 order_trace가 없을 수 있어 legacy fallback으로 판단합니다.
- 신규 포지션부터는 ORDER WORKER 진입 성공 저장부에 kedge_order_trace_utils_v9_6.py를 붙여야 완전 정확해집니다.
- CLOSE WORKER 실제 청산 전 이 AUDIT로 ACTIVE를 깨끗하게 만드는 것이 우선입니다.
