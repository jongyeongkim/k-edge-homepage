-- K-EDGE 국내/해외 API 컬럼 확장 SQL
-- Supabase > SQL Editor에서 1회 실행

alter table kedge_requests add column if not exists foreign_exchange text;
alter table kedge_requests add column if not exists foreign_api_key text;
alter table kedge_requests add column if not exists foreign_api_secret text;
alter table kedge_requests add column if not exists domestic_exchange text;
alter table kedge_requests add column if not exists domestic_api_key text;
alter table kedge_requests add column if not exists domestic_api_secret text;

alter table kedge_users add column if not exists foreign_exchange text;
alter table kedge_users add column if not exists foreign_api_key text;
alter table kedge_users add column if not exists foreign_api_secret text;
alter table kedge_users add column if not exists domestic_exchange text;
alter table kedge_users add column if not exists domestic_api_key text;
alter table kedge_users add column if not exists domestic_api_secret text;
