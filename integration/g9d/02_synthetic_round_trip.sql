\set ON_ERROR_STOP on

set role service_role;
set request.jwt.claims = '{"sub":"00000000-0000-0000-0000-000000000099","app_metadata":{"bros_roles":["SYSTEM_SERVICE"]}}';

insert into bros_affiliate.affiliate_invitations(id,invitation_key,token_hash,intended_email,intended_class,classification,expires_at)
values('10000000-0000-0000-0000-000000000001','G9D-SYNTH-INV-001',encode(extensions.digest('never-persist-this-raw-token','sha256'),'hex'),'synthetic-affiliate@example.invalid','STANDARD','TEST_SYNTHETIC_NON_PRODUCTION_PERSON',now()+interval '1 day');

insert into bros_affiliate.affiliate_audit_events(id,audit_key,actor_type,actor_id,action,entity_type,entity_id,after_state,reason_code,evidence_reference,correlation_id,occurred_at)
values('20000000-0000-0000-0000-000000000001','audit-invitation','SYSTEM_SERVICE','g9d-service','INVITATION_CREATED','affiliate_invitation','G9D-SYNTH-INV-001','{"classification":"TEST_SYNTHETIC_NON_PRODUCTION_PERSON"}','SYNTHETIC_PROOF','G9D-EVIDENCE-INV', '30000000-0000-0000-0000-000000000001',now());

insert into bros_affiliate.affiliate_applications(id,application_key,applicant_email,social_channels,desired_affiliate_class,application_answers,status,idempotency_key)
values('40000000-0000-0000-0000-000000000001','G9D-SYNTH-APP-001','synthetic-affiliate@example.invalid','["synthetic://instagram/g9d"]','STANDARD','{"classification":"TEST_SYNTHETIC_NON_PRODUCTION_PERSON"}','SUBMITTED','g9d-app-v1');
update bros_affiliate.affiliate_invitations set used_at=now() where invitation_key='G9D-SYNTH-INV-001';
insert into bros_affiliate.affiliate_audit_events(id,audit_key,actor_type,actor_id,action,entity_type,entity_id,after_state,reason_code,evidence_reference,correlation_id,occurred_at)
values('20000000-0000-0000-0000-000000000002','audit-application','AFFILIATE_USER','synthetic-applicant','APPLICATION_SUBMITTED','affiliate_application','G9D-SYNTH-APP-001','{"status":"SUBMITTED"}','PRIVATE_INVITATION','G9D-EVIDENCE-APP','30000000-0000-0000-0000-000000000001',now());

update bros_affiliate.affiliate_applications set status='APPROVED',reviewed_at=now(),reviewer_actor_type='PROJECT_OWNER',reviewer_actor_id='d-mac',decision_reason_code='BOUNDED_SYNTHETIC_PROOF' where id='40000000-0000-0000-0000-000000000001';
insert into bros_affiliate.affiliates(id,affiliate_code,person_id,source_application_id,status,affiliate_class,display_name,primary_email,primary_channels,tax_profile_status,payout_profile_status,activated_at)
values('50000000-0000-0000-0000-000000000001','AFF-900001','60000000-0000-0000-0000-000000000001','40000000-0000-0000-0000-000000000001','ACTIVE','STANDARD','G9D Synthetic Affiliate','synthetic-affiliate@example.invalid','["synthetic://instagram/g9d"]','NOT_REQUIRED_OR_UNKNOWN','VERIFIED',now());
update bros_affiliate.affiliate_applications set linked_affiliate_id='50000000-0000-0000-0000-000000000001' where id='40000000-0000-0000-0000-000000000001';
insert into bros_affiliate.affiliate_audit_events(id,audit_key,actor_type,actor_id,action,entity_type,entity_id,after_state,reason_code,evidence_reference,correlation_id,occurred_at)
values('20000000-0000-0000-0000-000000000003','audit-owner-decision','PROJECT_OWNER','d-mac','APPLICATION_APPROVED','affiliate_application','G9D-SYNTH-APP-001','{"status":"APPROVED","affiliate_code":"AFF-900001"}','BOUNDED_SYNTHETIC_PROOF','G9D-EVIDENCE-OWNER','30000000-0000-0000-0000-000000000001',now());

insert into bros_affiliate.affiliate_terms_acceptances(id,affiliate_id,terms_version,governed_document_reference,terms_checksum,acceptance_method,accepted_at,evidence_reference)
values('70000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000001','SYNTHETIC-TERMS-v1','G9D-TERMS','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','SYNTHETIC_UI',now(),'G9D-EVIDENCE-TERMS');
insert into bros_affiliate.affiliate_referral_routes(id,route_key,affiliate_id,destination_key,status,effective_from)
values('80000000-0000-0000-0000-000000000001','G9DREF900001','50000000-0000-0000-0000-000000000001','SYNTH-WELLNESS','ACTIVE',now());
insert into bros_affiliate.affiliate_qr_routes(id,qr_code,affiliate_id,destination_key,status,effective_from)
values('81000000-0000-0000-0000-000000000001','AQR-7M4D9X2KQP','50000000-0000-0000-0000-000000000001','SYNTH-WELLNESS','ACTIVE',now());
insert into bros_affiliate.affiliate_audit_events(id,audit_key,actor_type,actor_id,action,entity_type,entity_id,after_state,reason_code,evidence_reference,correlation_id,occurred_at)
values
('20000000-0000-0000-0000-000000000004','audit-terms','AFFILIATE_USER','synthetic-user','TERMS_ACCEPTED','affiliate','AFF-900001','{"terms_version":"SYNTHETIC-TERMS-v1"}','AFFILIATE_ACCEPTANCE','G9D-EVIDENCE-TERMS','30000000-0000-0000-0000-000000000001',now()),
('20000000-0000-0000-0000-000000000005','audit-assets','PROJECT_OWNER','d-mac','REFERRAL_ASSETS_CREATED','affiliate','AFF-900001','{"canonical":"/r/G9DREF900001","vanity":"/go/g9d-synthetic","qr":"AQR-7M4D9X2KQP"}','OWNER_AUTHORIZED','G9D-EVIDENCE-ASSETS','30000000-0000-0000-0000-000000000001',now());

insert into bros_affiliate.affiliate_referral_events(id,event_key,affiliate_id,referral_method,referral_route_id,destination_key,anonymous_visitor_key,occurred_at,attribution_expires_at,validation_status,correlation_id,metadata)
values('90000000-0000-0000-0000-000000000001','G9D-REF-EVENT-001','50000000-0000-0000-0000-000000000001','LINK','80000000-0000-0000-0000-000000000001','SYNTH-WELLNESS','g9d-visitor',now()-interval '1 hour',now()-interval '1 hour'+interval '30 days','QUALIFIED','30000000-0000-0000-0000-000000000001','{"synthetic":true}');

select * from public.bros_ingest_revenue_event('{"schema_version":"bros.revenue_event.v1","source_system":"woocommerce","source_event_id":"g9d-webhook:g9d-delivery-001","source_order_id":"G9D-ORDER-001","order_status":"completed","currency":"USD","gross_amount":200.00,"discount_amount":0,"shipping_amount":0,"tax_amount":0,"line_items":[{"source_line_id":"1","source_product_id":"SYNTH-WELLNESS","sku":"WELLNESS-SYNTH-001","quantity":1,"line_total":200.00,"line_tax":0,"product_family":"wellness"}],"commerce_correlation":{"status":"linked","affiliate_referral_event_id":"90000000-0000-0000-0000-000000000001"},"payload_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}'::jsonb);
select * from public.bros_ingest_revenue_event('{"schema_version":"bros.revenue_event.v1","source_system":"woocommerce","source_event_id":"g9d-webhook:g9d-delivery-001","source_order_id":"G9D-ORDER-001","order_status":"completed","currency":"USD","gross_amount":200.00,"discount_amount":0,"shipping_amount":0,"tax_amount":0,"line_items":[{"source_line_id":"1","source_product_id":"SYNTH-WELLNESS","sku":"WELLNESS-SYNTH-001","quantity":1,"line_total":200.00,"line_tax":0,"product_family":"wellness"}],"commerce_correlation":{"status":"linked","affiliate_referral_event_id":"90000000-0000-0000-0000-000000000001"},"payload_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}'::jsonb);

insert into bros_affiliate.affiliate_commission_rules(id,rule_code,rule_name,status,product_id,product_class,rate_type,rate_value,effective_from,precedence_level,governance_reference,approved_by_actor_id,rule_version)
values('a0000000-0000-0000-0000-000000000001','G9D-WELLNESS-30','G9D synthetic governed wellness rate','APPROVED','SYNTH-WELLNESS','WELLNESS_PHYSICAL_30','PERCENTAGE',0.30000000,now()-interval '1 day',1,'G9D-CCSS-SYNTH','d-mac',1);
insert into bros_affiliate.affiliate_attribution_decisions(id,decision_key,order_id,revenue_event_id,affiliate_id,winning_referral_event_id,status,method,decision_version,window_started_at,window_expires_at,evidence,reason_code,correlation_id)
values('b0000000-0000-0000-0000-000000000001','G9D-ATTR-001','G9D-ORDER-001','g9d-webhook:g9d-delivery-001','50000000-0000-0000-0000-000000000001','90000000-0000-0000-0000-000000000001','ATTRIBUTED','REFERRAL_LINK','affiliate-attribution-v1',now()-interval '1 hour',now()+interval '30 days','{"source":"bros.revenue_event.v1","synthetic":true}','LAST_QUALIFIED_REFERRAL','30000000-0000-0000-0000-000000000001');
insert into bros_affiliate.affiliate_commissions(id,commission_code,affiliate_id,woocommerce_order_id,attribution_decision_id,currency_code,qualifying_revenue_total,commission_amount_total,current_status,hold_until,rules_version,attribution_version,calculation_version)
values('c0000000-0000-0000-0000-000000000001','G9D-COMM-001','50000000-0000-0000-0000-000000000001','G9D-ORDER-001','b0000000-0000-0000-0000-000000000001','USD',200.000000,60.000000,'PENDING',now()-interval '1 second','G9D-CCSS-SYNTH','affiliate-attribution-v1','affiliate-commission-v1');
insert into bros_affiliate.affiliate_order_line_commissions(id,commission_id,woocommerce_order_id,woocommerce_order_line_id,affiliate_id,product_id,product_class,quantity,currency_code,gross_line_merchandise,qualifying_revenue,commission_rule_id,commission_rule_version,commission_rate,commission_amount,calculation_version,attribution_decision_id)
values('d0000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','G9D-ORDER-001','1','50000000-0000-0000-0000-000000000001','SYNTH-WELLNESS','WELLNESS_PHYSICAL_30',1,'USD',200.000000,200.000000,'a0000000-0000-0000-0000-000000000001',1,0.30000000,60.000000,'affiliate-commission-v1','b0000000-0000-0000-0000-000000000001');
insert into bros_affiliate.affiliate_commission_ledger(id,ledger_event_key,commission_id,affiliate_id,woocommerce_order_id,commission_line_id,event_type,amount_delta,currency_code,resulting_commission_balance,reason_code,actor_type,actor_id,evidence_reference,source_event_id,correlation_id,occurred_at)
values('e0000000-0000-0000-0000-000000000001','G9D-LEDGER-CREATED','c0000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000001','G9D-ORDER-001','d0000000-0000-0000-0000-000000000001','COMMISSION_CREATED',60.000000,'USD',60.000000,'ELIGIBLE_ORDER','SYSTEM_SERVICE','g9d-service','G9D-EVIDENCE-REVENUE','g9d-webhook:g9d-delivery-001','30000000-0000-0000-0000-000000000001',now());

update bros_affiliate.affiliate_commissions set current_status='PAYABLE',payable_at=now(),updated_at=now() where id='c0000000-0000-0000-0000-000000000001' and hold_until<=now();
insert into bros_affiliate.affiliate_commission_ledger(id,ledger_event_key,commission_id,affiliate_id,woocommerce_order_id,event_type,amount_delta,currency_code,resulting_commission_balance,reason_code,actor_type,actor_id,evidence_reference,source_event_id,correlation_id,occurred_at)
values('e0000000-0000-0000-0000-000000000002','G9D-LEDGER-PAYABLE','c0000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000001','G9D-ORDER-001','COMMISSION_PAYABLE',0,'USD',60.000000,'HOLD_COMPLETE','SYSTEM_SERVICE','g9d-service','G9D-EVIDENCE-MATURITY','g9d-maturity','30000000-0000-0000-0000-000000000001',now());
insert into bros_affiliate.affiliate_payout_batches(id,batch_code,period_start,period_end,currency_code,status,total_affiliates,total_amount,prepared_by_actor_id,prepared_at,reconciliation_status)
values('f0000000-0000-0000-0000-000000000001','G9D-PAYOUT-READY-001',current_date-1,current_date,'USD','UNDER_REVIEW',1,60.000000,'d-mac',now(),'NOT_STARTED');
insert into bros_affiliate.affiliate_payout_items(id,payout_batch_id,affiliate_id,currency_code,amount,status,provider_beneficiary_reference,provider_idempotency_key)
values('f1000000-0000-0000-0000-000000000001','f0000000-0000-0000-0000-000000000001','50000000-0000-0000-0000-000000000001','USD',60.000000,'PREPARED','SYNTHETIC-NO-PROVIDER','G9D-NO-SUBMISSION-001');
insert into bros_affiliate.affiliate_payout_item_commissions(payout_item_id,commission_id,included_amount)
values('f1000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001',60.000000);
insert into bros_affiliate.affiliate_audit_events(id,audit_key,actor_type,actor_id,action,entity_type,entity_id,after_state,reason_code,evidence_reference,correlation_id,occurred_at)
values
('20000000-0000-0000-0000-000000000006','audit-referral','SYSTEM_SERVICE','g9d-service','REFERRAL_RECORDED','referral_event','G9D-REF-EVENT-001','{"qualified":true}','VALID_SYNTHETIC_REFERRAL','G9D-EVIDENCE-REFERRAL','30000000-0000-0000-0000-000000000001',now()),
('20000000-0000-0000-0000-000000000007','audit-attribution','SYSTEM_SERVICE','g9d-service','ATTRIBUTION_DECIDED','order','G9D-ORDER-001','{"affiliate_code":"AFF-900001"}','LAST_QUALIFIED_REFERRAL','G9D-EVIDENCE-ATTRIBUTION','30000000-0000-0000-0000-000000000001',now()),
('20000000-0000-0000-0000-000000000008','audit-commission','SYSTEM_SERVICE','g9d-service','COMMISSION_CREATED','commission','G9D-COMM-001','{"amount":"60.000000","status":"PENDING"}','ELIGIBLE_ORDER','G9D-EVIDENCE-COMMISSION','30000000-0000-0000-0000-000000000001',now()),
('20000000-0000-0000-0000-000000000009','audit-maturity','SYSTEM_SERVICE','g9d-service','COMMISSION_MATURED','commission','G9D-COMM-001','{"amount":"60.000000","status":"PAYABLE"}','HOLD_COMPLETE','G9D-EVIDENCE-MATURITY','30000000-0000-0000-0000-000000000001',now()),
('20000000-0000-0000-0000-000000000010','audit-payout-ready','PROJECT_OWNER','d-mac','PAYOUT_READINESS_PREPARED','payout_batch','G9D-PAYOUT-READY-001','{"amount":"60.000000","status":"UNDER_REVIEW","submitted":false}','OWNER_VISIBILITY_ONLY','G9D-EVIDENCE-PAYOUT','30000000-0000-0000-0000-000000000001',now());

-- Affiliate B exists only to prove tenant isolation.
insert into bros_affiliate.affiliates(id,affiliate_code,person_id,status,affiliate_class,display_name,primary_email,primary_channels)
values('50000000-0000-0000-0000-000000000002','AFF-900002','60000000-0000-0000-0000-000000000002','ACTIVE','STANDARD','G9D Synthetic Affiliate B','synthetic-b@example.invalid','[]');

reset role;

do $$
declare flags_on integer; raw_token_matches integer; duplicate_events integer; audit_count integer;
begin
  select count(*) into flags_on from bros_affiliate.feature_flags where enabled;
  if flags_on <> 0 then raise exception 'PRODUCTION_FLAGS_CHANGED'; end if;
  select count(*) into raw_token_matches from bros_affiliate.affiliate_invitations where token_hash='never-persist-this-raw-token';
  if raw_token_matches <> 0 then raise exception 'RAW_TOKEN_PERSISTED'; end if;
  select count(*) into duplicate_events from public.revenue_events where source_event_id='g9d-webhook:g9d-delivery-001';
  if duplicate_events <> 1 then raise exception 'EVENT_IDEMPOTENCY_FAILED'; end if;
  select count(*) into audit_count from bros_affiliate.affiliate_audit_events;
  if audit_count <> 10 then raise exception 'AUDIT_COUNT_MISMATCH:%',audit_count; end if;
end $$;

select 'G9D_ROUND_TRIP_PASS' as result,
       (select affiliate_code from bros_affiliate.affiliates where id='50000000-0000-0000-0000-000000000001') as affiliate_code,
       (select current_status from bros_affiliate.affiliate_commissions where id='c0000000-0000-0000-0000-000000000001') as commission_status,
       (select amount from bros_affiliate.affiliate_payout_items where id='f1000000-0000-0000-0000-000000000001') as payout_ready,
       (select count(*) from public.revenue_events) as durable_revenue_events,
       (select count(*) from bros_affiliate.affiliate_audit_events) as durable_audit_events;
