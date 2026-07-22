
Budly Secure Memory System
Asset 2
Threat Model & Abuse Cases
Version 1.0

1. Purpose
This document identifies threats against the Budly Secure Memory System and defines the security controls required to mitigate them.
Its objectives are to:
	• Protect customer privacy.
	• Prevent unauthorized memory access.
	• Preserve customer trust.
	• Reduce operational risk.
	• Provide implementation guidance for Codex.
The threat model assumes that the system is publicly accessible over the Internet and may be targeted by both automated and human attackers.

2. Security Objectives
The Secure Memory System must ensure:
	1. Only verified customers may access remembered information.
	2. Consent is always respected.
	3. Customer memory cannot be retrieved through guessing or enumeration.
	4. Administrative functions remain protected.
	5. Security-sensitive actions are observable.
	6. Compromise of one subsystem does not compromise the entire platform.

3. Protected Assets
The following assets require protection.
Critical
	• Customer identity
	• Verification system
	• Session tokens
	• Consent records
	• Customer memory
	• Administrative privileges
	• Audit records

High Value
	• Customer preferences
	• Conversation summaries
	• Operational status
	• Support references

Infrastructure
	• SMTP credentials
	• Database credentials
	• API secrets
	• Encryption keys
	• Configuration

4. Trust Boundaries
The architecture contains multiple trust boundaries.
Internet
      │
      ▼
Public REST API
      │
      ▼
Verification Service
      │
      ▼
Session Service
      │
      ▼
Memory Service
      │
      ▼
Database
      │
      ▼
Administrative Dashboard
Every transition across these boundaries requires authentication, authorization, validation, or all three.

5. Threat Actors
The threat model considers the following actors.
5.1 Curious Visitor
Capabilities:
	• Public website access
	• No authentication
Motivation:
	• Explore functionality
	• Guess customer information
Risk:
Low

5.2 Automated Bot
Capabilities:
	• High request volume
	• Distributed IPs
	• Automated retries
Motivation:
	• Enumeration
	• Credential guessing
	• Resource exhaustion
Risk:
High

5.3 Malicious Customer
Capabilities:
	• Own verified session
Motivation:
	• Access another customer’s memory
	• Escalate privileges
	• Abuse APIs
Risk:
High

5.4 Malicious Administrator
Capabilities:
	• Administrative access
Motivation:
	• Abuse privileges
	• Unauthorized data access
Risk:
Critical
This is why administrator actions require immutable audit logging.

5.5 External Attacker
Capabilities:
	• Internet access
	• Knowledge of web vulnerabilities
Motivation:
	• Data theft
	• Financial gain
	• Reputation damage
Risk:
Critical

5.6 Insider
Capabilities:
	• Infrastructure access
Motivation:
	• Data extraction
	• Misuse of privileged access
Risk:
Critical

6. Threat Categories
Threats are grouped using established security concepts.
	• Identity attacks
	• Authentication attacks
	• Authorization attacks
	• Data exposure
	• Availability attacks
	• Administrative abuse
	• Infrastructure compromise
	• Privacy violations
	• Operational failures

7. Abuse Cases
Each abuse case includes:
	• Description
	• Risk
	• Required mitigations
	• Acceptance criteria

Abuse Case 1
Email Enumeration
Scenario
An attacker submits thousands of email addresses to determine which customers exist.
Impact
	• Customer privacy loss
	• Targeted phishing
	• Reputation damage
Risk
High
Required Controls
	• Neutral responses
	• Rate limiting
	• Audit logging
	• Monitoring
Acceptance Criteria
An attacker cannot determine whether an email address exists based on public responses.

Abuse Case 2
Verification Code Guessing
Scenario
Attacker repeatedly submits six-digit codes.
Impact
Unauthorized memory access.
Risk
High
Controls
	• Five-attempt limit
	• Request lock
	• Short expiration
	• Rate limiting
	• Audit events
Acceptance Criteria
Repeated guessing never authenticates a customer without possession of the correct code.

Abuse Case 3
Replay Attack
Scenario
Attacker intercepts or reuses a previously successful verification code.
Controls
	• Single-use verification codes
	• Atomic state transition
	• Immediate invalidation
Acceptance Criteria
Previously used verification codes are always rejected.

Abuse Case 4
Session Hijacking
Scenario
Attacker attempts to use another customer’s session.
Controls
	• Secure cookies
	• HTTPOnly
	• Token hashing
	• Idle expiration
	• Absolute expiration
Acceptance Criteria
Expired, revoked, or stolen session tokens cannot be reused successfully.

Abuse Case 5
Cross-Customer Memory Access
Scenario
Authenticated customer manipulates identifiers to retrieve another customer’s memory.
Controls
	• Server-side authorization
	• Customer key validation
	• No client-supplied ownership
Acceptance Criteria
Every memory request is resolved exclusively from the authenticated session, never from client-provided identifiers.

Abuse Case 6
SQL Injection
Scenario
Attacker submits crafted input intended to modify database queries.
Controls
	• Parameterized queries
	• Input validation
	• ORM or prepared statements
	• Least-privilege database account
Acceptance Criteria
User input never alters SQL structure.

Abuse Case 7
Cross-Site Scripting (XSS)
Scenario
Attacker attempts to inject executable content through customer-controlled fields.
Controls
	• Context-aware output escaping
	• Input validation
	• Content Security Policy where appropriate
Acceptance Criteria
Customer-supplied data is rendered as data, not executable code.

Abuse Case 8
Cross-Site Request Forgery (CSRF)
Scenario
Authenticated customer is tricked into unknowingly changing consent or deleting memory.
Controls
	• CSRF protection
	• Nonce validation
	• SameSite cookies
Acceptance Criteria
State-changing requests require valid anti-CSRF protections.

Abuse Case 9
Brute Force Verification Requests
Scenario
Attacker floods verification endpoint.
Controls
	• Per-IP limits
	• Per-email limits
	• Monitoring
	• Temporary lockouts
Acceptance Criteria
The system remains responsive while abusive traffic is throttled.

Abuse Case 10
Denial of Service
Scenario
Large request volume overwhelms the system.
Controls
	• Rate limiting
	• Reverse proxy protections
	• Request timeouts
	• Resource monitoring
Acceptance Criteria
Graceful degradation occurs before service failure.

Abuse Case 11
Administrative Abuse
Scenario
Administrator revokes customer sessions without authorization.
Controls
	• Immutable audit log
	• Role-based permissions
	• Operational review
Acceptance Criteria
Every administrative action is attributable to a specific administrator and time.

Abuse Case 12
Memory Deletion Abuse
Scenario
Attacker deletes another customer’s memory.
Controls
	• Verified session
	• Authorization checks
	• Optional confirmation
	• Audit logging
Acceptance Criteria
Only the verified customer (or authorized administrator under documented procedures) can initiate deletion.

Abuse Case 13
Backup Exposure
Scenario
Backup files are stolen.
Controls
	• Encryption at rest
	• Access controls
	• Secure key management
Acceptance Criteria
Backups do not expose usable customer data without the appropriate encryption keys.

Abuse Case 14
Insider Data Harvesting
Scenario
Privileged individual exports customer data outside normal workflows.
Controls
	• Least privilege
	• Export restrictions
	• Audit logging
	• Operational review
Acceptance Criteria
Bulk access to customer data is controlled and detectable.

Abuse Case 15
Consent Bypass
Scenario
Application bug returns remembered information despite withdrawn consent.
Controls
	• Consent validation before every retrieval
	• Automated regression tests
	• Fail-closed behavior
Acceptance Criteria
Memory is never returned when consent validation fails.

8. Risk Matrix
Threat	Likelihood	Impact	Priority
Email enumeration	High	Medium	High
Code guessing	High	High	Critical
Replay attack	Medium	High	High
Session hijacking	Medium	Critical	Critical
SQL injection	Medium	Critical	Critical
XSS	Medium	High	High
CSRF	Medium	High	High
Cross-customer access	Low	Critical	Critical
DoS	Medium	High	High
Insider abuse	Low	Critical	Critical
Critical risks should be addressed before production deployment.

9. Security Monitoring
Operational monitoring should include alerts for:
	• Excessive verification failures
	• Repeated rate-limit violations
	• Multiple session revocations
	• Administrative privilege changes
	• Unexpected spikes in memory deletions
	• Repeated authorization failures
	• Failed backup verification
	• Audit logging failures
Monitoring should prioritize actionable events rather than excessive noise.

10. Residual Risk
No Internet-facing system can eliminate all risk.
Residual risks include:
	• Customer email account compromise
	• Infrastructure provider outages
	• Zero-day software vulnerabilities
	• Social engineering attacks
	• Authorized users intentionally sharing their own verification codes
These risks should be documented, monitored, and reassessed periodically.

11. Secure Development Requirements
Every implementation should include:
	• Peer review (or equivalent review of generated code)
	• Automated security testing
	• Dependency vulnerability scanning
	• Static analysis where practical
	• Secure secret management
	• Regular updates to third-party components
Security should remain part of the development lifecycle rather than a final deployment step.

12. Final Acceptance Criteria
Asset 2 is considered complete when:
✓ All identified abuse cases have documented mitigations.
✓ High and critical risks have implementation requirements.
✓ Security controls map back to the architecture in Asset 1.
✓ Monitoring requirements are defined.
✓ Residual risks are documented.
✓ Codex can trace each mitigation to specific implementation tasks.

End of Asset 2

