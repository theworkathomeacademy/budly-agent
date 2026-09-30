create schema if not exists extensions;
create schema if not exists auth;
create or replace function auth.jwt() returns jsonb language sql stable as $$ select coalesce(current_setting('request.jwt.claims', true)::jsonb, '{}'::jsonb); $$;

do $$ begin
  create role anon nologin;
  create role authenticated nologin;
  create role service_role nologin;
exception when duplicate_object then null;
end $$;

grant usage on schema extensions to postgres, anon, authenticated, service_role;
grant usage on schema auth to postgres, anon, authenticated, service_role;
