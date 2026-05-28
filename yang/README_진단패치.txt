K-EDGE 빗썸 API 진단 패치

적용:
1) AUTO 4개 py 파일을 기존 폴더에 덮어쓰기
2) 기존 CMD 전부 종료
3) SAFE BAT 재실행

확인할 로그:
[API진단 로드] exchange=BITHUMB type=spot source=... key_len=... secret_len=...
[API진단 잔고조회 시작]
[API진단 잔고조회 성공] 또는 [API진단 잔고조회 실패]

판단:
- key_len=0 이면 DB/API 읽기 문제
- key_len/secret_len 정상인데 Invalid Apikey면 빗썸 키/IP/서명 방식 문제
