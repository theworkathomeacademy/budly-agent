Budly Secure Memory System
Asset 3
Customer Experience & Screen Copy
Version 1.0

1. Purpose
The Customer Experience specification defines the complete interaction between a returning customer and the Secure Memory System.
The goals are to:
	• Minimize friction
	• Build trust
	• Explain why verification is required
	• Give customers meaningful control over remembered information
	• Make privacy understandable without overwhelming users
The experience should feel welcoming, transparent, and respectful.
Budly should never make customers feel like they are being interrogated.

2. UX Design Principles
Every screen follows these principles.
Simplicity
One primary action per screen.
Avoid unnecessary choices.

Transparency
Explain:
	• Why information is requested
	• Why verification is required
	• What Budly remembers
	• How customers remain in control

Respect
Budly asks for permission.
Budly never assumes permission.

Confidence
Use reassuring language.
Avoid technical jargon.

Accessibility
Every interaction should support:
	• Keyboard navigation
	• Screen readers
	• High contrast
	• Mobile devices
	• Responsive layouts

3. Customer Journey
Start Chat
     │
     ▼
Budly detects returning customer option
     │
     ▼
Customer chooses:
     • Continue as Returning Customer
     • Start Fresh
     │
     ▼
Email Verification
     │
     ▼
Verification Code
     │
     ▼
Verification Success
     │
     ▼
Memory Preview
     │
     ▼
Customer decides:
     • Use Memory
     • Start Fresh
     • Review Memory
     • Update Consent
     │
     ▼
Conversation Begins

4. Screen 1
Welcome Back
Purpose
Introduce the returning customer experience.

Heading
Welcome Back

Body
If you’ve chatted with Budly before, we can securely reconnect you with your saved preferences and conversation history.
We’ll first verify that you have access to your email address before showing any remembered information.
Your privacy comes first.

Primary Button
Continue as Returning Customer

Secondary Button
Start a New Conversation

Footer
You can always choose not to use remembered information after verification.

5. Screen 2
Enter Email
Heading
Verify Your Email

Body
Enter the email address you previously used with Budly.
We’ll send you a one-time verification code.

Field
Email Address

Primary Button
Send Verification Code

Validation
Invalid email:
Please enter a valid email address.

Success Message
If this address is eligible, we’ve sent a verification code.

6. Screen 3
Check Your Email
Heading
Check Your Inbox

Body
We’ve sent a six-digit verification code.
Enter it below to continue.
If you don’t see it within a few minutes, check your spam or junk folder.

Field
Verification Code

Primary Button
Verify

Secondary Button
Resend Code
(Subject to rate limits.)

7. Screen 4
Verification Failed
Incorrect code:
That code doesn’t match. Please try again.

Expired code:
That code has expired. Request a new one to continue.

Too many attempts:
For your security, this verification request has been locked. Please request a new code.
These messages avoid exposing unnecessary implementation details.

8. Screen 5
Verification Successful
Heading
You’re Verified

Body
Thanks! We found information you’ve previously allowed Budly to remember.
Before we use it, we’d like to show you exactly what we’ll use.
You’re always in control.

Button
Review Remembered Information

9. Screen 6
Memory Preview
Heading
Here’s What Budly Remembers

Display cards such as:
Preferred Name
Jordan

Experience Level
Beginner

Shopping Goal
CBD Education

Preferred Product Types
Topicals

Last Conversation
You explored fragrance-free CBD topical products and asked about daily use.

Last Visit
July 15, 2026

Buttons
Use This Information
Start Fresh
Review Privacy Settings

10. Screen 7
Start Fresh
Heading
Start Fresh

Body
No problem.
Budly won’t use your remembered information during this conversation.
Your saved preferences will remain available for future visits unless you choose to delete them.

Button
Start Conversation

11. Screen 8
Memory Enabled
Heading
Great! Let’s Pick Up Where We Left Off

Body
Budly will use your remembered information to personalize this conversation.
You can change this at any time.

Button
Continue

12. Screen 9
Privacy Settings
Display current settings.
Remember my preferences
ON/OFF

Use remembered information during verified conversations
ON/OFF

Receive marketing updates
ON/OFF
Each setting should include a plain-language explanation.

13. Screen 10
Delete Remembered Information
Heading
Delete Remembered Information

Body
You can permanently remove the information Budly remembers about you.
This action cannot be undone.
Your security and audit records may still be retained where required to protect the system and investigate security events.

Confirmation Checkbox
I understand that this action cannot be undone.

Button
Delete My Remembered Information

14. Screen 11
Memory Deleted
Heading
Your Remembered Information Has Been Deleted

Body
Budly has removed the information used to personalize your conversations.
If you return in the future, you’ll begin with a new conversation unless you choose to save information again.

15. Session Expired
Heading
Verification Expired

Body
For your security, your verified session has expired.
You can quickly verify your email again to continue.

Button
Verify Again

16. Error Messages
The system should use calm, informative language.
Examples:
Instead of:
Authentication Error 483
Use:
We couldn’t verify your session. Please verify your email again.

Instead of:
Database Failure
Use:
We’re temporarily unable to retrieve remembered information. You can still start a new conversation.

Instead of:
Permission Denied
Use:
Budly doesn’t have permission to complete that action.

17. Loading States
Avoid blank screens.
Examples:
Sending verification code…
Verifying your code…
Loading remembered information…
Updating your privacy settings…
Deleting remembered information…
Each loading indicator should reassure the customer that work is in progress.

18. Empty States
If no remembered information exists:
Heading
Nothing Saved Yet
Body
Budly doesn’t have any remembered information for this email yet.
Let’s start a new conversation together.

Button
Start Conversation

19. Accessibility Requirements
Customer-facing interfaces should provide:
	• Keyboard-only navigation
	• Screen reader labels
	• Descriptive button text
	• Error messages announced to assistive technologies
	• High-contrast compatibility
	• Responsive layouts
	• Minimum touch target sizes appropriate for mobile devices
Animations should respect reduced-motion preferences when supported.

20. Tone & Voice Guide
Budly should sound:
	• Friendly
	• Respectful
	• Clear
	• Professional
	• Reassuring
	• Educational
Budly should avoid sounding:
	• Robotic
	• Alarmist
	• Overly technical
	• Condescending
	• Pushy
Privacy and security messaging should be confident without creating unnecessary anxiety.

21. Production Copy Guidelines
All customer-facing text should:
	• Use plain language
	• Avoid unexplained technical terms
	• Be concise
	• Explain the purpose of requests
	• Reinforce customer control
When errors occur, messages should explain what happened (when appropriate) and what the customer can do next, without exposing sensitive implementation details.

22. Customer Journey Acceptance Criteria
The experience is considered complete when a customer can:
✓ Recognize the returning customer option.
✓ Verify their email.
✓ Understand why verification is required.
✓ Review remembered information.
✓ Choose whether to use it.
✓ Update privacy settings.
✓ Delete remembered information.
✓ Recover from common errors without confusion.
✓ Complete the entire process comfortably on desktop or mobile.

23. Future Experience Enhancements
The experience is designed to accommodate future improvements without changing the core journey, such as:
	• Passkey-based sign-in
	• Remembered trusted devices (subject to security review)
	• Mobile app integration
	• Personalized onboarding
	• Expanded preference management
	• Multi-language support
	• Accessibility enhancements
	• Context-aware help
Future additions should preserve the same principles of transparency, customer control, and minimal friction.

24. Final Acceptance Criteria
Asset 3 is complete when:
✓ Every customer-facing screen has a defined purpose.
✓ All primary workflows are documented.
✓ Production-ready copy exists for key screens and messages.
✓ Error, loading, and empty states are covered.
✓ Accessibility expectations are defined.
✓ Tone and voice guidelines are established.
✓ The experience reflects the architecture and security requirements from Assets 1 and 2.

End of Asset 3
Asset 3 Status: COMPLETE ✅
At this point we have completed:
	• ✅ Asset 1: Secure Memory Architecture Specification
	• ✅ Asset 2: Threat Model & Abuse Cases
	• ✅ Asset 3: Customer Experience & Screen Copy


