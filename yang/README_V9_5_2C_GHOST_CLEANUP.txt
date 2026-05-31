K-EDGE V9.5.2c GHOST CLEANUP

목적:
- 자동매도/해외청산 없이 ACTIVE 상태값만 정리합니다.
- 국내 평가금액 < 1000원 AND 해외 포지션 가치 < 1000원인 유령만 ACTIVE -> GHOST_CLOSED 처리합니다.
- 국내만 남은 DOMESTIC_ONLY, 해외만 남은 FUTURES_ONLY는 이번 패치에서 자동 정리하지 않습니다.

실행 순서:
1) 먼저 조회만:
   run_position_audit_once.bat

2) 결과 확인 후 유령만 정리:
   run_position_ghost_cleanup_once.bat

확인 로그:
- [GHOST CLEANUP] ... ACTIVE -> GHOST_CLOSED / 실제 주문 없음

주의:
- 이 패치는 실제 주문을 전혀 보내지 않습니다.
- 빗썸 매도/해외 청산은 추후 CLOSE WORKER 실청산 패치에서 처리합니다.
