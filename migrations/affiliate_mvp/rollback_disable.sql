-- Non-destructive rollback for AFF-001 Phase F.
-- Financial/history tables are intentionally preserved.
update bros_affiliate.feature_flags set enabled=false, updated_at=now(), updated_by='rollback_disable'
where flag_name in ('affiliate_referral_enabled','affiliate_attribution_enabled','affiliate_commission_processing_enabled','affiliate_portal_enabled','affiliate_payout_submission_enabled');

