K-EDGE V9.4.6 REAL ORDER PATCH

Patch summary:
1. Entry order changed: foreign short first -> confirm success -> Bithumb spot buy.
2. Close order changed: foreign short close first -> confirm success -> Bithumb spot sell.
3. If foreign close fails, Bithumb sell is blocked.
4. Partial states added: FUTURES_CLOSED_ONLY / SPOT_CLOSED_ONLY.
5. Same-coin global lock strengthened.
6. Speed guard: MAX_AUTO_RECHECK_DELAY_SEC=1.0.
7. Slippage guard: MIN_ALLOWED_SLIPPAGE_FOR_REAL_ENTRY_PERCENT=0.15.

Run:
Double-click run_all_v9_4_6_REAL_ORDER.bat

Callback poller:
MEXC=true, GATE/BITGET/BINGX=false.
