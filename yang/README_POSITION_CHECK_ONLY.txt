K-EDGE 포지션 조회 전용봇

포함 파일:
- kedge_position_check_only.py
- run_position_check_once.bat
- run_position_check_loop.bat

중요:
- 실제 주문 없음
- 실제 청산 없음
- 실제 매도 없음
- ACTIVE 포지션의 빗썸 현물 수량과 해외 선물 포지션 수량 조회만 수행

설치:
1) 세 파일을 kedge_v9_4_4_REAL_ORDER_BINGX.py 가 있는 폴더에 복사
2) 같은 폴더에 semi_auto_state_bingx.json / mexc / gate / bitget 파일이 있어야 함
3) run_position_check_once.bat 실행

결과:
- 콘솔 출력
- position_check_log.csv 생성

분류:
- 정상_ACTIVE(국내O/해외O)
- 유령후보(국내X/해외X)
- 비대칭(국내X/해외O)-해외숏만 남음
- 비대칭(국내O/해외X)-국내현물만 남음

자동정리/강제청산은 아직 하지 않음.
