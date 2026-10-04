\set ON_ERROR_STOP on

-- G9D isolated vertical-slice additions. Production gates remain OFF.

create table if not exists bros_affiliate.affiliate_invitations (
  id uuid primary key default extensions.gen_random_uuid(),
  invitation_key text not null unique,
  token_hash char(64) not null unique,
  intended_email extensions.citext not null,
  intended_class bros_affiliate.affiliate_class not null,
  classification text not null check (classification = 'TEST_SYNTHETIC_NON_PRODUCTION_PERSON'),
  expires_at timestamptz not null,
  revoked_at timestamptz,
  used_at timestamptz,
  created_at timestamptz not null default now(),
  check (expires_at > created_at)
);

alter table bros_affiliate.affiliate_invitations enable row level security;
revoke all on bros_affiliate.affiliate_invitations from anon, authenticated;

create table if not exists public.revenue_events (
  id uuid primary key default extensions.gen_random_uuid(),
  schema_version text not null check (schema_version = 'bros.revenue_event.v1'),
  source_system text not null check (source_system = 'woocommerce'),
  source_event_id text not null unique,
  source_order_id text not null,
  event_payload jsonb not null,
  payload_sha256 char(64) not null,
  received_at timestamptz not null default now(),
  created_at timestamptz not null default now()
);
alter table public.revenue_events enable row level security;
revoke all on public.revenue_events from anon, authenticated;

create or replace function public.bros_ingest_revenue_event(payload jsonb)
returns table(event_id uuid, inserted boolean)
language plpgsql security invoker set search_path = '' as $$
declare existing_id uuid;
begin
  if payload->>'schema_version' <> 'bros.revenue_event.v1'
     or payload->>'source_system' <> 'woocommerce'
     or coalesce(payload->>'source_event_id','') = ''
     or coalesce(payload->>'source_order_id','') = '' then
    raise exception 'INVALID_REVENUE_EVENT';
  end if;
  select id into existing_id from public.revenue_events
    where source_event_id = payload->>'source_event_id';
  if existing_id is not null then
    return query select existing_id, false;
    return;
  end if;
  insert into public.revenue_events(schema_version,source_system,source_event_id,source_order_id,event_payload,payload_sha256)
  values(payload->>'schema_version',payload->>'source_system',payload->>'source_event_id',payload->>'source_order_id',payload,payload->>'payload_sha256')
  returning id into existing_id;
  return query select existing_id, true;
end $$;
revoke all on function public.bros_ingest_revenue_event(jsonb) from public, anon, authenticated;
grant usage on schema public to service_role;
grant select,insert on public.revenue_events to service_role;
grant execute on function public.bros_ingest_revenue_event(jsonb) to service_role;

grant select on bros_affiliate.affiliate_applications,
  bros_affiliate.affiliate_terms_acceptances,
  bros_affiliate.affiliate_referral_events,
  bros_affiliate.affiliate_attribution_decisions,
  bros_affiliate.affiliate_order_line_commissions,
  bros_affiliate.affiliate_commission_ledger,
  bros_affiliate.affiliate_audit_events,
  bros_affiliate.affiliate_payout_batches to authenticated;

create policy applications_owner_read on bros_affiliate.affiliate_applications
  for select to authenticated using ((select private.bros_has_role('PROJECT_OWNER')) or (select private.bros_has_role('AFFILIATE_OPERATOR')));
create policy terms_self_or_owner_read on bros_affiliate.affiliate_terms_acceptances
  for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')));
create policy referral_self_or_owner_read on bros_affiliate.affiliate_referral_events
  for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')));
create policy attribution_self_or_owner_read on bros_affiliate.affiliate_attribution_decisions
  for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')));
create policy lines_self_or_owner_read on bros_affiliate.affiliate_order_line_commissions
  for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')));
create policy ledger_self_or_owner_read on bros_affiliate.affiliate_commission_ledger
  for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')));
create policy audit_owner_read on bros_affiliate.affiliate_audit_events
  for select to authenticated using ((select private.bros_has_role('PROJECT_OWNER')));
create policy payout_batches_owner_read on bros_affiliate.affiliate_payout_batches
  for select to authenticated using ((select private.bros_has_role('PROJECT_OWNER')) or (select private.bros_has_role('FINANCIAL_APPROVER')));

grant usage on schema bros_affiliate, extensions to service_role;
grant all privileges on all tables in schema bros_affiliate to service_role;
grant usage, select on all sequences in schema bros_affiliate to service_role;

comment on table public.revenue_events is 'G9D isolated Woo-compatible bros.revenue_event.v1 intake contract.';
comment on table bros_affiliate.affiliate_invitations is 'G9D synthetic invitations; raw tokens are never stored.';
