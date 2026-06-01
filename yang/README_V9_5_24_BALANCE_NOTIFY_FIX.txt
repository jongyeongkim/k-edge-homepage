K-EDGE V9.5.24 BALANCE NOTIFY FIX

해결 내용:
- AUTO 설정 저장 후 텔레그램 최초잔고 알림이 안 오던 문제 수정
- 원인: 메뉴워커가 auto_settings의 capital_krw를 잔고 계산에 합치지 않고 승인회원 row만 사용
- 수정: member + auto_settings를 merge해서 자산 계산
- balance_snapshot_requested=true 행을 메뉴워커가 감지하면 최초잔고 DM 발송
- 주문/오더워커/진입로직 파일은 포함하지 않음

적용:
1) auto-settings.html 덮어쓰기
2) yang/kedge_telegram_menu_worker_V9_5_24_BALANCE_NOTIFY_FIX.py 복사
3) yang/run_kedge_telegram_menu_worker_V9_5_24_BALANCE_NOTIFY_FIX.bat 복사
4) 기존 메뉴워커 창 종료
5) 새 bat 실행

확인:
- AUTO 설정 저장 시 auto_settings.balance_snapshot_requested=true
- 메뉴워커 CMD에 pending balance snapshots=N
- 텔레그램에 최초 기준잔고 DM 도착
