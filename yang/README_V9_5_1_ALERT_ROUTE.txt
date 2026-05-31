K-EDGE V9.5.1 ALERT ROUTE / QUEUE ARCH

Purpose
- 4 scanner bots keep VIP/FREE room candidate alerts and enqueue AUTO candidates.
- Scanner bots do NOT send AUTO user personal DM.
- ORDER WORKER reads order_queue.jsonl and sends AUTO user personal DM only for account-impacting entry success/failure.
- CLOSE WORKER is still monitor skeleton in this step. Next patch: foreign-first close + ghost cleanup.

Files
- kedge_v9_5_1_SCAN_QUEUE_MEXC.py
- kedge_v9_5_1_SCAN_QUEUE_GATE.py
- kedge_v9_5_1_SCAN_QUEUE_BITGET.py
- kedge_v9_5_1_SCAN_QUEUE_BINGX.py
- kedge_order_worker_v9_5_1.py
- kedge_close_worker_v9_5_1.py
- run_all_v9_5_1_alert_route.bat

Expected scan bot logs
- [QUEUE 저장] ...
- [AUTO QUEUE] 후보 저장 완료 ...
- [VIP 텔레그램 전송 성공]
- [FREE 텔레그램 전송 성공]
- [AUTO 개인DM 스캔봇 미발송] ... ORDER WORKER가 진입성공·실패 DM 처리

Expected order worker logs
- [ORDER WORKER] GLOBAL_FUTURE_EXS=['BINGX','BITGET','GATE','MEXC'] or equivalent
- [ORDER PICK] ...
- [ORDER SUCCESS] or [ORDER FAIL/SKIP]

Important
- Scanner room alerts stay in scan bots.
- AUTO personal DM belongs to ORDER WORKER/CLOSE WORKER only.
- Worker loads all futures exchanges for recheck/order, not only MEXC.
