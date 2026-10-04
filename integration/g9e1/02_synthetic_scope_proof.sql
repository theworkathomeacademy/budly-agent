\set ON_ERROR_STOP on

insert into bros_affiliate.synthetic_test_scopes(
  scope_id,classification,wordpress_user_id,affiliate_id,affiliate_code,
  referral_token,destination_key,campaign_id,event_id,order_id,active,expires_at,created_by_actor_id
) values (
  '91000000-0000-0000-0000-000000000001','TEST_SYNTHETIC_NON_PRODUCTION_PERSON',990001,
  '50000000-0000-0000-0000-000000000001','AFF-900001','G9ESYNTH900001',
  'SYNTH-WELLNESS','G9E-SYNTH-CAMPAIGN-001','G9E-SYNTH-EVENT-001','G9E-SYNTH-ORDER-001',
  true,now()+interval '30 minutes','d-mac'
) on conflict (scope_id) do nothing;

insert into bros_affiliate.synthetic_scope_audit(
  idempotency_key,operation,actor,synthetic_identity,event_or_order_id,gate_name,
  gate_state,scope_result,decision,reason,evidence
) values
('g9e-proof-allow','attribution','service:g9e','AFF-900001','G9E-SYNTH-EVENT-001',
 'affiliate_attribution_enabled',true,'MATCH','ALLOW','TRUSTED_SYNTHETIC_ATTRIBUTION_MATCH',
 '{"classification":"TEST_SYNTHETIC_NON_PRODUCTION_PERSON","order_id":"G9E-SYNTH-ORDER-001"}'),
('g9e-proof-deny','attribution','service:g9e',null,'REAL-WOO-ORDER-001',
 'affiliate_attribution_enabled',true,'NO_MATCH','DENY','TRUSTED_EVENT_CLASSIFICATION_MISMATCH',
 '{"classification":"PRODUCTION","order_id":"REAL-WOO-ORDER-001"}')
on conflict (idempotency_key) do nothing;

do $$
declare enabled_flags integer; scope_count integer; audit_count integer;
begin
  select count(*) into enabled_flags from bros_affiliate.feature_flags where enabled;
  if enabled_flags <> 0 then raise exception 'PRODUCTION_FLAGS_CHANGED'; end if;
  select count(*) into scope_count from bros_affiliate.synthetic_test_scopes where scope_id='91000000-0000-0000-0000-000000000001' and active and expires_at > now();
  if scope_count <> 1 then raise exception 'SYNTHETIC_SCOPE_NOT_PERSISTED'; end if;
  select count(*) into audit_count from bros_affiliate.synthetic_scope_audit where idempotency_key in ('g9e-proof-allow','g9e-proof-deny');
  if audit_count <> 2 then raise exception 'SCOPE_AUDIT_NOT_PERSISTED'; end if;
end $$;

select 'G9E1_SYNTHETIC_SCOPE_PROOF_PASS' as result,
       (select count(*) from bros_affiliate.synthetic_test_scopes) as scopes,
       (select count(*) from bros_affiliate.synthetic_scope_audit) as audit_events,
       (select count(*) from bros_affiliate.feature_flags where enabled) as enabled_production_flags;
