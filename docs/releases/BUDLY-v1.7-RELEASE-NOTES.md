# Budly v1.7.0 Release Notes

**Release**: Budly v1.7: Conversation Intelligence and Customer Lifecycle
**Target Application Version**: 1.7.0
**Target Schema Version**: 1.5.0

## Summary of Changes
Budly v1.7 upgrades the Budly Sales Agent from a question-driven deterministic assistant into a conversation-driven guide.

### Key Capabilities Introduced
- **Conversation State Machine**: Maintains auditable, explicit conversation states (`visitor`, `exploring`, `discovering`, `evaluating_recommendation`, `recovering`, `completed`).
- **Adaptive Question Engine**: Dynamically ranks next questions by expected information value while skipping already-known attributes and avoiding questionnaire behavior.
- **Explainable Recommendation Rationale**: Generates transparent, human-explainable rationale (`observation`, `reasoning`, `recommendation`, `explanation`, `confirmation_prompt`) based strictly on consented customer inputs.
- **Canonical Customer Lifecycle Engine**: Tracks customer lifecycle across canonical states (`Visitor`, `Explorer`, `Member`, `Returning Member`, `Community Member`, `Advocate`, `Leader`).
- **Relationship Health**: Measures trust, engagement, and knowledge scores over time.
- **Pattern Library**: Structured conversation patterns for First Visit, Returning Member, Product Recommendation, Comparison, Complaint, Wholesale, and Recovery.
- **Additive Schema 1.5.0**: Adds `budly_conversation_state`, `budly_conversation_pattern_history`, `budly_relationship_health`, and `budly_member_journey`.
- **WordPress Admin Visibility**: Protected endpoints for conversation health and lifecycle distribution reporting.
