\set ON_ERROR_STOP on

-- Minimal Supabase-compatible role/auth surface for an isolated PostgreSQL test.
-- This is not a replacement Supabase deployment and contains no production data.
create schema if not exists extensions;
create schema if not exists auth;

do $$ begin create role anon nologin; exception when duplicate_object then null; end $$;
do $$ begin create role authenticated nologin; exception when duplicate_object then null; end $$;
do $$ begin create role service_role nologin bypassrls; exception when duplicate_object then null; end $$;

create or replace function auth.jwt() returns jsonb
language sql stable security invoker set search_path = '' as $$
  select coalesce(nullif(current_setting('request.jwt.claims', true), '')::jsonb, '{}'::jsonb)
$$;

create or replace function auth.uid() returns uuid
language sql stable security invoker set search_path = '' as $$
  select nullif(auth.jwt()->>'sub', '')::uuid
$$;

revoke all on function auth.jwt(), auth.uid() from public;
grant usage on schema auth to anon, authenticated, service_role;
grant execute on function auth.jwt(), auth.uid() to anon, authenticated, service_role;
