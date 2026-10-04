-- G9E.1 authoritative synthetic-only scope. Inert until a row is inserted by
-- an explicitly authorized server-side operation and the corresponding global
-- gate is separately enabled.

create table if not exists bros_affiliate.synthetic_test_scopes (
  scope_id uuid primary key default extensions.gen_random_uuid(),
  classification text not null check (classification = 'TEST_SYNTHETIC_NON_PRODUCTION_PERSON'),
  wordpress_user_id bigint not null unique,
  affiliate_id uuid not null unique references bros_affiliate.affiliates(id),
  affiliate_code varchar(10) not null unique check (affiliate_code ~ '^AFF-[0-9]{6}$'),
  referral_token varchar(64) not null unique,
  destination_key text not null check (destination_key like 'SYNTH-%'),
  campaign_id text not null check (campaign_id like 'G9E-SYNTH-%'),
  event_id text not null unique check (event_id like 'G9E-SYNTH-%'),
  order_id text not null unique check (order_id like 'G9E-SYNTH-%'),
  active boolean not null default false,
  expires_at timestamptz not null,
  created_by_actor_id text not null,
  created_at timestamptz not null default now(),
  check (expires_at > created_at)
);

create table if not exists bros_affiliate.synthetic_scope_audit (
  audit_id uuid primary key default extensions.gen_random_uuid(),
  idempotency_key text unique,
  operation text not null check (operation in ('portal','referral','attribution','commission')),
  actor text not null,
  synthetic_identity varchar(10),
  event_or_order_id text,
  gate_name text not null,
  gate_state boolean not null,
  scope_result text not null check (scope_result in ('MATCH','NO_MATCH')),
  decision text not null check (decision in ('ALLOW','DENY')),
  reason text not null,
  occurred_at timestamptz not null default now(),
  evidence jsonb not null default '{}'::jsonb,
  check (not (evidence ?| array['raw_invitation_token','cookie','credential','secret']))
);

alter table bros_affiliate.synthetic_test_scopes enable row level security;
alter table bros_affiliate.synthetic_scope_audit enable row level security;

revoke all on bros_affiliate.synthetic_test_scopes from public, anon, authenticated;
revoke all on bros_affiliate.synthetic_scope_audit from public, anon, authenticated;
grant select on bros_affiliate.synthetic_test_scopes to service_role;
grant select, insert on bros_affiliate.synthetic_scope_audit to service_role;

create trigger synthetic_scope_audit_immutable
before update or delete on bros_affiliate.synthetic_scope_audit
for each row execute function private.reject_immutable_affiliate_row();

comment on table bros_affiliate.synthetic_test_scopes is
  'G9E bounded test identities. No client-supplied value may create or widen a scope.';
