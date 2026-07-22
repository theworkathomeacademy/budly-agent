Budly Identity & Memory API Specification
Asset 5 | Version 1.0

1. Purpose
The Budly Identity & Memory API provides a shared contract for securely identifying returning customers and using approved customer memory across the Budly ecosystem.
This API is intended to support current and future authorized Budly applications, including:
	• Customer-facing Budly conversations
	• Product and sales experiences
	• Affiliate support experiences
	• Educational experiences
	• Customer-support experiences
	• Approved website applications
	• Approved administrative tools
The API centralizes:
	• Customer identity
	• Email verification
	• Session management
	• Consent
	• Customer profiles
	• Preferences
	• Conversation summaries
	• Memory authorization
	• Memory deletion
	• Security auditing
No Budly agent should create a separate identity or memory database when the shared service can satisfy the requirement.

2. Core Platform Rule
The Identity & Memory API is the authoritative source for:
	• Customer identity
	• Verification state
	• Session validity
	• Consent state
	• Customer-visible profile information
	• Shared customer preferences
	• Approved memory summaries
Individual agents may maintain their own operational data, but they must not duplicate or independently redefine shared identity, consent, or customer memory.

3. Design Objectives
The API must provide:
	1. One verified customer identity across approved Budly services.
	2. One centralized consent model.
	3. One secure session-validation system.
	4. Controlled memory sharing between approved agents.
	5. Strict separation between shared and agent-specific memory.
	6. Customer visibility and control.
	7. Clear auditability.
	8. Future compatibility without breaking Version 1 clients.

4. Architectural Position
The API sits between Budly applications and the secure persistence layer.
Customer
   │
   ▼
Approved Budly Interface
   │
   ▼
Budly Identity & Memory API
   │
   ├── Verification Service
   ├── Session Service
   ├── Consent Service
   ├── Identity Service
   ├── Memory Service
   ├── Authorization Service
   └── Audit Service
   │
   ▼
Secure Budly Data Store
Budly applications must not access identity, verification, session, consent, or shared-memory tables directly.

5. Scope
5.1 Included
Version 1 includes:
	• Passwordless email verification
	• Customer session creation
	• Session validation
	• Session revocation
	• Customer identity retrieval
	• Customer profile retrieval
	• Profile updates
	• Consent retrieval and updates
	• Memory previews
	• Memory-use authorization
	• Start Fresh behavior
	• Shared preference retrieval
	• Agent-specific memory retrieval
	• Conversation summary storage
	• Customer memory deletion
	• Administrative health and audit functions

5.2 Excluded
Version 1 does not include:
	• Password authentication
	• Social login
	• SMS verification
	• Passkeys
	• Biometric identification
	• Anonymous cross-device tracking
	• Advertising profiles
	• Automatic marketing enrollment
	• Full raw-chat transcript sharing
	• Unrestricted agent-to-agent data access
	• Public customer search
	• Bulk customer export
	• Agent-controlled identity creation outside approved workflows

6. API Base Path
Recommended WordPress REST namespace:
/wp-json/budly-identity/v1
Example:
https://example.com/wp-json/budly-identity/v1/auth/request-code
All Version 1 endpoints must remain under the /v1 namespace.
Breaking changes require a new API version.

7. Transport Requirements
All requests must use HTTPS.
Minimum requirements:
	• TLS 1.2 or later
	• TLS 1.3 preferred
	• JSON request and response bodies
	• UTF-8 encoding
	• Secure authentication cookies or approved bearer-token transport
	• Explicit content-type validation
Requests sent through insecure HTTP must be rejected or redirected before sensitive data is processed.

8. Request Headers
Recommended standard headers:
Content-Type: application/json
Accept: application/json
X-Budly-Agent-ID: sales-agent
X-Budly-Request-ID: 4f8cbbd7-6cf4-4e37-a05d-0c127ef3f475
X-Budly-Conversation-ID: conv_01JABC123
8.1 X-Budly-Agent-ID
Identifies the approved Budly application making the request.
Examples:
	• core-chat
	• sales-agent
	• affiliate-agent
	• support-agent
	• academy-agent
	• wholesale-agent
	• mobile-app
The value must come from an approved registry.
Clients may not invent agent identifiers dynamically.

8.2 X-Budly-Request-ID
A client-generated unique request identifier.
Used for:
	• Traceability
	• Idempotency support
	• Debugging
	• Audit correlation
The server may generate one when omitted.

8.3 X-Budly-Conversation-ID
Identifies the active customer conversation.
This value is optional for authentication and profile endpoints but required when storing or retrieving conversation-specific memory.
A conversation identifier does not grant access by itself.

9. Standard Response Envelope
9.1 Successful Response
{
  "success": true,
  "data": {},
  "meta": {
    "request_id": "4f8cbbd7-6cf4-4e37-a05d-0c127ef3f475",
    "api_version": "1.0",
    "timestamp": "2026-07-19T15:30:00Z"
  }
}

9.2 Error Response
{
  "success": false,
  "error": {
    "code": "SESSION_EXPIRED",
    "message": "Your verified session has expired.",
    "details": {}
  },
  "meta": {
    "request_id": "4f8cbbd7-6cf4-4e37-a05d-0c127ef3f475",
    "api_version": "1.0",
    "timestamp": "2026-07-19T15:30:00Z"
  }
}
Error details must not expose:
	• Stack traces
	• SQL errors
	• File paths
	• Token values
	• Verification codes
	• Secrets
	• Internal customer identifiers unless explicitly permitted

10. Standard HTTP Status Codes
Status	Meaning
200	Successful request
201	Resource created
202	Request accepted
204	Successful request with no body
400	Invalid request
401	Authentication required or invalid
403	Authenticated but not authorized
404	Resource unavailable
409	State conflict
410	Resource expired or permanently unavailable
422	Validation failed
429	Rate limit exceeded
500	Unexpected server error
503	Required service unavailable

11. Standard Error Codes
Recommended stable error codes include:
INVALID_REQUEST
INVALID_EMAIL
INVALID_CODE
CODE_EXPIRED
CODE_ALREADY_USED
VERIFICATION_LOCKED
RATE_LIMITED
EMAIL_DELIVERY_UNAVAILABLE
AUTHENTICATION_REQUIRED
SESSION_INVALID
SESSION_EXPIRED
SESSION_REVOKED
AGENT_NOT_REGISTERED
AGENT_NOT_AUTHORIZED
CONSENT_REQUIRED
CONSENT_DENIED
MEMORY_USE_NOT_APPROVED
MEMORY_NOT_FOUND
MEMORY_UNAVAILABLE
PROFILE_NOT_FOUND
FIELD_NOT_ALLOWED
CONVERSATION_ID_REQUIRED
CONVERSATION_NOT_AUTHORIZED
RESOURCE_CONFLICT
CSRF_VALIDATION_FAILED
ADMIN_PERMISSION_REQUIRED
SERVICE_UNAVAILABLE
INTERNAL_ERROR
Clients must not depend on customer-facing error wording.
Clients should use the stable machine-readable code.

12. Authentication Levels
The API defines four authentication levels.
Level 0: Public
No verified customer session.
Permitted actions:
	• Request verification code
	• Submit verification code

Level 1: Verified Customer
Customer has successfully verified control of the email address and holds a valid session.
Permitted actions may include:
	• Read session state
	• Read profile
	• Read consent
	• Review memory preview
	• Start Fresh
	• Delete memory
	• Log out

Level 2: Memory Authorized
Customer is verified and has approved memory use for the active context.
Permitted actions may include:
	• Retrieve approved shared memory
	• Retrieve authorized agent-specific memory
	• Store approved conversation summaries
	• Apply customer preferences

Level 3: Administrator or Trusted Service
Requires:
	• Approved administrative authentication or service credential
	• Explicit capability
	• Agent registration
	• Audit logging
Permitted actions depend on assigned scopes.

13. Agent Registration
Every Budly agent using the API must be registered.
An agent registration should contain:
{
  "agent_id": "sales-agent",
  "display_name": "Budly Sales Agent",
  "status": "active",
  "allowed_scopes": [
    "identity:read",
    "profile:read",
    "preferences:read",
    "memory:read:shared",
    "memory:read:agent",
    "memory:write:summary"
  ],
  "allowed_memory_namespaces": [
    "shared",
    "sales"
  ],
  "created_at": "2026-07-19T15:30:00Z",
  "updated_at": "2026-07-19T15:30:00Z"
}
An unregistered, inactive, or unauthorized agent must be denied access.

14. Authorization Scopes
Recommended scopes:
Identity
identity:read
identity:update
Profile
profile:read
profile:update
Preferences
preferences:read
preferences:update
Consent
consent:read
consent:update
Memory
memory:preview
memory:read:shared
memory:read:agent
memory:write:summary
memory:delete:self
Session
session:read
session:revoke:self
session:revoke:admin
Administration
admin:health
admin:audit
admin:agents
admin:sessions
admin:configuration
Possession of a scope does not override customer consent.

15. Identity Model
The shared identity record represents the customer, not an agent-specific account.
Recommended customer identity structure:
{
  "customer_id": "cus_01JABC123",
  "identity_version": 1,
  "status": "active",
  "email_verified": true,
  "preferred_name": "Jordan",
  "created_at": "2026-04-10T14:22:00Z",
  "updated_at": "2026-07-15T18:05:00Z"
}
15.1 Identity Rules
	• customer_id is immutable.
	• Email verification status is server-controlled.
	• Agents may not change verified email ownership.
	• Customer IDs must not be accepted as proof of authorization.
	• The authenticated session determines the customer.
	• Deleted or restricted customers may return reduced data.
	• Internal database keys should not be exposed when a public opaque identifier is available.

16. Profile Model
The profile contains customer-visible information approved for reuse.
Recommended structure:
{
  "preferred_name": "Jordan",
  "experience_level": "beginner",
  "communication_preferences": {
    "detail_level": "moderate",
    "tone": "educational"
  },
  "updated_at": "2026-07-15T18:05:00Z"
}
16.1 Allowed Profile Fields
Version 1 may include:
	• Preferred name
	• Experience level
	• Communication preferences
	• Approved accessibility preferences
	• General educational preferences
The allowlist must be explicit.
Agents may not add arbitrary profile fields without a schema revision.

17. Preference Model
Preferences describe reusable customer choices.
Recommended structure:
{
  "product_interests": [
    "topicals",
    "education"
  ],
  "format_preferences": [
    "step-by-step",
    "plain-language"
  ],
  "shopping_preferences": {
    "fragrance_free": true
  },
  "updated_at": "2026-07-15T18:05:00Z"
}
Preferences must be:
	• Structured
	• Purpose-limited
	• Customer-visible where appropriate
	• Editable or deletable
	• Supported by valid memory-storage consent
Agents must not infer sensitive personal attributes and store them as preferences.

18. Memory Namespaces
Memory is divided into namespaces to prevent unrestricted sharing.
18.1 Shared Namespace
Accessible to approved agents with memory:read:shared.
Examples:
	• Preferred name
	• Communication style
	• General experience level
	• Broad product-format preferences
	• Current consent state
Shared memory should contain only information genuinely useful across multiple Budly services.

18.2 Agent-Specific Namespace
Accessible only to the owning agent and explicitly authorized services.
Examples:
Sales Namespace
	• Product categories previously discussed
	• Shopping-stage summary
	• Approved follow-up context
Affiliate Namespace
	• Onboarding stage
	• Training completion
	• Approved affiliate goals
Support Namespace
	• Open support-topic summary
	• Prior troubleshooting steps
	• Resolution status
Academy Namespace
	• Completed lessons
	• Learning preferences
	• Current curriculum position
Agent-specific memory must not automatically become shared memory.

18.3 Restricted Namespace
Contains security or operational information.
Examples:
	• Abuse indicators
	• Verification metadata
	• Internal risk scores
	• Administrative notes
	• Security-investigation references
Restricted memory is never exposed to normal agents or customers through memory endpoints.

19. Memory Record Model
Recommended structure:
{
  "memory_id": "mem_01JXYZ789",
  "customer_id": "cus_01JABC123",
  "namespace": "sales",
  "memory_type": "conversation_summary",
  "classification": "customer_visible",
  "schema_version": 1,
  "source_agent_id": "sales-agent",
  "summary": {
    "topic": "CBD topical products",
    "customer_goal": "Compare fragrance-free options",
    "resolved_questions": [
      "Difference between butter and balm"
    ],
    "open_questions": [
      "Preferred container size"
    ]
  },
  "consent_reference": "cons_01JDEF456",
  "created_at": "2026-07-15T18:00:00Z",
  "updated_at": "2026-07-15T18:05:00Z",
  "expires_at": null
}

20. Memory Storage Rules
Agents may store memory only when:
	1. The customer is verified.
	2. Memory-storage consent is active.
	3. The agent is registered.
	4. The agent has the required write scope.
	5. The namespace is authorized.
	6. The memory type is supported.
	7. The payload passes schema validation.
	8. The content is appropriate for long-term retention.
	9. The operation is audited.
Agents must not store:
	• Raw verification codes
	• Session tokens
	• Passwords
	• Payment-card information
	• Government identification numbers
	• Medical diagnoses
	• Unverified sensitive personal attributes
	• Hidden system prompts
	• Internal chain-of-thought
	• Entire raw conversations by default
	• Information unrelated to the approved customer purpose

21. Memory Retrieval Rules
Memory may be returned only when:
	1. The session is valid.
	2. The customer identity is resolved from the session.
	3. Memory-use consent is active.
	4. The customer has approved memory use for the current conversation or context.
	5. The requesting agent is registered.
	6. The agent has the correct scope.
	7. The namespace is authorized.
	8. The record classification permits exposure.
	9. The requested purpose matches the approved use.
	10. The request is audited where required.
Failure at any stage must deny access.

22. Memory Use Context
Memory authorization should be tied to a use context.
Recommended structure:
{
  "conversation_id": "conv_01JABC123",
  "agent_id": "sales-agent",
  "purpose": "personalize_product_guidance",
  "approved": true,
  "approved_at": "2026-07-19T15:30:00Z",
  "expires_at": "2026-07-19T17:30:00Z"
}
Approval for one conversation does not automatically authorize all future conversations.
Longer-lived consent may permit memory eligibility, but the customer should still retain control over whether memory is used in the current interaction.

23. Consent Model
Version 1 defines three independent consent types.
{
  "memory_storage": {
    "status": "granted",
    "version": "1.0",
    "updated_at": "2026-07-15T18:00:00Z"
  },
  "memory_use": {
    "status": "granted",
    "version": "1.0",
    "updated_at": "2026-07-15T18:00:00Z"
  },
  "marketing": {
    "status": "denied",
    "version": "1.0",
    "updated_at": "2026-07-15T18:00:00Z"
  }
}
Consent statuses:
unknown
granted
denied
withdrawn
Marketing consent must never be inferred from memory consent.

24. Consent Enforcement
Memory Storage Consent
When denied or withdrawn:
	• New memory must not be stored.
	• Existing memory handling follows the customer-selected action and approved policy.
	• The customer may be offered deletion.
	• Agents must not silently recreate deleted or withdrawn memory.
Memory Use Consent
When denied or withdrawn:
	• Memory must not be returned to agents.
	• Memory must not be injected into prompts.
	• Personalization using stored memory must stop immediately.
Marketing Consent
Controls only approved marketing communications.
It does not control authentication, service messages, security messages, or necessary transactional communications.

25. Authentication Endpoints
25.1 Request Verification Code
POST /auth/request-code
Authentication
Public.
Request
{
  "email": "customer@example.com"
}
Successful Response
{
  "success": true,
  "data": {
    "message": "If this address is eligible, we've sent a verification code.",
    "request_id": "ver_01JABC123",
    "expires_in_seconds": 600
  },
  "meta": {}
}
The public message must remain neutral.
Errors
	• INVALID_EMAIL
	• RATE_LIMITED
	• EMAIL_DELIVERY_UNAVAILABLE
	• INVALID_REQUEST

25.2 Verify Code
POST /auth/verify
Authentication
Public.
Request
{
  "request_id": "ver_01JABC123",
  "code": "482913"
}
Successful Response
{
  "success": true,
  "data": {
    "verified": true,
    "session": {
      "status": "active",
      "idle_expires_at": "2026-07-19T16:00:00Z",
      "absolute_expires_at": "2026-07-19T17:30:00Z"
    }
  },
  "meta": {}
}
The raw session token should normally be delivered through a secure HttpOnly cookie.
Errors
	• INVALID_CODE
	• CODE_EXPIRED
	• CODE_ALREADY_USED
	• VERIFICATION_LOCKED
	• RATE_LIMITED

26. Session Endpoints
26.1 Read Session
GET /auth/session
Authentication
Verified customer.
Response
{
  "success": true,
  "data": {
    "status": "active",
    "verified": true,
    "memory_use_approved": false,
    "agent_id": "sales-agent",
    "idle_expires_at": "2026-07-19T16:00:00Z",
    "absolute_expires_at": "2026-07-19T17:30:00Z"
  },
  "meta": {}
}

26.2 Log Out
POST /auth/logout
Authentication
Verified customer.
Response
{
  "success": true,
  "data": {
    "logged_out": true
  },
  "meta": {}
}
Logout must revoke the server-side session.

27. Identity Endpoint
27.1 Read Current Identity
GET /identity
Required Scope
identity:read
Authentication
Verified customer and approved agent.
Response
{
  "success": true,
  "data": {
    "customer_id": "cus_01JABC123",
    "preferred_name": "Jordan",
    "status": "active",
    "email_verified": true
  },
  "meta": {}
}
The verified email address may be omitted unless the requesting interface requires it and has explicit permission.

28. Profile Endpoints
28.1 Read Profile
GET /profile
Required Scope
profile:read
Response
{
  "success": true,
  "data": {
    "preferred_name": "Jordan",
    "experience_level": "beginner",
    "communication_preferences": {
      "detail_level": "moderate",
      "tone": "educational"
    },
    "updated_at": "2026-07-15T18:05:00Z"
  },
  "meta": {}
}

28.2 Update Profile
PATCH /profile
Required Scope
profile:update
Request
{
  "preferred_name": "Jordan",
  "experience_level": "intermediate"
}
Response
{
  "success": true,
  "data": {
    "updated_fields": [
      "preferred_name",
      "experience_level"
    ],
    "updated_at": "2026-07-19T15:30:00Z"
  },
  "meta": {}
}
Only allowlisted fields may be updated.

29. Preference Endpoints
29.1 Read Preferences
GET /preferences
Required Scope
preferences:read
Response
{
  "success": true,
  "data": {
    "product_interests": [
      "topicals"
    ],
    "format_preferences": [
      "plain-language"
    ],
    "shopping_preferences": {
      "fragrance_free": true
    }
  },
  "meta": {}
}

29.2 Update Preferences
PATCH /preferences
Required Scope
preferences:update
Request
{
  "shopping_preferences": {
    "fragrance_free": true
  }
}
The server must reject unsupported or restricted fields.

30. Consent Endpoints
30.1 Read Consent
GET /consent
Required Scope
consent:read
Response
{
  "success": true,
  "data": {
    "memory_storage": {
      "status": "granted",
      "version": "1.0",
      "updated_at": "2026-07-15T18:00:00Z"
    },
    "memory_use": {
      "status": "granted",
      "version": "1.0",
      "updated_at": "2026-07-15T18:00:00Z"
    },
    "marketing": {
      "status": "denied",
      "version": "1.0",
      "updated_at": "2026-07-15T18:00:00Z"
    }
  },
  "meta": {}
}

30.2 Update Consent
PATCH /consent
Required Scope
consent:update
Request
{
  "memory_use": "denied",
  "marketing": "denied",
  "consent_version": "1.0",
  "source": "privacy_settings"
}
Response
{
  "success": true,
  "data": {
    "updated": [
      "memory_use",
      "marketing"
    ],
    "effective_at": "2026-07-19T15:30:00Z"
  },
  "meta": {}
}
Consent changes must take effect immediately.

31. Memory Preview Endpoint
31.1 Preview Memory
GET /memory/preview
Required Scope
memory:preview
Authentication
Verified customer.
Memory-use approval is not yet required because the purpose is to show the customer what may be used.
Response
{
  "success": true,
  "data": {
    "has_memory": true,
    "profile": {
      "preferred_name": "Jordan",
      "experience_level": "beginner"
    },
    "preferences": {
      "product_interests": [
        "topicals"
      ]
    },
    "recent_context": {
      "summary": "You previously explored fragrance-free CBD topical products.",
      "last_interaction_at": "2026-07-15T18:05:00Z"
    },
    "available_namespaces": [
      "shared",
      "sales"
    ]
  },
  "meta": {}
}
The preview must use an explicit field allowlist.

32. Approve Memory Use
32.1 Approve Memory for Current Context
POST /memory/use
Required Scope
memory:read:shared
Request
{
  "conversation_id": "conv_01JABC123",
  "agent_id": "sales-agent",
  "purpose": "personalize_product_guidance",
  "approved": true
}
Response
{
  "success": true,
  "data": {
    "memory_use_approved": true,
    "conversation_id": "conv_01JABC123",
    "agent_id": "sales-agent",
    "expires_at": "2026-07-19T17:30:00Z"
  },
  "meta": {}
}
Approval must be bound to:
	• Customer session
	• Agent
	• Conversation
	• Purpose
	• Expiration

33. Start Fresh Endpoint
33.1 Start Fresh
POST /memory/start-fresh
Request
{
  "conversation_id": "conv_01JABC123",
  "agent_id": "sales-agent"
}
Response
{
  "success": true,
  "data": {
    "memory_use_approved": false,
    "start_fresh": true,
    "conversation_id": "conv_01JABC123"
  },
  "meta": {}
}
Start Fresh:
	• Disables memory use for the active conversation.
	• Does not automatically delete stored memory.
	• Does not alter marketing consent.
	• Must be respected by every agent.

34. Retrieve Shared Memory
34.1 Read Shared Memory
GET /memory/shared?conversation_id=conv_01JABC123
Required Scope
memory:read:shared
Requirements
	• Valid session
	• Registered agent
	• Active memory-use consent
	• Current-context approval
	• Authorized conversation
	• Purpose validation
Response
{
  "success": true,
  "data": {
    "profile": {
      "preferred_name": "Jordan",
      "experience_level": "beginner"
    },
    "preferences": {
      "format_preferences": [
        "plain-language"
      ]
    },
    "memory_version": 3
  },
  "meta": {}
}

35. Retrieve Agent-Specific Memory
35.1 Read Agent Memory
GET /memory/agent/sales?conversation_id=conv_01JABC123
Required Scope
memory:read:agent
Response
{
  "success": true,
  "data": {
    "namespace": "sales",
    "summary": {
      "topic": "CBD topical products",
      "customer_goal": "Compare fragrance-free options",
      "open_questions": [
        "Preferred container size"
      ]
    },
    "schema_version": 1,
    "updated_at": "2026-07-15T18:05:00Z"
  },
  "meta": {}
}
An agent must not retrieve another agent’s namespace unless explicitly authorized.

36. Store Conversation Summary
36.1 Create or Update Summary
POST /memory/summary
Required Scope
memory:write:summary
Request
{
  "conversation_id": "conv_01JABC123",
  "namespace": "sales",
  "summary": {
    "topic": "CBD topical products",
    "customer_goal": "Compare fragrance-free options",
    "resolved_questions": [
      "Difference between butter and balm"
    ],
    "open_questions": [
      "Preferred container size"
    ]
  },
  "schema_version": 1
}
Response
{
  "success": true,
  "data": {
    "memory_id": "mem_01JXYZ789",
    "namespace": "sales",
    "stored": true,
    "updated_at": "2026-07-19T15:30:00Z"
  },
  "meta": {}
}
Storage must be rejected when memory-storage consent is unavailable, denied, or withdrawn.

37. Memory Deletion Endpoint
37.1 Delete Customer Memory
DELETE /memory
Required Scope
memory:delete:self
Request
{
  "confirmation": true,
  "scope": "all_customer_memory"
}
Response
{
  "success": true,
  "data": {
    "deleted": true,
    "sessions_revoked": true,
    "effective_at": "2026-07-19T15:30:00Z"
  },
  "meta": {}
}
Deletion should remove or irreversibly de-identify approved customer-memory records according to the implementation policy.
Required security and audit records may remain where permitted by policy, but they must not be used for customer personalization.

38. Agent Context Endpoint
38.1 Retrieve Authorized Agent Context
POST /context
This endpoint provides a compact, policy-filtered context bundle for an approved Budly agent.
Required Scopes
Dependent on requested fields.
Request
{
  "conversation_id": "conv_01JABC123",
  "agent_id": "sales-agent",
  "purpose": "personalize_product_guidance",
  "requested_sections": [
    "identity",
    "profile",
    "preferences",
    "shared_memory",
    "agent_memory"
  ]
}
Response
{
  "success": true,
  "data": {
    "customer": {
      "preferred_name": "Jordan",
      "experience_level": "beginner"
    },
    "preferences": {
      "format_preferences": [
        "plain-language"
      ]
    },
    "shared_memory": {
      "product_interests": [
        "topicals"
      ]
    },
    "agent_memory": {
      "topic": "CBD topical products",
      "open_questions": [
        "Preferred container size"
      ]
    },
    "policy": {
      "memory_use_approved": true,
      "marketing_allowed": false,
      "start_fresh": false
    }
  },
  "meta": {}
}
This endpoint should return only the minimum information required for the declared purpose.

39. Context Injection Rules
When an agent receives memory context:
	• Treat it as background context, not unquestionable truth.
	• Do not reveal internal field names.
	• Do not repeat all stored information unnecessarily.
	• Do not claim certainty about stale information.
	• Allow the customer to correct remembered information.
	• Do not use memory for unrelated purposes.
	• Do not expose one agent’s restricted context to another.
	• Do not infer marketing permission.
	• Do not persist new memory without consent.
	• Do not place raw secure-memory payloads into public logs.

40. Data Freshness
Memory responses should include timestamps or versions where useful.
Agents should treat information as potentially stale when:
	• The customer has not confirmed it recently.
	• The record is older than the applicable freshness window.
	• The underlying preference may reasonably change.
	• The record conflicts with the customer’s current statement.
A customer’s current statement takes precedence over stored memory for the active conversation.
Persisting the correction requires valid storage consent.

41. Idempotency
State-changing endpoints should support idempotency where duplicate requests could create inconsistent state.
Recommended header:
Idempotency-Key: 72173f6d-d6f6-473e-9942-e6e3381f640f
Recommended for:
	• Consent updates
	• Memory-use approval
	• Start Fresh
	• Summary storage
	• Memory deletion
	• Administrative revocation
The server should safely return the original result for a repeated valid idempotency key.

42. Pagination
Endpoints returning collections must support pagination.
Recommended parameters:
page
per_page
cursor
Example response metadata:
{
  "meta": {
    "pagination": {
      "page": 1,
      "per_page": 25,
      "total": 117,
      "next_cursor": "eyJpZCI6MTI1fQ"
    }
  }
}
Administrative audit endpoints must use bounded pagination.

43. Filtering
Administrative or service endpoints may support approved filters.
Examples:
	• Date range
	• Agent ID
	• Memory namespace
	• Audit event type
	• Severity
	• Result
Filters must be validated against an allowlist.
Raw SQL filtering expressions must never be accepted.

44. Rate Limiting
Rate limits should be applied by:
	• IP address
	• Normalized or hashed email identity
	• Session
	• Agent ID
	• Endpoint
	• Administrative actor
Suggested initial limits:
Endpoint	Suggested Limit
Request verification code per email	3/hour
Request verification code per IP	10/hour
Verify code attempts per request	5
Profile updates	20/hour/session
Consent updates	20/hour/session
Memory preview	60/hour/session
Context retrieval	Configurable by agent
Administrative actions	Lower threshold with alerts
Rate-limit responses should include safe retry guidance.

45. Session Binding
Protected API requests must bind authorization to the verified session.
Agents must not submit a customer ID to select a different customer.
Unsafe pattern:
{
  "customer_id": "cus_other_customer"
}
Safe pattern:
The API resolves the customer exclusively from the validated session and registered agent context.
Administrative customer selection requires a separate privileged endpoint and must be audited.

46. Service-to-Service Authentication
Trusted backend agents may require service authentication.
Approved approaches may include:
	• Short-lived signed service tokens
	• Mutual TLS
	• Server-managed credentials
	• WordPress internal capability mechanisms
	• Secure workload identity
Service credentials must:
	• Be scoped to one agent
	• Be revocable
	• Expire or rotate
	• Never be embedded in browser code
	• Never replace customer consent
	• Never allow arbitrary customer impersonation
Service authentication proves the agent’s identity.
Customer authentication proves the customer’s identity.
Both may be required.

47. Administrative Endpoints
Recommended administrative endpoints:
GET  /admin/health
GET  /admin/audit
GET  /admin/agents
POST /admin/agents
PATCH /admin/agents/{agent_id}
POST /admin/sessions/revoke
POST /admin/customers/{customer_id}/sessions/revoke-all
POST /admin/email/test
GET  /admin/cleanup/status
POST /admin/cleanup/run
GET  /admin/schema
Every administrative action requires:
	• Administrator authentication
	• Capability authorization
	• CSRF or nonce protection
	• Input validation
	• Audit logging

48. Health Endpoint
48.1 System Health
GET /admin/health
Response
{
  "success": true,
  "data": {
    "overall_status": "healthy",
    "components": {
      "database": "healthy",
      "verification": "healthy",
      "sessions": "healthy",
      "consent": "healthy",
      "memory": "healthy",
      "email": "healthy",
      "audit": "healthy",
      "cleanup": "healthy"
    },
    "schema_version": "1.0.0",
    "last_cleanup_at": "2026-07-19T14:00:00Z"
  },
  "meta": {}
}
Public health checks should expose less detail than administrative checks.

49. Audit Events
Recommended event types:
verification.requested
verification.sent
verification.failed
verification.locked
verification.succeeded
session.created
session.validated
session.expired
session.revoked
consent.granted
consent.denied
consent.withdrawn
memory.previewed
memory.use_approved
memory.start_fresh
memory.read
memory.summary_created
memory.summary_updated
memory.deleted
profile.updated
preferences.updated
agent.registered
agent.updated
agent.disabled
admin.action
rate_limit.triggered
security.authorization_failed
cleanup.completed
cleanup.failed

50. Audit Record Structure
Recommended structure:
{
  "audit_id": "aud_01JABC123",
  "event_type": "memory.read",
  "actor_type": "agent",
  "actor_id": "sales-agent",
  "customer_reference": "hashed-or-opaque-reference",
  "conversation_id": "conv_01JABC123",
  "result": "success",
  "severity": "informational",
  "metadata": {
    "namespace": "sales",
    "purpose": "personalize_product_guidance"
  },
  "created_at": "2026-07-19T15:30:00Z"
}
Audit metadata must not include raw secrets or unrestricted memory content.

51. Versioning
51.1 API Versioning
Breaking changes require a new major API namespace.
Example:
/v1
/v2
51.2 Schema Versioning
Memory records must include a schema version.
Agents must declare the versions they support.
The API may transform compatible older records into the current response format.
51.3 Consent Versioning
Consent records must preserve the version of the copy or policy presented when the customer made the choice.

52. Backward Compatibility
Within Version 1:
	• Existing fields must not change meaning.
	• Required fields must not be removed.
	• New optional fields may be added.
	• New error codes may be added.
	• Existing machine-readable error codes must remain stable.
	• Agents should ignore unknown optional response fields.
Deprecations must be announced and documented before removal.

53. Data Classification
API fields should be classified as:
Public
Safe for public interface display.
Customer Visible
May be returned to the verified customer.
Agent Authorized
May be returned only to approved agents with scope and consent.
Internal
Used for operations but not returned to normal agents.
Restricted
Security-sensitive and available only through explicitly privileged workflows.
Every response serializer should enforce classification rules.

54. Data Minimization
Agents should request only the sections needed for the active purpose.
Bad request:
{
  "requested_sections": [
    "everything"
  ]
}
Good request:
{
  "requested_sections": [
    "preferred_name",
    "communication_preferences",
    "sales_summary"
  ]
}
The API may reject overly broad requests.

55. Prompt-Safety Requirements
Memory data may be supplied to AI systems, so it must be treated as untrusted input.
Required controls:
	• Store structured summaries instead of unrestricted raw text where practical.
	• Separate data from system instructions.
	• Never treat stored customer text as developer or system instructions.
	• Escape or delimit memory content before prompt injection.
	• Filter unsupported fields.
	• Limit payload size.
	• Detect malformed or suspicious memory content.
	• Do not store hidden model reasoning.
	• Do not allow one customer to influence another customer’s agent context.

56. Conversation Summary Standard
Recommended conversation-summary schema:
{
  "topic": "string",
  "customer_goal": "string",
  "resolved_questions": [
    "string"
  ],
  "open_questions": [
    "string"
  ],
  "confirmed_preferences": {
    "key": "value"
  },
  "customer_corrections": [
    "string"
  ],
  "next_recommended_step": "string",
  "summary_created_at": "2026-07-19T15:30:00Z"
}
Summary content should be:
	• Concise
	• Factual
	• Customer-relevant
	• Free from hidden instructions
	• Free from unnecessary sensitive details
	• Clear about uncertainty

57. Customer Corrections
Customers must be able to correct remembered information.
Agents should:
	1. Acknowledge the correction.
	2. Use the current customer statement immediately.
	3. Update persistent memory only with valid storage consent.
	4. Preserve auditability without retaining unnecessary incorrect content.
	5. Avoid arguing with the customer based on stored memory.

58. Deletion Semantics
Deletion may include:
	• Customer profile memory
	• Preferences
	• Conversation summaries
	• Agent-specific memory
	• Shared memory-use approvals
Deletion should also:
	• Revoke active sessions where required
	• Prevent future memory retrieval
	• Produce an audit event
	• Return a clear completion status
	• Avoid falsely claiming deletion if a component failed
Security logs required for system protection may remain under applicable policy, but they must be segregated from personalization memory.

59. Failure Behavior
Identity Service Unavailable
	• Deny protected identity operations.
	• Do not guess customer identity.
Consent Service Unavailable
	• Deny memory storage and use.
	• Fail closed.
Memory Service Unavailable
	• Permit Start Fresh conversation when possible.
	• Do not invent remembered information.
Audit Service Unavailable
	• Follow approved operational policy.
	• Critical administrative or destructive actions should normally fail closed.
	• Generate an operational alert.
Email Service Unavailable
	• Do not create an authenticated session.
	• Return a safe retry message.

60. Security Requirements
The API must enforce:
	• HTTPS
	• Strong session-token generation
	• Token hashing at rest
	• Verification-code hashing
	• Short code expiration
	• Attempt limits
	• Replay protection
	• Session revocation
	• Idle and absolute expiration
	• CSRF protection
	• Server-side authorization
	• Prepared database statements
	• Input validation
	• Output escaping
	• Rate limiting
	• Payload limits
	• Agent registration
	• Scope enforcement
	• Namespace enforcement
	• Consent enforcement
	• Safe logging
	• Secret separation
	• Append-only auditing
	• Enumeration-resistant authentication responses

61. Privacy Requirements
The API must:
	• Minimize personal data collection.
	• Avoid unnecessary sensitive data.
	• Keep marketing consent independent.
	• Provide customer-visible memory review.
	• Support customer correction and deletion.
	• Restrict internal metadata.
	• Avoid exposing customer existence publicly.
	• Avoid sharing memory between agents without authorization.
	• Avoid storing raw conversations by default.
	• Document retention behavior.

62. Testing Requirements
Authentication Tests
	• Valid verification
	• Invalid code
	• Expired code
	• Replayed code
	• Attempt lockout
	• Enumeration resistance
	• Rate limiting
Session Tests
	• Valid session
	• Idle expiration
	• Absolute expiration
	• Revocation
	• Logout
	• Cross-customer manipulation
Consent Tests
	• Consent granted
	• Consent denied
	• Consent withdrawn
	• Immediate enforcement
	• Marketing independence
Memory Tests
	• Preview allowlisting
	• Shared namespace access
	• Agent namespace isolation
	• Start Fresh
	• Storage without consent rejected
	• Use without consent rejected
	• Deletion
	• Restricted-field exclusion
Agent Tests
	• Registered agent accepted
	• Unknown agent denied
	• Disabled agent denied
	• Missing scope denied
	• Wrong namespace denied
	• Service credential rotation
Security Tests
	• SQL injection resistance
	• XSS handling
	• CSRF rejection
	• Session fixation resistance
	• Prompt-injection isolation
	• Payload-size enforcement
	• Safe error responses

63. Agent Integration Checklist
Before an agent may use the API:
	• Agent ID registered
	• Display name approved
	• Purpose documented
	• Scopes assigned
	• Memory namespaces assigned
	• Service credentials configured
	• Consent requirements mapped
	• Context fields minimized
	• Error handling implemented
	• Start Fresh supported
	• Customer correction supported
	• Logging reviewed
	• Security tests passed
	• Integration tests passed
	• Threat-model review completed

64. Example Agent Integration Flow
1. Customer begins interaction with Sales Agent.
2. Agent offers Returning Customer or Start Fresh.
3. Customer selects Returning Customer.
4. Interface requests email verification.
5. Customer submits the code.
6. API creates a verified session.
7. Agent requests memory preview.
8. Customer reviews remembered information.
9. Customer approves memory use for this conversation.
10. Agent requests authorized context.
11. API validates session, consent, agent, scope, namespace, and purpose.
12. API returns a minimized context bundle.
13. Agent personalizes the conversation.
14. Agent prepares a structured summary.
15. API checks memory-storage consent.
16. Approved summary is stored in the agent namespace.
17. Customer may later review, correct, decline, or delete memory.

65. Integration Anti-Patterns
Agents must not:
	• Build their own login system.
	• Store session tokens in local storage when secure cookies are available.
	• Query identity tables directly.
	• Trust customer IDs supplied by the browser.
	• Copy the entire shared profile into an agent database.
	• Store memory when consent is denied.
	• Treat marketing consent as implied.
	• Retrieve all namespaces.
	• Insert raw memory into system instructions.
	• Store entire transcripts without approval.
	• Use memory after Start Fresh.
	• Continue using cached memory after consent withdrawal.
	• Hide memory deletion controls.
	• Claim deletion succeeded before confirmation.
	• Expose internal API errors to customers.

66. Caching Rules
Caching may improve performance but must not weaken authorization.
Permitted:
	• Short-lived configuration cache
	• Agent-registry cache
	• Non-sensitive schema metadata
	• Per-request context cache
Restricted:
	• Customer memory cache must be session-bound.
	• Consent cache must have a short lifetime or immediate invalidation.
	• Revoked sessions must invalidate cached authorization.
	• Start Fresh must invalidate active memory context.
	• Deleted memory must be purged from application caches.
	• Shared caches must never mix customer records.

67. Observability
Recommended metrics:
	• Verification requests
	• Verification success rate
	• Verification failure rate
	• Code lockouts
	• Active sessions
	• Session-validation failures
	• Consent grants and withdrawals
	• Memory previews
	• Memory-use approvals
	• Start Fresh selections
	• Memory reads by agent
	• Memory writes by agent
	• Authorization denials
	• Namespace violations
	• Deletion requests
	• API latency
	• Service errors
Metrics must avoid exposing raw customer information.

68. Service-Level Expectations
Initial operational targets may include:
	• API availability target defined by deployment policy
	• Fast session validation
	• Predictable memory retrieval latency
	• Immediate consent enforcement
	• Immediate revocation enforcement
	• Graceful fallback when memory is unavailable
	• No authentication fallback when verification is unavailable
Exact service-level objectives should be established from production observations rather than invented traffic assumptions.

69. Documentation Requirements
Every integrated agent must document:
	• Agent ID
	• Agent purpose
	• Requested scopes
	• Memory namespaces
	• Requested context fields
	• Stored summary fields
	• Consent dependencies
	• Error behavior
	• Start Fresh behavior
	• Deletion behavior
	• Security assumptions
	• Test coverage
The central API documentation must remain the source of truth.

70. Implementation Acceptance Criteria
The Identity & Memory API is complete when:
Identity
✓ A verified session securely resolves one customer identity.
✓ Agents cannot select customers using client-provided identifiers.
Agents
✓ Every agent is registered and scope-controlled.
✓ Disabled or unknown agents are denied.
Consent
✓ Memory storage and memory use are independently enforced.
✓ Marketing consent remains separate.
✓ Consent changes take effect immediately.
Memory
✓ Shared and agent-specific namespaces are separated.
✓ Customer-visible fields are explicitly allowlisted.
✓ Start Fresh prevents memory use for the active conversation.
✓ Memory deletion prevents future personalization access.
Security
✓ Verification codes and session tokens are never stored in plaintext.
✓ Replay, brute-force, enumeration, CSRF, injection, and cross-customer tests pass.
✓ Service authentication does not override customer consent.
Operations
✓ Audit events are generated.
✓ Health checks are available.
✓ Errors are safe and standardized.
✓ Rate limiting is enforced.
Compatibility
✓ Version 1 contracts are documented.
✓ Schema versions are tracked.
✓ Future agents can integrate without duplicating identity or consent logic.

71. Definition of Done
Asset 5 is considered implemented when:
	• The Version 1 API namespace is operational.
	• All required endpoints are available.
	• Authentication and session behavior match Asset 1.
	• Threat controls match Asset 2.
	• Customer-facing behavior supports Asset 3.
	• The implementation follows the Codex build requirements in Asset 4.
	• Agent registration and scope enforcement work.
	• Shared and agent-specific memory are isolated.
	• Consent is checked before every memory operation.
	• Automated security and integration tests pass.
	• Developer and agent-integration documentation are complete.
	• No unresolved critical or high-severity security defects remain.

72. Final Platform Statement
The Budly Identity & Memory API is the shared trust layer for the Budly ecosystem.
It allows multiple Budly agents to recognize and assist the same verified customer without creating disconnected accounts, duplicated profiles, conflicting consent records, or uncontrolled memory silos.
The platform preserves a simple rule:
A Budly agent may use only the customer information it needs, for a purpose the customer has approved, within a session the system has verified.
This contract should govern every future integration involving Budly customer identity, consent, preferences, or remembered context.

End of Asset 5
Asset 5 Status: COMPLETE
The approved Secure Returning-Customer Memory planning package is now complete:
	• Asset 1: Secure Memory Architecture Specification
	• Asset 2: Threat Model & Abuse Cases
	• Asset 3: Customer Experience & Screen Copy
	• Asset 4: Codex Remote Build Command
	• Asset 5: Budly Identity & Memory API Specification
Together, these five assets form the complete architecture, security, customer-experience, implementation, and integration contract for the Budly Secure Returning-Customer Memory System.
