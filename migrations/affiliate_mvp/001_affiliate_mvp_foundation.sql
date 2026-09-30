-- AFF-001 Phase F: additive, non-production Affiliate MVP foundation.
-- Baseline: b8acdcbbbe6cfc31dbf3e89351c064de5ac276c9
-- Feature gates default OFF. No production affiliate behavior is activated here.

create extension if not exists pgcrypto with schema extensions;
create extension if not exists citext with schema extensions;
create schema if not exists bros_affiliate;
create schema if not exists private;
grant usage on schema bros_affiliate to authenticated, anon;

do $$ begin create type bros_affiliate.affiliate_status as enum ('APPROVED_PENDING_TERMS','ACTIVE','INACTIVE','SUSPENDED','TERMINATED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.affiliate_class as enum ('STANDARD','STRATEGIC_PARTNER'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.application_status as enum ('SUBMITTED','UNDER_REVIEW','MORE_INFO_REQUIRED','APPROVED','DECLINED','WITHDRAWN'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.route_status as enum ('ACTIVE','INACTIVE','EXPIRED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.referral_method as enum ('LINK','QR','COUPON','MANUAL_CORRECTION'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.referral_validation_status as enum ('QUALIFIED','REJECTED','BOT_SUSPECTED','INVALID'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.attribution_context_status as enum ('ACTIVE','EXPIRED','SUPERSEDED','INVALID'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.attribution_status as enum ('ATTRIBUTED','UNATTRIBUTED','EXPIRED','INELIGIBLE','UNRESOLVED','OVERRIDDEN'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.attribution_method as enum ('REFERRAL_LINK','QR_REFERRAL','AFFILIATE_COUPON','MANUAL_CORRECTION'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.mapping_status as enum ('ACTIVE','INACTIVE','EXPIRED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.commission_rule_status as enum ('DRAFT','APPROVED','INACTIVE','SUPERSEDED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.commission_rate_type as enum ('PERCENTAGE','FIXED_AMOUNT'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.commission_status as enum ('PENDING','APPROVED','PAYABLE','PAID','REVERSED','DISPUTED','REJECTED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.commission_event_type as enum ('COMMISSION_CREATED','COMMISSION_APPROVED','COMMISSION_PAYABLE','COMMISSION_PAID','COMMISSION_PARTIAL_REVERSAL','COMMISSION_FULL_REVERSAL','COMMISSION_ADJUSTMENT_CREDIT','COMMISSION_ADJUSTMENT_DEBIT','COMMISSION_DISPUTED','COMMISSION_DISPUTE_RESOLVED','COMMISSION_REJECTED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.payout_status as enum ('PREPARED','UNDER_REVIEW','APPROVED','SUBMITTED','COMPLETED','PARTIAL_FAILURE','FAILED','RECONCILED','CANCELLED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.payout_item_status as enum ('PREPARED','APPROVED','SUBMITTED','PAID','FAILED','HELD','RECONCILED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.dispute_status as enum ('NONE','OPEN','UNDER_REVIEW','RESOLVED_AFFIRMED','RESOLVED_ADJUSTED','RESOLVED_REJECTED','CLOSED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.dispute_type as enum ('ATTRIBUTION','COMMISSION','REVERSAL','PAYOUT','OTHER'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.risk_event_type as enum ('SELF_REFERRAL_SUSPECTED','DUPLICATE_IDENTITY','ABNORMAL_REFUND_RATE','BOT_TRAFFIC_PATTERN','COUPON_LEAKAGE','ATTRIBUTION_MANIPULATION','UNUSUAL_CONVERSION_PATTERN','PAYMENT_RISK_CLUSTER','RELATED_PARTY_REVIEW','OTHER_REVIEW_REQUIRED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.risk_severity as enum ('LOW','MEDIUM','HIGH','CRITICAL'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.risk_review_status as enum ('OPEN','UNDER_REVIEW','RESOLVED','DISMISSED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.audit_actor_type as enum ('PROJECT_OWNER','AFFILIATE_OPERATOR','FINANCIAL_APPROVER','SUPPORT_OPERATOR','SYSTEM_SERVICE','AFFILIATE_USER','BUDLY','EXTERNAL_PROVIDER'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.quarantine_status as enum ('OPEN','RETRY_SCHEDULED','UNDER_REVIEW','RESOLVED_REPROCESSED','RESOLVED_REJECTED','CLOSED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.quarantine_reason as enum ('MALFORMED_EVENT','INVALID_SIGNATURE','UNKNOWN_AFFILIATE','UNKNOWN_PRODUCT','CONFLICTING_ATTRIBUTION','MISSING_COMMISSION_RULE','INVALID_CURRENCY','INVALID_AFFILIATE_STATE','IMPOSSIBLE_STATE_TRANSITION','PERSISTENCE_FAILURE_RETRY_EXHAUSTED','FINANCIAL_RECONCILIATION_MISMATCH','UNSUPPORTED_EVENT_VERSION'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.tax_profile_status as enum ('NOT_REQUIRED_OR_UNKNOWN','INCOMPLETE','PENDING','VERIFIED','BLOCKED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.payout_profile_status as enum ('INCOMPLETE','PENDING','VERIFIED','BLOCKED'); exception when duplicate_object then null; end $$;
do $$ begin create type bros_affiliate.reconciliation_status as enum ('NOT_STARTED','PENDING','MATCHED','MISMATCH','RESOLVED'); exception when duplicate_object then null; end $$;

create table if not exists bros_affiliate.feature_flags (
  flag_name text primary key,
  enabled boolean not null default false,
  updated_at timestamptz not null default now(),
  updated_by text not null default 'migration'
);
insert into bros_affiliate.feature_flags(flag_name) values
 ('affiliate_referral_enabled'),('affiliate_attribution_enabled'),('affiliate_commission_processing_enabled'),('affiliate_portal_enabled'),('affiliate_payout_submission_enabled')
on conflict (flag_name) do nothing;

create sequence if not exists bros_affiliate.affiliate_code_seq minvalue 1 maxvalue 999999 no cycle;

create table if not exists bros_affiliate.affiliate_applications (
 id uuid primary key default extensions.gen_random_uuid(), application_key varchar(40) not null unique,
 person_id uuid, organization_id uuid, applicant_email extensions.citext not null, business_name text,
 website_url text check (website_url is null or website_url ~ '^https?://'), social_channels jsonb not null default '[]'::jsonb,
 audience_category varchar(64), estimated_audience_size bigint check (estimated_audience_size >= 0),
 promotion_methods jsonb not null default '[]'::jsonb, geographic_market jsonb,
 desired_affiliate_class bros_affiliate.affiliate_class not null, application_answers jsonb not null default '{}'::jsonb,
 status bros_affiliate.application_status not null default 'SUBMITTED', submitted_at timestamptz not null default now(),
 reviewed_at timestamptz, reviewer_actor_type bros_affiliate.audit_actor_type, reviewer_actor_id text,
 decision_reason_code text, review_notes text, linked_affiliate_id uuid unique, idempotency_key varchar(128) unique,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table if not exists bros_affiliate.affiliates (
 id uuid primary key default extensions.gen_random_uuid(),
 affiliate_code varchar(10) not null unique default ('AFF-' || lpad(nextval('bros_affiliate.affiliate_code_seq')::text,6,'0')),
 person_id uuid, organization_id uuid, source_application_id uuid unique references bros_affiliate.affiliate_applications(id),
 status bros_affiliate.affiliate_status not null default 'APPROVED_PENDING_TERMS', affiliate_class bros_affiliate.affiliate_class not null,
 display_name text not null, primary_email extensions.citext not null, business_name text, website_url text check (website_url is null or website_url ~ '^https?://'),
 primary_channels jsonb not null default '[]'::jsonb, promotion_methods jsonb not null default '[]'::jsonb,
 jurisdiction_context jsonb, tax_profile_status bros_affiliate.tax_profile_status not null default 'NOT_REQUIRED_OR_UNKNOWN',
 tax_provider_reference text, tax_verified_at timestamptz, payout_profile_status bros_affiliate.payout_profile_status not null default 'INCOMPLETE',
 activated_at timestamptz, suspended_at timestamptz, terminated_at timestamptz, inactive_at timestamptz,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 constraint affiliate_code_format check (affiliate_code ~ '^AFF-[0-9]{6}$')
);
alter table bros_affiliate.affiliate_applications drop constraint if exists affiliate_applications_linked_affiliate_id_fkey;
alter table bros_affiliate.affiliate_applications add constraint affiliate_applications_linked_affiliate_id_fkey foreign key (linked_affiliate_id) references bros_affiliate.affiliates(id);

create table if not exists bros_affiliate.affiliate_terms_acceptances (
 id uuid primary key default extensions.gen_random_uuid(), affiliate_id uuid not null references bros_affiliate.affiliates(id),
 terms_version varchar(64) not null, governed_document_reference text not null, terms_checksum varchar(128) not null,
 acceptance_method varchar(32) not null, accepted_at timestamptz not null, source_ip_hash text, user_agent_summary text,
 jurisdiction_context jsonb, evidence_reference text, created_at timestamptz not null default now(),
 unique(affiliate_id,terms_version,terms_checksum)
);

create table if not exists bros_affiliate.affiliate_referral_routes (
 id uuid primary key default extensions.gen_random_uuid(), route_key varchar(64) not null unique,
 affiliate_id uuid not null references bros_affiliate.affiliates(id), campaign_id text, destination_key text not null,
 product_or_topic text, content_id text, status bros_affiliate.route_status not null,
 effective_from timestamptz, effective_until timestamptz, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check (effective_until is null or effective_from is null or effective_until > effective_from)
);

create table if not exists bros_affiliate.affiliate_qr_routes (
 id uuid primary key default extensions.gen_random_uuid(), qr_code varchar(14) not null unique,
 affiliate_id uuid not null references bros_affiliate.affiliates(id), campaign_id text, destination_key text not null,
 product_or_topic text, content_id text, status bros_affiliate.route_status not null,
 effective_from timestamptz, expires_at timestamptz, last_destination_change_at timestamptz,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 constraint affiliate_qr_format check (qr_code ~ '^AQR-[0-9A-HJKMNP-TV-Z]{10}$')
);

create table if not exists bros_affiliate.affiliate_coupon_mappings (
 id uuid primary key default extensions.gen_random_uuid(), coupon_code_normalized extensions.citext not null unique,
 woocommerce_coupon_id text not null, affiliate_id uuid not null references bros_affiliate.affiliates(id), campaign_id text,
 attribution_enabled boolean not null default true, status bros_affiliate.mapping_status not null,
 effective_from timestamptz, effective_until timestamptz, governance_reference text not null,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);

create table if not exists bros_affiliate.affiliate_referral_events (
 id uuid primary key default extensions.gen_random_uuid(), event_key varchar(128) not null unique,
 affiliate_id uuid not null references bros_affiliate.affiliates(id), campaign_id text,
 referral_method bros_affiliate.referral_method not null, referral_route_id uuid references bros_affiliate.affiliate_referral_routes(id),
 qr_route_id uuid references bros_affiliate.affiliate_qr_routes(id), coupon_mapping_id uuid references bros_affiliate.affiliate_coupon_mappings(id),
 content_id text, source text, platform text, destination_key text not null, session_id text, anonymous_visitor_key text,
 occurred_at timestamptz not null, attribution_expires_at timestamptz not null,
 validation_status bros_affiliate.referral_validation_status not null, validation_reason text,
 client_ip_hash text, user_agent_summary text, metadata jsonb not null default '{}'::jsonb,
 correlation_id uuid not null, check (attribution_expires_at = occurred_at + interval '30 days')
);

create table if not exists bros_affiliate.affiliate_attribution_contexts (
 id uuid primary key default extensions.gen_random_uuid(), context_key text not null unique,
 session_id text, anonymous_visitor_key text, person_id uuid, affiliate_id uuid not null references bros_affiliate.affiliates(id),
 originating_referral_event_id uuid not null references bros_affiliate.affiliate_referral_events(id), campaign_id text,
 attribution_method bros_affiliate.attribution_method not null, attribution_started_at timestamptz not null,
 attribution_expires_at timestamptz not null, last_qualified_referral_at timestamptz not null,
 status bros_affiliate.attribution_context_status not null, version integer not null default 1 check (version > 0),
 updated_at timestamptz not null default now(),
 check (session_id is not null or anonymous_visitor_key is not null or person_id is not null)
);

create table if not exists bros_affiliate.affiliate_attribution_decisions (
 id uuid primary key default extensions.gen_random_uuid(), decision_key varchar(128) not null unique,
 order_id text not null, revenue_event_id text not null, affiliate_id uuid references bros_affiliate.affiliates(id),
 winning_referral_event_id uuid references bros_affiliate.affiliate_referral_events(id),
 coupon_mapping_id uuid references bros_affiliate.affiliate_coupon_mappings(id), campaign_id text,
 status bros_affiliate.attribution_status not null, method bros_affiliate.attribution_method,
 decision_version varchar(32) not null, window_started_at timestamptz, window_expires_at timestamptz,
 evidence jsonb not null, reason_code text not null, correlation_id uuid not null, created_at timestamptz not null default now(),
 unique(order_id,decision_version)
);

create table if not exists bros_affiliate.affiliate_commission_rules (
 id uuid primary key default extensions.gen_random_uuid(), rule_code varchar(64) not null unique, rule_name text not null,
 status bros_affiliate.commission_rule_status not null, affiliate_class bros_affiliate.affiliate_class,
 affiliate_id uuid references bros_affiliate.affiliates(id), product_id text, product_class text, campaign_id text,
 rate_type bros_affiliate.commission_rate_type not null, rate_value numeric(12,8) not null,
 currency_code char(3), effective_from timestamptz not null, effective_until timestamptz,
 precedence_level smallint not null check (precedence_level between 1 and 6), priority integer not null default 0,
 governance_reference text not null, approved_by_actor_id text not null,
 supersedes_rule_id uuid references bros_affiliate.affiliate_commission_rules(id), rule_version integer not null check (rule_version > 0),
 created_at timestamptz not null default now(),
 check (rate_type = 'PERCENTAGE' and rate_value between 0 and 1),
 check (effective_until is null or effective_until > effective_from)
);

create table if not exists bros_affiliate.affiliate_commissions (
 id uuid primary key default extensions.gen_random_uuid(), commission_code varchar(32) not null unique,
 affiliate_id uuid not null references bros_affiliate.affiliates(id), woocommerce_order_id text not null,
 attribution_decision_id uuid not null references bros_affiliate.affiliate_attribution_decisions(id), currency_code char(3) not null,
 qualifying_revenue_total numeric(20,6) not null check (qualifying_revenue_total >= 0),
 commission_amount_total numeric(20,6) not null check (commission_amount_total >= 0),
 current_status bros_affiliate.commission_status not null, hold_until timestamptz not null,
 dispute_status bros_affiliate.dispute_status not null default 'NONE', compliance_hold boolean not null default false,
 rules_version text not null, attribution_version text not null, calculation_version text not null,
 created_at timestamptz not null default now(), approved_at timestamptz, payable_at timestamptz, paid_at timestamptz, reversed_at timestamptz,
 updated_at timestamptz not null default now(), unique(affiliate_id,woocommerce_order_id)
);

create table if not exists bros_affiliate.affiliate_order_line_commissions (
 id uuid primary key default extensions.gen_random_uuid(), commission_id uuid not null references bros_affiliate.affiliate_commissions(id),
 woocommerce_order_id text not null, woocommerce_order_line_id text not null,
 affiliate_id uuid not null references bros_affiliate.affiliates(id), product_id text not null, product_class text,
 quantity numeric(20,6) not null check (quantity > 0), currency_code char(3) not null,
 gross_line_merchandise numeric(20,6) not null, line_discount numeric(20,6) not null default 0,
 line_tax numeric(20,6) not null default 0, line_shipping_allocated numeric(20,6) not null default 0,
 line_refunded_amount numeric(20,6) not null default 0, qualifying_revenue numeric(20,6) not null check (qualifying_revenue >= 0),
 commission_rule_id uuid not null references bros_affiliate.affiliate_commission_rules(id), commission_rule_version integer not null,
 commission_rate numeric(12,8) not null check (commission_rate between 0 and 1),
 commission_amount numeric(20,6) not null check (commission_amount >= 0), calculation_version varchar(32) not null,
 attribution_decision_id uuid not null references bros_affiliate.affiliate_attribution_decisions(id), created_at timestamptz not null default now(),
 unique(woocommerce_order_id,woocommerce_order_line_id,affiliate_id,calculation_version)
);

create table if not exists bros_affiliate.affiliate_commission_ledger (
 id uuid primary key default extensions.gen_random_uuid(), ledger_event_key varchar(128) not null unique,
 commission_id uuid not null references bros_affiliate.affiliate_commissions(id), affiliate_id uuid not null references bros_affiliate.affiliates(id),
 woocommerce_order_id text not null, commission_line_id uuid references bros_affiliate.affiliate_order_line_commissions(id),
 event_type bros_affiliate.commission_event_type not null, amount_delta numeric(20,6) not null,
 currency_code char(3) not null, resulting_commission_balance numeric(20,6) not null,
 reason_code text not null, actor_type bros_affiliate.audit_actor_type not null, actor_id text not null,
 evidence_reference text, source_event_id text, correlation_id uuid not null,
 occurred_at timestamptz not null, created_at timestamptz not null default now()
);

create table if not exists bros_affiliate.affiliate_risk_events (
 id uuid primary key default extensions.gen_random_uuid(), affiliate_id uuid references bros_affiliate.affiliates(id),
 woocommerce_order_id text, commission_id uuid references bros_affiliate.affiliate_commissions(id),
 risk_type bros_affiliate.risk_event_type not null, severity bros_affiliate.risk_severity not null,
 evidence jsonb not null default '{}'::jsonb, review_status bros_affiliate.risk_review_status not null default 'OPEN',
 reviewer_actor_id text, resolution_code text, created_at timestamptz not null default now(), reviewed_at timestamptz, resolved_at timestamptz,
 correlation_id uuid not null
);

create table if not exists bros_affiliate.affiliate_disputes (
 id uuid primary key default extensions.gen_random_uuid(), dispute_code varchar(32) not null unique,
 affiliate_id uuid not null references bros_affiliate.affiliates(id), commission_id uuid references bros_affiliate.affiliate_commissions(id),
 woocommerce_order_id text, dispute_type bros_affiliate.dispute_type not null, statement_or_notice_at timestamptz not null,
 submitted_at timestamptz not null, within_standard_window boolean not null, claim_text text not null,
 evidence jsonb not null default '[]'::jsonb, status bros_affiliate.dispute_status not null,
 assigned_actor_id text, decision text, decision_reason text, adjustment_ledger_event_id uuid,
 resolved_at timestamptz, created_at timestamptz not null default now()
);

create table if not exists bros_affiliate.affiliate_attribution_overrides (
 id uuid primary key default extensions.gen_random_uuid(), order_id text not null,
 original_attribution_decision_id uuid not null references bros_affiliate.affiliate_attribution_decisions(id),
 replacement_affiliate_id uuid references bros_affiliate.affiliates(id),
 replacement_referral_event_id uuid references bros_affiliate.affiliate_referral_events(id),
 reason_code text not null, evidence jsonb not null, authorized_actor_type bros_affiliate.audit_actor_type not null,
 authorized_actor_id text not null, created_at timestamptz not null default now(),
 replacement_attribution_decision_id uuid not null references bros_affiliate.affiliate_attribution_decisions(id)
);

create table if not exists bros_affiliate.affiliate_payout_batches (
 id uuid primary key default extensions.gen_random_uuid(), batch_code varchar(40) not null unique,
 period_start date not null, period_end date not null, currency_code char(3) not null,
 status bros_affiliate.payout_status not null, total_affiliates integer not null check (total_affiliates >= 0),
 total_amount numeric(20,6) not null check (total_amount >= 0), prepared_by_actor_id text not null, prepared_at timestamptz not null,
 approved_by_actor_id text, approved_at timestamptz, submitted_at timestamptz, completed_at timestamptz,
 provider_code text, external_batch_reference text, reconciliation_status bros_affiliate.reconciliation_status not null,
 created_at timestamptz not null default now(), check (period_end >= period_start)
);

create table if not exists bros_affiliate.affiliate_payout_items (
 id uuid primary key default extensions.gen_random_uuid(), payout_batch_id uuid not null references bros_affiliate.affiliate_payout_batches(id),
 affiliate_id uuid not null references bros_affiliate.affiliates(id), currency_code char(3) not null,
 amount numeric(20,6) not null check (amount > 0), status bros_affiliate.payout_item_status not null,
 provider_beneficiary_reference text not null, provider_idempotency_key varchar(128) not null unique,
 external_transaction_id text, failure_code text, failure_detail text, paid_at timestamptz,
 created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists bros_affiliate.affiliate_payout_item_commissions (
 payout_item_id uuid not null references bros_affiliate.affiliate_payout_items(id),
 commission_id uuid not null references bros_affiliate.affiliate_commissions(id),
 included_amount numeric(20,6) not null check (included_amount > 0), primary key(payout_item_id,commission_id)
);

create table if not exists bros_affiliate.affiliate_quarantine_events (
 id uuid primary key default extensions.gen_random_uuid(), quarantine_key varchar(128) not null unique,
 source_event_type text not null, source_event_id text, reason bros_affiliate.quarantine_reason not null,
 status bros_affiliate.quarantine_status not null default 'OPEN', payload_reference text not null,
 payload_hash varchar(128) not null, error_class text not null, error_detail text,
 correlation_id uuid not null, retry_count integer not null default 0 check (retry_count >= 0), next_retry_at timestamptz,
 review_actor_id text, resolution_note text, created_at timestamptz not null default now(), resolved_at timestamptz
);

create table if not exists bros_affiliate.affiliate_audit_events (
 id uuid primary key default extensions.gen_random_uuid(), audit_key varchar(128) not null unique,
 actor_type bros_affiliate.audit_actor_type not null, actor_id text not null, action text not null,
 entity_type text not null, entity_id text not null, before_state jsonb, after_state jsonb,
 reason_code text, evidence_reference text, correlation_id uuid not null, occurred_at timestamptz not null
);

create index if not exists affiliate_applications_status_idx on bros_affiliate.affiliate_applications(status);
create index if not exists affiliate_applications_email_idx on bros_affiliate.affiliate_applications(applicant_email);
create index if not exists affiliate_applications_submitted_idx on bros_affiliate.affiliate_applications(submitted_at);
create index if not exists affiliate_referral_events_session_idx on bros_affiliate.affiliate_referral_events(session_id,occurred_at desc);
create index if not exists affiliate_referral_events_visitor_idx on bros_affiliate.affiliate_referral_events(anonymous_visitor_key,occurred_at desc);
create index if not exists affiliate_attribution_order_idx on bros_affiliate.affiliate_attribution_decisions(order_id);
create index if not exists affiliate_commissions_affiliate_status_idx on bros_affiliate.affiliate_commissions(affiliate_id,current_status,currency_code);
create index if not exists affiliate_ledger_commission_idx on bros_affiliate.affiliate_commission_ledger(commission_id,occurred_at);
create index if not exists affiliate_quarantine_status_idx on bros_affiliate.affiliate_quarantine_events(status,created_at);

create or replace function private.bros_has_role(required_role text) returns boolean
language sql stable security invoker set search_path = '' as $$
 select coalesce((select jsonb_typeof(auth.jwt()->'app_metadata'->'bros_roles')='array' and (auth.jwt()->'app_metadata'->'bros_roles') ? required_role),false)
$$;
create or replace function private.bros_affiliate_id() returns uuid
language sql stable security invoker set search_path = '' as $$
 select nullif(auth.jwt()->'app_metadata'->>'affiliate_id','')::uuid
$$;
revoke all on function private.bros_has_role(text) from public;
revoke all on function private.bros_affiliate_id() from public;
grant usage on schema private to authenticated;
grant execute on function private.bros_has_role(text), private.bros_affiliate_id() to authenticated;

create or replace function private.reject_immutable_affiliate_row() returns trigger
language plpgsql security invoker set search_path = '' as $$ begin raise exception 'AFFILIATE_IMMUTABLE_ROW'; end $$;
revoke all on function private.reject_immutable_affiliate_row() from public;

drop trigger if exists affiliate_terms_immutable on bros_affiliate.affiliate_terms_acceptances;
create trigger affiliate_terms_immutable before update or delete on bros_affiliate.affiliate_terms_acceptances for each row execute function private.reject_immutable_affiliate_row();

drop trigger if exists affiliate_referral_events_immutable on bros_affiliate.affiliate_referral_events;
create trigger affiliate_referral_events_immutable before update or delete on bros_affiliate.affiliate_referral_events for each row execute function private.reject_immutable_affiliate_row();

drop trigger if exists affiliate_attribution_decisions_immutable on bros_affiliate.affiliate_attribution_decisions;
create trigger affiliate_attribution_decisions_immutable before update or delete on bros_affiliate.affiliate_attribution_decisions for each row execute function private.reject_immutable_affiliate_row();

drop trigger if exists affiliate_ledger_immutable on bros_affiliate.affiliate_commission_ledger;
create trigger affiliate_ledger_immutable before update or delete on bros_affiliate.affiliate_commission_ledger for each row execute function private.reject_immutable_affiliate_row();

drop trigger if exists affiliate_overrides_immutable on bros_affiliate.affiliate_attribution_overrides;
create trigger affiliate_overrides_immutable before update or delete on bros_affiliate.affiliate_attribution_overrides for each row execute function private.reject_immutable_affiliate_row();

drop trigger if exists affiliate_audit_immutable on bros_affiliate.affiliate_audit_events;
create trigger affiliate_audit_immutable before update or delete on bros_affiliate.affiliate_audit_events for each row execute function private.reject_immutable_affiliate_row();

do $$ declare t text; begin
 foreach t in array array['affiliate_applications','affiliates','affiliate_terms_acceptances','affiliate_referral_routes','affiliate_qr_routes','affiliate_coupon_mappings','affiliate_referral_events','affiliate_attribution_contexts','affiliate_attribution_decisions','affiliate_commission_rules','affiliate_commissions','affiliate_order_line_commissions','affiliate_commission_ledger','affiliate_risk_events','affiliate_disputes','affiliate_attribution_overrides','affiliate_payout_batches','affiliate_payout_items','affiliate_payout_item_commissions','affiliate_quarantine_events','affiliate_audit_events'] loop
   execute format('alter table bros_affiliate.%I enable row level security',t);
   execute format('revoke all on bros_affiliate.%I from anon, authenticated',t);
 end loop;
end $$;

grant select on bros_affiliate.affiliates,bros_affiliate.affiliate_referral_routes,bros_affiliate.affiliate_qr_routes,bros_affiliate.affiliate_commissions,bros_affiliate.affiliate_payout_items,bros_affiliate.affiliate_disputes to authenticated;

drop policy if exists affiliate_own_profile on bros_affiliate.affiliates;
create policy affiliate_own_profile on bros_affiliate.affiliates for select to authenticated using (id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')) or (select private.bros_has_role('AFFILIATE_OPERATOR')) or (select private.bros_has_role('SUPPORT_OPERATOR')));

drop policy if exists affiliate_own_links on bros_affiliate.affiliate_referral_routes;
create policy affiliate_own_links on bros_affiliate.affiliate_referral_routes for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')) or (select private.bros_has_role('AFFILIATE_OPERATOR')));

drop policy if exists affiliate_own_qr on bros_affiliate.affiliate_qr_routes;
create policy affiliate_own_qr on bros_affiliate.affiliate_qr_routes for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')) or (select private.bros_has_role('AFFILIATE_OPERATOR')));

drop policy if exists affiliate_own_commissions on bros_affiliate.affiliate_commissions;
create policy affiliate_own_commissions on bros_affiliate.affiliate_commissions for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')) or (select private.bros_has_role('FINANCIAL_APPROVER')));

drop policy if exists affiliate_own_payouts on bros_affiliate.affiliate_payout_items;
create policy affiliate_own_payouts on bros_affiliate.affiliate_payout_items for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')) or (select private.bros_has_role('FINANCIAL_APPROVER')));

drop policy if exists affiliate_own_disputes on bros_affiliate.affiliate_disputes;
create policy affiliate_own_disputes on bros_affiliate.affiliate_disputes for select to authenticated using (affiliate_id=(select private.bros_affiliate_id()) or (select private.bros_has_role('PROJECT_OWNER')) or (select private.bros_has_role('AFFILIATE_OPERATOR')) or (select private.bros_has_role('SUPPORT_OPERATOR')));

comment on schema bros_affiliate is 'AFF-001 controlled non-production Affiliate MVP. Feature gates default OFF.';
comment on column bros_affiliate.affiliate_applications.person_id is 'Nullable Jetpack/BROS identity reference; FK deferred until governed person table exists.';
comment on column bros_affiliate.affiliate_applications.organization_id is 'Nullable governed organization reference; FK deferred until canonical organization table exists.';

