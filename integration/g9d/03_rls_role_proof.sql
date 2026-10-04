\set ON_ERROR_STOP on

select 'anon_table_privilege=' || has_table_privilege('anon','bros_affiliate.affiliates','select') as proof;
select 'authenticated_ingest_rpc=' || has_function_privilege('authenticated','public.bros_ingest_revenue_event(jsonb)','execute') as proof;
select 'service_ingest_rpc=' || has_function_privilege('service_role','public.bros_ingest_revenue_event(jsonb)','execute') as proof;

set role authenticated;
select set_config('request.jwt.claims','{"sub":"60000000-0000-0000-0000-000000000001","app_metadata":{"affiliate_id":"50000000-0000-0000-0000-000000000001","bros_roles":["AFFILIATE_USER"]}}',false);
select 'affiliate_a_profiles=' || count(*) from bros_affiliate.affiliates;
select 'affiliate_a_commissions=' || count(*) from bros_affiliate.affiliate_commissions;
select 'affiliate_a_applications=' || count(*) from bros_affiliate.affiliate_applications;
select 'affiliate_a_audit=' || count(*) from bros_affiliate.affiliate_audit_events;

select set_config('request.jwt.claims','{"sub":"60000000-0000-0000-0000-000000000002","app_metadata":{"affiliate_id":"50000000-0000-0000-0000-000000000002","bros_roles":["AFFILIATE_USER"]}}',false);
select 'affiliate_b_profiles=' || count(*) from bros_affiliate.affiliates;
select 'affiliate_b_commissions=' || count(*) from bros_affiliate.affiliate_commissions;

select set_config('request.jwt.claims','{"sub":"60000000-0000-0000-0000-000000000099","app_metadata":{"bros_roles":["PROJECT_OWNER"]}}',false);
select 'owner_profiles=' || count(*) from bros_affiliate.affiliates;
select 'owner_applications=' || count(*) from bros_affiliate.affiliate_applications;
select 'owner_commissions=' || count(*) from bros_affiliate.affiliate_commissions;
select 'owner_audit=' || count(*) from bros_affiliate.affiliate_audit_events;
select 'owner_payout_batches=' || count(*) from bros_affiliate.affiliate_payout_batches;
reset role;

do $$
declare
  anon_select boolean;
  authenticated_rpc boolean;
  service_rpc boolean;
begin
  select has_table_privilege('anon','bros_affiliate.affiliates','select') into anon_select;
  select has_function_privilege('authenticated','public.bros_ingest_revenue_event(jsonb)','execute') into authenticated_rpc;
  select has_function_privilege('service_role','public.bros_ingest_revenue_event(jsonb)','execute') into service_rpc;
  if anon_select then raise exception 'ANON_PRIVATE_ACCESS'; end if;
  if authenticated_rpc then raise exception 'AFFILIATE_BACKEND_RPC_ACCESS'; end if;
  if not service_rpc then raise exception 'SERVICE_RPC_MISSING'; end if;
end $$;

select 'G9D_RLS_ROLE_PROOF_PASS' as result;
