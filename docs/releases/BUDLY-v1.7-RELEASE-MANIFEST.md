# BUDLY v1.7 RELEASE MANIFEST

**Release**: Budly v1.7: Conversation Intelligence and Customer Lifecycle
**Target Application Version**: 1.7.0
**Target Schema Version**: 1.5.0
**Governed Rules Version**: bros-rules-1.5.0.0
**Commerce Configuration Version**: commerce-attribution-1.6.0.0
**Conversation Intelligence Configuration Version**: conversation-intelligence-1.7.0.0
**Branch**: `release/budly-v1.7`
**Status**: CANDIDATE (PR Ready for Review; Gate F Blocked; Production Unauthorized)

## Core Components
- `deploy/wordpress/budly-sales-agent/budly-sales-agent.php` (Version 1.7.0)
- `deploy/wordpress/budly-sales-agent/includes/SecureMemory/Config.php` (Schema 1.5.0, 24 allowed tables)
- `deploy/wordpress/budly-sales-agent/includes/SecureMemory/Database/Migrator.php` (Additive Schema 1.5.0 migration)
- `deploy/wordpress/budly-sales-agent/includes/Conversation/ConversationManager.php` (Conversation State Machine & Adaptive Questioning)
- `deploy/wordpress/budly-sales-agent/includes/Lifecycle/LifecycleEngine.php` (Canonical Lifecycle Engine & Relationship Health)
- `deploy/wordpress/budly-sales-agent/includes/SecureMemory/Api/Routes.php` (v1.7 REST endpoints and admin health/lifecycle visibility)
- `src/sales_agent.py` (Version 1.7.0, Schema 1.5.0, Adaptive Questioning & Rationale Builder)
- `src/conversation_service.py` (v1.7 Customer-facing orchestration & Rationale output)

## Schema 1.5.0 Additive Database Tables
1. `budly_conversation_state` (Explicit conversation state machine tracking & UUIDs)
2. `budly_conversation_pattern_history` (Pattern execution history & match scores)
3. `budly_relationship_health` (Relationship health metrics & trust/engagement scores)
4. `budly_member_journey` (Member journey milestones & audit references)

## Canonical Customer Lifecycle States
- Visitor
- Explorer
- Member
- Returning Member
- Community Member
- Advocate
- Leader
