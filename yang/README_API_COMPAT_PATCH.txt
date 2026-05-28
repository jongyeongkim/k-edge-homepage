K-EDGE API 호환 패치 요약

1) 백업 파일
- kedge_backup_before_api_compat_patch.zip
- 이번 수정 전 파일 원본 백업입니다.

2) 패치 목적
- 기존 DB 컬럼 방식(domestic_api_key/domestic_api_secret/foreign_api_key/foreign_api_secret)과
  새 JSON 방식(domestic_apis/foreign_apis)을 AUTO 봇이 둘 다 읽도록 수정했습니다.
- payment.html은 앞으로 신청 저장 시 새 JSON + 기존 일반 컬럼 둘 다 저장하도록 수정했습니다.

3) 적용 파일
- kedge_v9_4_4_REAL_ORDER_MEXC.py
- kedge_v9_4_4_REAL_ORDER_GATE.py
- kedge_v9_4_4_REAL_ORDER_BITGET.py
- kedge_v9_4_4_REAL_ORDER_BINGX.py
- payment.html
- admin.html
- start_kedge_v944_live_real_SAFE.bat

4) 주의
- 이미 DB에 null로 저장된 기존 row는 자동으로 채워지지 않습니다.
- 삭제하지 말고 Supabase에서 해당 row의 domestic_api_key/domestic_api_secret 또는 domestic_apis를 직접 채우면 됩니다.
- 이후 새 신청부터는 payment.html이 두 구조 모두 저장합니다.
