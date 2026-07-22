# Budly Secure Returning-Customer Memory System

## Purpose

This directory contains the approved and authoritative specifications for Phase 3 of the Budly platform:

**Secure Returning-Customer Memory**

These documents govern the implementation, security, customer experience, API design, testing, deployment, and acceptance of the system.

## Authoritative Documents

1. [Asset 1: Secure Memory Architecture](./asset-1-secure-memory-architecture.md)
2. [Asset 2: Threat Model and Abuse Cases](./asset-2-threat-model.md)
3. [Asset 3: Customer Experience and Screen Copy](./asset-3-customer-experience.md)
4. [Asset 4: Codex Build Command](./asset-4-codex-build-command.md)
5. [Asset 5: Identity and Memory API](./asset-5-identity-memory-api.md)

## Authority and Precedence

These five documents are authoritative.

When the current implementation conflicts with these documents, the approved documents govern unless an explicit written amendment is added to this directory.

Asset 4 defines the implementation workflow.

Assets 1, 2, 3, and 5 define the architecture, security requirements, customer experience, and API contract that Asset 4 must implement.

## Required Reading Order

Codex and human engineers must read the documents in this order:

1. This README
2. Asset 1
3. Asset 2
4. Asset 3
5. Asset 5
6. Asset 4

Asset 4 must be executed only after the supporting specifications have been read.

## Current Implementation Status

The deployed version 1.2.0 implementation is an incomplete MVP.

It must not be treated as the approved final architecture.

Known gaps include:

- Client-forged consent and memory poisoning
- Missing server-side verified sessions
- Incomplete OTP expiry and resend controls
- Missing privacy export and deletion controls
- Missing administrative memory tooling
- Missing retention and cleanup operations
- Incomplete functional and security testing

## Scope Restriction

Phase 4, WooCommerce Purchase Attribution, must not begin until Phase 3 satisfies the approved acceptance gates.
