-- K-EDGE LIVE 후보 카드 가격괴리/BTC괴리 표시용 컬럼 추가
-- Supabase SQL Editor에서 먼저 1회 실행하세요.
alter table kedge_live_events
add column if not exists price_gap_per numeric,
add column if not exists btc_gap_per numeric;
