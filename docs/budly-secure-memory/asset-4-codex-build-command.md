CODEX REMOTE BUILD COMMAND
Budly Secure Returning-Customer Memory System
Asset 4 | Version 1.0
You are Codex operating as the implementation engineer for the Budly Secure Returning-Customer Memory System.
Your assignment is to build the production-ready Version 1 system defined by the approved architecture, security, and customer-experience specifications.
You must implement the system faithfully. Do not redesign the product, expand the scope, substitute a different authentication model, or add unrelated features.

1. Authoritative Source Documents
The following approved assets are the source of truth:
	1. Asset 1: Budly Secure Memory Architecture Specification
		○ Chapter 1: Executive Overview
		○ Chapter 2: System Architecture & Component Design
		○ Chapter 3: Authentication, Verification & Session Management
		○ Chapter 4: Memory Model, Consent Model & Data Structures
		○ Chapter 5: REST API Specification
		○ Chapter 6: Database Schema & Storage Rules
		○ Chapter 7: Security Controls
		○ Chapter 8: Administration, Monitoring & Operational Procedures
		○ Chapter 9: Testing & Acceptance Criteria
	2. Asset 2: Threat Model & Abuse Cases
	3. Asset 3: Customer Experience & Screen Copy
Where implementation details are ambiguous, choose the safest and simplest approach that remains consistent with these approved specifications.
Do not silently change an approved requirement. Record any unavoidable deviation in the final implementation report.

2. Primary Objective
Build a secure, passwordless returning-customer memory system for Budly that allows a customer to:
	1. Identify themselves with an email address.
	2. Receive a one-time verification code by email.
	3. Verify control of that email address.
	4. Establish a short-lived secure session.
	5. Review customer-visible remembered information.
	6. Explicitly approve or decline the use of that memory.
	7. Start fresh without using remembered information.
	8. Review and update consent settings.
	9. Update permitted customer-visible profile fields.
	10. Delete remembered information.
	11. Log out and invalidate the active session.
The system must also provide administrators with controlled operational capabilities for:
	• Health monitoring
	• SMTP testing
	• Audit review
	• Session revocation
	• Cleanup monitoring
	• Configuration visibility
	• Operational diagnostics

3. Non-Negotiable Scope Boundaries
Version 1 must use:
	• Passwordless email verification
	• Six-digit one-time codes
	• Secure server-side sessions
	• Explicit memory consent
	• Explicit memory-use consent
	• Independent marketing consent
	• REST API versioning
	• WordPress-compatible administration
	• Database-backed identity, memory, consent, session, verification, and audit records
	• Customer-visible memory review
	• Customer-controlled memory deletion
	• Immutable or append-only audit behavior
Version 1 must not add:
	• Password authentication
	• WooCommerce account authentication as a dependency
	• Social login
	• SMS verification
	• Automatic marketing enrollment
	• Behavioral advertising profiles
	• Device fingerprinting
	• Biometric identification
	• Unapproved AI-generated customer facts
	• Cross-customer memory sharing
	• Bulk customer data export
	• Unrelated CRM features
	• Affiliate-system functionality
	• Sales-agent functionality
	• Academy-agent functionality
	• Wholesale functionality
	• Mobile application functionality
	• Passkeys or MFA unless implemented only as clearly disabled future extension points
Do not add new product requirements.

4. Required Architectural Components
Implement the following logical services with clear boundaries:
	1. Verification Service
		○ Accept verification requests
		○ Normalize email addresses
		○ Generate secure request identifiers
		○ Generate cryptographically secure six-digit codes
		○ Hash codes before persistence
		○ Enforce expiration
		○ Enforce attempt limits
		○ Enforce replay protection
		○ Enforce rate limits
		○ Trigger email delivery
		○ Produce neutral public responses
	2. Session Management Service
		○ Generate high-entropy session tokens
		○ Store only token hashes
		○ Create sessions after successful verification
		○ Enforce idle expiration
		○ Enforce absolute expiration
		○ Revoke sessions on logout
		○ Support administrator revocation
		○ Support revocation of all sessions for one customer
		○ Prevent expired or revoked sessions from regaining validity
	3. Memory Service
		○ Retrieve customer-visible memory
		○ Filter restricted and internal fields
		○ Generate memory preview responses
		○ Respect consent before storage or use
		○ Support Start Fresh behavior
		○ Support customer memory deletion
		○ Prevent cross-customer access
		○ Resolve customer ownership only from the verified session
	4. Consent Service
		○ Store memory-storage consent
		○ Store memory-use consent
		○ Store marketing consent independently
		○ Preserve consent history
		○ Record consent version and timestamp
		○ Apply consent changes immediately
		○ Fail closed when consent cannot be verified
	5. Audit Service
		○ Record security-sensitive and administrative events
		○ Prevent normal modification of historical records
		○ Exclude plaintext secrets and raw session tokens
		○ Record actor, event type, timestamp, result, and safe metadata
		○ Support filtered administrator review
	6. Administration Service
		○ Provide health status
		○ Provide safe operational metrics
		○ Support session revocation
		○ Support SMTP testing
		○ Support audit inspection
		○ Enforce WordPress administrator authentication
		○ Enforce capability checks
		○ Enforce CSRF or nonce validation
		○ Log every administrative action
	7. Cleanup Service
		○ Remove expired verification artifacts
		○ Remove expired sessions after the approved retention window
		○ Remove obsolete temporary records
		○ Never remove active consent or customer memory without an authorized deletion action
		○ Record cleanup summaries
		○ Expose last-run status to health monitoring
Logical separation is mandatory even if multiple services share the same deployable plugin or application package.

5. Required Customer States
Implement and enforce the following customer state model:
	• Anonymous
	• Verification Requested
	• Verified
	• Active Memory Session
	• Session Expired
	• Session Revoked
	• Memory Use Approved
	• Start Fresh Selected
	• Memory Deleted
Invalid transitions must be rejected.
Examples:
	• Anonymous users cannot retrieve memory.
	• Verification Requested users cannot retrieve memory.
	• Verified customers must still approve memory use before remembered information is injected into a Budly conversation.
	• Start Fresh must suppress memory use for the current conversation without automatically deleting saved memory.
	• Deleted memory must not remain retrievable through normal application interfaces.

6. Authentication Requirements
6.1 Verification Requests
Implement:
	• Server-side email normalization
	• Neutral response wording regardless of whether a customer exists
	• Cryptographically secure six-digit code generation
	• Cryptographically secure request ID generation
	• Code hashing before storage
	• Ten-minute expiration
	• Maximum five verification attempts per request
	• Single-use codes
	• Atomic successful-consumption behavior
	• Per-email rate limiting
	• Per-IP rate limiting
	• Resend controls
	• Audit events for success, failure, lockout, expiration, and delivery failure
Recommended initial rate limits:
	• Three verification requests per normalized email per hour
	• Ten verification requests per IP address per hour
	• Five code attempts per verification request
Store configurable values rather than scattering constants throughout the codebase.
6.2 Verification Responses
Do not reveal whether:
	• The customer exists
	• Memory exists
	• Consent exists
	• The email has previously interacted with Budly
Use the approved neutral response:
“If this address is eligible, we’ve sent a verification code.”
6.3 Email Delivery
Implement an email-delivery abstraction.
Requirements:
	• No SMTP credentials in source control
	• Safe handling of delivery errors
	• Delivery failures recorded without exposing secrets
	• Administrator test-email function
	• Replaceable transport implementation
	• Plain-language verification email
	• Code expiration included in the email
	• No marketing language
	• No customer memory displayed in the email

7. Session Requirements
Create a secure session only after successful verification.
Required defaults:
	• Idle expiration: 30 minutes
	• Absolute expiration: 2 hours
	• Secure, high-entropy token
	• Token stored only as a hash
	• Secure cookie
	• HttpOnly cookie
	• SameSite=Lax or stricter where compatible
	• HTTPS-only transmission
	• Session rotation when appropriate
	• Server-side validation on every protected request
	• Logout revocation
	• Administrative revocation
	• Revocation of all customer sessions following memory deletion
Do not encode customer information into the session token.
Do not trust a customer ID supplied by the client.

8. Consent Requirements
Implement three independent consent categories:
	1. Memory Storage
	2. Memory Use
	3. Marketing
Rules:
	• Marketing consent must never be inferred from either memory consent type.
	• Memory must not be stored without valid memory-storage consent.
	• Memory must not be used without valid memory-use consent.
	• Consent withdrawal must affect future behavior immediately.
	• Consent changes must create immutable history records.
	• Current consent must remain easy to retrieve.
	• Failure to retrieve or validate consent must deny memory access.
	• Consent copy and version must be recordable.
	• Consent timestamp and source must be stored.

9. Memory Requirements
Implement structured memory rather than unrestricted raw transcripts.
Supported Version 1 categories:
	• Identity
	• Preferences
	• Conversation summary
	• Operational metadata
	• Consent references
Memory classifications:
	• Public
	• Customer Visible
	• Internal
	• Restricted
Customer APIs may return only approved Customer Visible fields.
Do not expose:
	• Raw security metadata
	• Verification records
	• Session token hashes
	• Internal abuse signals
	• Restricted administrator notes
	• Database identifiers not required by the interface
	• Infrastructure metadata
	• Raw prompts or hidden system instructions
The preview response must be assembled through an explicit allowlist.

10. Required Data Model
Implement database migrations for the following tables or equivalent approved names:
	• budly_customers
	• budly_preferences
	• budly_conversation_memory
	• budly_consent
	• budly_consent_history
	• budly_verification_requests
	• budly_sessions
	• budly_audit
	• budly_schema_migrations
Use the exact table prefix strategy appropriate to the WordPress environment while preserving the logical names.
Required database practices:
	• UTC timestamps
	• Parameterized queries
	• Unique immutable primary keys
	• Appropriate foreign keys where supported
	• Explicit indexes
	• No plaintext verification codes
	• No plaintext session tokens
	• Schema versioning
	• Repeatable migrations
	• Safe failure on partial migration
	• Documented rollback or recovery strategy
	• JSON only where flexible structured data is justified
	• No arbitrary serialized objects that couple storage to runtime classes

11. Required REST API
Implement Version 1 endpoints equivalent to:
Public
	• POST /auth/request-code
	• POST /auth/verify
Verified Customer
	• GET /auth/session
	• POST /auth/logout
	• GET /memory/preview
	• POST /memory/use
	• POST /memory/start-fresh
	• GET /profile
	• PATCH /profile
	• GET /consent
	• PATCH /consent
	• DELETE /memory
Administrator
	• GET /admin/health
	• POST /admin/revoke-session
	• POST /admin/revoke-all
	• GET /admin/audit
	• POST /admin/test-email
Use a versioned namespace such as:
/wp-json/budly-memory/v1/
All responses must use a consistent envelope.
Recommended success shape:
{
  "success": true,
  "data": {},
  "meta": {}
}
Recommended error shape:
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Customer-safe message"
  }
}
Define and use stable machine-readable error codes.
Do not leak stack traces, SQL messages, raw exceptions, secrets, or internal file paths through API responses.

12. Required Customer Interface
Build the customer flow defined in Asset 3.
Required screens or interface states:
	1. Welcome Back
	2. Verify Your Email
	3. Check Your Inbox
	4. Verification Failure States
	5. Verification Successful
	6. Memory Preview
	7. Start Fresh
	8. Memory Enabled
	9. Privacy Settings
	10. Delete Remembered Information
	11. Memory Deleted
	12. Session Expired
	13. Empty Memory State
	14. Loading States
	15. Recoverable Error States
Use the approved production copy from Asset 3 unless small grammatical adjustments are required for implementation.
Do not rewrite the tone into aggressive sales language.
The interface must remain:
	• Mobile responsive
	• Keyboard navigable
	• Screen-reader compatible
	• Clear without technical knowledge
	• Calm during errors
	• Explicit about customer control

13. Administration Interface
Build a WordPress-compatible administration interface with capability-based access.
Required sections:
System Status
	• Overall health
	• API status
	• Database connectivity
	• SMTP status
	• Cleanup status
	• Schema version
Verification Activity
	• Requests
	• Successful verifications
	• Failed attempts
	• Locked requests
	• Delivery failures
Session Activity
	• Active sessions
	• Recently expired sessions
	• Revoked sessions
	• Individual revocation control
	• Revoke-all-for-customer control
Never display raw session tokens.
Consent and Memory Metrics
Aggregate operational counts only.
Do not create a casual customer-browsing interface.
Audit Review
Support safe filters such as:
	• Date range
	• Event type
	• Severity
	• Actor type
	• Result
Operations
	• Test email
	• Trigger or inspect cleanup where permitted
	• View last successful cleanup
	• View current non-secret configuration
	• View migration status
All administrator state-changing actions require:
	• Authentication
	• Capability checks
	• CSRF or WordPress nonce validation
	• Confirmation where destructive
	• Audit logging

14. Security Controls
Implement the controls required by Asset 1 and Asset 2.
Mandatory controls include:
	• HTTPS enforcement expectations
	• Secure cookies
	• Server-side authorization
	• Server-side input validation
	• Context-aware output escaping
	• Prepared database statements
	• CSRF protection
	• Rate limiting
	• Attempt limits
	• Neutral enumeration-resistant responses
	• Token hashing
	• One-time code hashing
	• Replay protection
	• Session expiration
	• Session revocation
	• Fail-closed consent checks
	• Least-privilege administrator capabilities
	• Append-only audit behavior
	• Secret separation
	• Safe logging
	• Payload-size limits
	• Content-type validation
	• Consistent error handling
Explicitly defend against:
	• Email enumeration
	• Verification-code guessing
	• Verification replay
	• Session fixation
	• Session hijacking
	• Cross-customer memory access
	• SQL injection
	• XSS
	• CSRF
	• Brute-force verification requests
	• Resource exhaustion
	• Administrative abuse
	• Unauthorized memory deletion
	• Consent bypass
	• Backup exposure
	• Insider data harvesting

15. Logging Rules
Security and operational logging must be separate in purpose.
Security Audit Events
Record events such as:
	• Verification requested
	• Verification failed
	• Verification locked
	• Verification succeeded
	• Session created
	• Session expired
	• Session revoked
	• Consent changed
	• Memory preview accessed
	• Memory use approved
	• Start Fresh selected
	• Profile updated
	• Memory deleted
	• Administrator action
	• Rate limit triggered
Operational Logs
Record events such as:
	• Service startup
	• Migration execution
	• Cleanup execution
	• Health check failure
	• SMTP transport failure
	• Backup-status integration result, if available
Never log:
	• Plaintext verification codes
	• Raw session tokens
	• SMTP passwords
	• API secrets
	• Encryption keys
	• Full sensitive request bodies
	• Unnecessary customer memory
Mask or hash identifiers where practical.

16. Cleanup and Retention
Implement scheduled cleanup using the WordPress scheduling mechanism or another approved scheduler.
Cleanup must:
	• Remove expired verification requests when eligible
	• Remove expired session records after the configured retention period
	• Remove obsolete temporary authentication records
	• Preserve current consent
	• Preserve required consent history
	• Preserve audit records within policy
	• Preserve customer memory unless an authorized deletion occurs
	• Generate a run summary
	• Report last successful execution
	• Fail safely without corrupting records
Retention values must be configurable.
Do not invent legal retention requirements. Document configured defaults clearly as operational policy values.

17. Testing Requirements
Create automated tests covering all critical behavior.
Unit Tests
Required for:
	• Code generation
	• Code hashing and comparison
	• Verification expiration
	• Attempt counters
	• Rate-limit calculations
	• Session token generation
	• Session expiration
	• Session revocation
	• Consent decisions
	• Memory allowlisting
	• Audit event construction
	• Cleanup eligibility
	• Input validation
Integration Tests
Required for:
	• Verification to session creation
	• Session to memory retrieval
	• Session to consent validation
	• Consent withdrawal to immediate memory denial
	• Memory deletion to session revocation
	• Administrator revocation to immediate invalidation
	• Cleanup execution
	• Migration execution
API Tests
Test each endpoint for:
	• Valid success
	• Invalid input
	• Missing authentication
	• Expired session
	• Revoked session
	• Incorrect capability
	• CSRF failure
	• Rate limiting
	• Stable response shape
	• Correct status code
	• Safe error message
Security Tests
Include tests for:
	• Email enumeration resistance
	• Code replay rejection
	• Brute-force lockout
	• Cross-customer identifier manipulation
	• SQL injection payload handling
	• XSS payload handling
	• CSRF rejection
	• Session fixation resistance
	• Revoked session rejection
	• Consent bypass attempts
	• Oversized request rejection
	• Malformed JSON handling
	• Restricted field exclusion
End-to-End Tests
Validate:
	1. Returning customer verification
	2. Memory preview
	3. Memory-use approval
	4. Start Fresh
	5. Consent update
	6. Profile update
	7. Memory deletion
	8. Logout
	9. Session expiration
	10. Administrator session revocation
All critical and high-risk security tests must pass before production readiness is declared.

18. Accessibility Requirements
Customer-facing implementation must support:
	• Keyboard-only navigation
	• Logical focus order
	• Visible focus indicators
	• Proper labels
	• Accessible error announcements
	• Semantic headings
	• Adequate contrast
	• Mobile touch targets
	• Reduced-motion preferences
	• No critical information communicated by color alone
Use automated accessibility checks plus manual keyboard review.

19. Performance and Reliability Expectations
Do not overengineer for speculative scale, but avoid obvious bottlenecks.
Implement:
	• Indexed session lookups
	• Indexed verification lookups
	• Indexed customer identity lookups
	• Paginated audit queries
	• Bounded administrator query ranges
	• Efficient cleanup batches
	• Request timeouts where relevant
	• Safe handling of SMTP delays
	• Graceful memory-service failure
When memory is unavailable, the customer must still be able to start a new conversation.
When session or consent validation is unavailable, protected memory access must be denied.

20. Recommended Repository Structure
Inspect the existing repository before creating files.
Preserve existing project conventions where they are clear and safe.
If no suitable structure exists, use a modular structure equivalent to:
budly-secure-memory/
├── budly-secure-memory.php
├── README.md
├── composer.json
├── package.json
├── phpunit.xml
├── assets/
│   ├── css/
│   └── js/
├── includes/
│   ├── Bootstrap/
│   ├── Admin/
│   ├── Api/
│   ├── Auth/
│   ├── Consent/
│   ├── Database/
│   ├── Memory/
│   ├── Sessions/
│   ├── Verification/
│   ├── Audit/
│   ├── Cleanup/
│   ├── Email/
│   ├── Security/
│   └── Support/
├── migrations/
├── templates/
│   ├── customer/
│   └── admin/
├── tests/
│   ├── Unit/
│   ├── Integration/
│   ├── Api/
│   ├── Security/
│   └── EndToEnd/
├── docs/
│   ├── architecture-map.md
│   ├── installation.md
│   ├── configuration.md
│   ├── administration.md
│   ├── operations.md
│   ├── security.md
│   ├── testing.md
│   └── implementation-report.md
└── uninstall.php
Do not force this structure if the repository already has an established modular architecture that satisfies the same separation requirements.

21. Engineering Standards
Follow these standards:
	• Use readable, maintainable code.
	• Prefer small focused classes and functions.
	• Avoid hidden global state.
	• Use dependency injection where practical.
	• Centralize configuration.
	• Centralize error codes.
	• Centralize authorization checks.
	• Centralize input validation helpers where appropriate.
	• Do not duplicate security logic across controllers.
	• Add comments for security-sensitive decisions, not obvious syntax.
	• Use strict comparisons.
	• Handle null and error states explicitly.
	• Avoid suppressed errors.
	• Avoid direct database access from templates.
	• Keep customer presentation separate from persistence logic.
	• Keep administrator permissions separate from customer session logic.
	• Sanitize input and escape output according to context.
	• Use WordPress coding standards where applicable.
	• Do not disable security tooling to make tests pass.

22. Implementation Sequence
Execute the build in the following order.
Phase 0: Repository Reconnaissance
Before changing code:
	1. Inspect the repository.
	2. Identify the platform and existing architecture.
	3. Identify WordPress and WooCommerce integration points.
	4. Identify existing authentication or customer-memory code.
	5. Identify existing coding and testing conventions.
	6. Identify environment configuration patterns.
	7. Identify current CI checks.
	8. Identify conflicts with the approved specification.
Produce a short implementation map before coding.
Do not delete or rewrite unrelated working systems.
Phase 1: Foundation
Build:
	• Plugin or application bootstrap
	• Configuration management
	• Error-code system
	• Database migration framework
	• Core data-access layer
	• Shared validation
	• Shared response envelope
	• Audit-event foundation
Phase 2: Verification
Build:
	• Email normalization
	• Verification request persistence
	• Secure code generation
	• Code hashing
	• Attempt enforcement
	• Expiration
	• Replay protection
	• Rate limiting
	• Email transport abstraction
	• Request-code endpoint
	• Verify endpoint
	• Tests
Phase 3: Sessions
Build:
	• Secure token creation
	• Hash persistence
	• Cookie handling
	• Validation middleware
	• Idle expiration
	• Absolute expiration
	• Logout
	• Revocation
	• Tests
Phase 4: Consent
Build:
	• Current consent persistence
	• Consent history
	• Consent retrieval
	• Consent updates
	• Immediate enforcement
	• Tests
Phase 5: Memory and Profile
Build:
	• Customer profile access
	• Preference access
	• Conversation summary access
	• Customer-visible allowlist
	• Memory preview
	• Memory-use approval
	• Start Fresh state
	• Profile update
	• Memory deletion
	• Tests
Phase 6: Customer Experience
Build:
	• Returning-customer entry
	• Verification flow
	• Memory preview
	• Start Fresh flow
	• Privacy settings
	• Memory deletion flow
	• Loading, empty, and error states
	• Accessibility behavior
	• Responsive styling
Phase 7: Administration
Build:
	• Health dashboard
	• Verification metrics
	• Session metrics
	• Session revocation
	• Audit review
	• Test email
	• Cleanup status
	• Capability checks
	• Nonce or CSRF protection
	• Tests
Phase 8: Cleanup and Operations
Build:
	• Scheduled cleanup
	• Cleanup logging
	• Health checks
	• Configuration inspection
	• Operational documentation
	• Recovery procedures
Phase 9: Security Hardening
Perform:
	• Authorization review
	• Enumeration review
	• CSRF review
	• XSS review
	• SQL injection review
	• Session review
	• Secret-management review
	• Logging review
	• Payload-limit review
	• Error-leakage review
	• Threat-model traceability review
Phase 10: Acceptance and Documentation
Complete:
	• Full automated test suite
	• Manual end-to-end test
	• Accessibility review
	• Migration test
	• Cleanup test
	• Restore guidance
	• Installation guide
	• Configuration guide
	• Administrator guide
	• Security guide
	• Implementation report
	• Known-limitations list
	• Final acceptance checklist

23. Required Milestone Gates
Do not declare a phase complete until its gate passes.
Gate A: Foundation
	• Migrations run cleanly.
	• Data-access layer uses prepared statements.
	• Error responses follow the standard envelope.
	• Audit service can record events.
Gate B: Authentication
	• Verification codes are never stored in plaintext.
	• Enumeration tests pass.
	• Replay tests pass.
	• Attempt limits pass.
	• Rate limits pass.
	• Successful verification creates a valid session.
Gate C: Authorization
	• Protected endpoints reject anonymous users.
	• Expired sessions fail.
	• Revoked sessions fail.
	• Customer ownership comes exclusively from the session.
	• Cross-customer access tests pass.
Gate D: Consent and Memory
	• Memory storage requires consent.
	• Memory use requires consent.
	• Marketing remains independent.
	• Memory preview exposes allowlisted fields only.
	• Start Fresh suppresses memory use.
	• Deletion removes customer memory and revokes sessions.
Gate E: Administration
	• Capability checks pass.
	• CSRF or nonce checks pass.
	• Raw tokens are never displayed.
	• Administrative actions are audited.
	• Health checks report safe status.
Gate F: Production Readiness
	• All critical tests pass.
	• No known critical or high-severity security defects remain.
	• Documentation matches the implementation.
	• Acceptance checklist is complete.
	• Any deviations are documented.

24. Required Deliverables
When implementation is complete, provide:
	1. Production implementation
	2. Database migrations
	3. Automated tests
	4. Customer-facing interface
	5. Administrator interface
	6. Cleanup jobs
	7. Health checks
	8. Installation documentation
	9. Configuration documentation
	10. Administrator guide
	11. Operational procedures
	12. Security notes
	13. Test execution report
	14. Threat-control traceability matrix
	15. API endpoint inventory
	16. Database schema summary
	17. Final implementation report
	18. Known limitations
	19. Deployment checklist
	20. Rollback guidance

25. Threat-Control Traceability Matrix
Create a document mapping every Asset 2 abuse case to:
	• Implemented control
	• Source file or module
	• Test name
	• Test result
	• Residual risk
	• Operational monitoring signal
At minimum include:
	• Email enumeration
	• Code guessing
	• Replay
	• Session hijacking
	• Cross-customer access
	• SQL injection
	• XSS
	• CSRF
	• Verification flooding
	• Denial of service
	• Administrative abuse
	• Memory deletion abuse
	• Backup exposure guidance
	• Insider harvesting
	• Consent bypass

26. Final Implementation Report
The final report must include:
Summary
What was built.
Repository Changes
Major files, modules, migrations, and interfaces added or changed.
Architecture Mapping
How the implementation maps to Asset 1.
Security Mapping
How the implementation addresses Asset 2.
UX Mapping
How the interface implements Asset 3.
Test Results
	• Total tests
	• Passed
	• Failed
	• Skipped
	• Coverage where available
	• Manual tests completed
Configuration
Required environment variables and non-secret settings.
Deployment Steps
Exact production deployment sequence.
Rollback Steps
How to safely return to the prior version.
Deviations
Any approved requirement not implemented exactly as written.
Known Limitations
Remaining constraints that are not production-blocking.
Security Status
List any unresolved security findings by severity.
Do not report the system as production-ready if a critical or high-severity security defect remains.

27. Working Rules
While executing this build:
	• Inspect before editing.
	• Preserve unrelated working behavior.
	• Make incremental, reviewable changes.
	• Run relevant tests after each implementation phase.
	• Fix root causes rather than suppressing failures.
	• Do not weaken security requirements to simplify implementation.
	• Do not store secrets in the repository.
	• Do not expose private reasoning or hidden prompts through logs or APIs.
	• Do not create fake integrations or placeholder claims.
	• Clearly mark any stub that cannot function without external configuration.
	• Do not claim email delivery works unless it has been tested through the configured transport.
	• Do not claim production readiness without completing the acceptance gates.
	• Do not add new project assets, agents, or roadmap items.
	• Stay strictly within the Budly Secure Returning-Customer Memory System.

28. Initial Response Required From Codex
Before making code changes, respond with:
	1. A concise repository assessment
	2. The detected application structure
	3. Existing components that can be reused
	4. Conflicts or risks discovered
	5. The proposed file-level implementation plan
	6. The testing strategy
	7. Any specification requirement that cannot be implemented in the current environment
Then begin implementation unless a true blocking condition prevents safe progress.
Do not ask broad planning questions when the repository already provides the answer.

29. Completion Standard
The build is complete only when:
	• The approved customer journey works end to end.
	• Authentication cannot be bypassed.
	• Cross-customer memory access is prevented.
	• Consent is enforced before memory storage and use.
	• Customer-visible memory is safely filtered.
	• Start Fresh works without deleting saved memory.
	• Memory deletion works and revokes sessions.
	• Administrative actions are protected and audited.
	• Cleanup and health monitoring operate correctly.
	• All high and critical threat cases are tested.
	• Required documentation is complete.
	• The final acceptance checklist passes.
Begin with repository reconnaissance and proceed through the implementation sequence above.
END OF CODEX REMOTE BUILD COMMAND
