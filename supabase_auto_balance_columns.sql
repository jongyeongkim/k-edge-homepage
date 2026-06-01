alter table auto_settings
  add column if not exists initial_total_balance_krw numeric,
  add column if not exists initial_domestic_balance_krw numeric,
  add column if not exists initial_foreign_futures_balance_krw numeric,
  add column if not exists initial_foreign_spot_balance_krw numeric,
  add column if not exists initial_balance_detail jsonb,
  add column if not exists initial_saved_at timestamptz,
  add column if not exists last_total_balance_krw numeric,
  add column if not exists last_domestic_balance_krw numeric,
  add column if not exists last_foreign_futures_balance_krw numeric,
  add column if not exists last_foreign_spot_balance_krw numeric,
  add column if not exists last_balance_detail jsonb,
  add column if not exists last_balance_checked_at timestamptz,
  add column if not exists balance_snapshot_requested boolean default false,
  add column if not exists balance_snapshot_request_at timestamptz,
  add column if not exists balance_snapshot_notified boolean default false;

select column_name, data_type
from information_schema.columns
where table_name = 'auto_settings'
  and column_name like '%balance%'
order by ordinal_position;
