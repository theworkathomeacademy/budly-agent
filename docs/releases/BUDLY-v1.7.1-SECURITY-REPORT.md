# BUDLY v1.7.1 SECURITY REPORT

## Corrected critical boundary

Protected conversation-state, relationship, and journey handlers now accept customer identity only from a successfully verified server-side session. Authentication/session errors are returned unchanged. Mutation additionally requires the existing customer CSRF control. No customer ID is accepted from request parameters and no default identity exists.

## Tests

Executable PHP tests cover missing, invalid, expired, and unverified session results; mutation CSRF; no customer-1 fallback; customer-keyed persistence; administrator authorization; and Bootstrap loading. The inherited Secure Memory, consent, replay, commerce, and secret-scanning tests remain mandatory.

## Residual deployment control

The prior production Bootstrap byte hash differs from the Git source byte hash. Exact source-to-package-to-production verification remains mandatory during separately authorized deployment. The previous deployment Application Password must not be reused.
