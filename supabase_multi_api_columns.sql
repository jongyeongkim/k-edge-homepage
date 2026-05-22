alter table public.kedge_requests
add column if not exists domestic_apis jsonb default '{}'::jsonb,
add column if not exists foreign_apis jsonb default '{}'::jsonb;

alter table public.kedge_users
add column if not exists domestic_apis jsonb default '{}'::jsonb,
add column if not exists foreign_apis jsonb default '{}'::jsonb;
