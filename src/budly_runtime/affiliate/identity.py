"""Canonical Affiliate Identity & Referral Token Definitions (G9B.7B).

Defines:
- Canonical Affiliate ID format (AFF-######)
- Canonical Referral Token generator (random, non-sequential, non-guessable, 8-12 alphanumeric chars)
- Slug normalization, reserved word checks, and syntax validation.
"""

from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

CANONICAL_ID_REGEX = re.compile(r"^AFF-[0-9]{6}$")
REFERRAL_TOKEN_REGEX = re.compile(r"^[A-HJ-NP-Z2-9]{8,12}$")
SLUG_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]{1,28}[a-z0-9]$")

RESERVED_SLUGS = frozenset({
    "admin", "api", "auth", "app", "login", "logout", "register", "cart",
    "checkout", "shop", "account", "dashboard", "budly", "bros", "terms",
    "privacy", "help", "support", "r", "go", "wp-admin", "wp-login",
    "affiliate", "affiliates", "partner", "partners", "billing", "root",
    "test", "system", "null", "undefined", "order", "orders", "webhook",
    "webhooks", "public", "private", "internal", "assets", "static", "images",
    "css", "js", "wp-content", "wp-includes", "wp-json", "feed", "comments",
    "product", "products", "category", "tag", "explore", "search", "home",
})

PROHIBITED_TERMS = frozenset({
    "official", "support-team", "billing-help", "customer-service", "security",
    "system-admin", "verification", "verified-badge",
})

TOKEN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Base32 crockford-like without I, O, 0, 1


class IdentityError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_canonical_id(sequence: int) -> str:
    """Generate deterministic immutable canonical affiliate ID."""
    if sequence < 1 or sequence > 999999:
        raise IdentityError("INVALID_SEQUENCE", "Sequence must be between 1 and 999999")
    return f"AFF-{sequence:06d}"


def generate_referral_token(length: int = 8) -> str:
    """Generate high-entropy, non-sequential, non-guessable canonical referral token."""
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(length))


def normalize_slug(raw_slug: str) -> str:
    """Normalize input slug (stripping @, lowercasing, replacing spaces/dots with hyphens)."""
    if not raw_slug:
        return ""
    slug = raw_slug.strip().lstrip("@").lower()
    slug = re.sub(r"[\s\._]+", "-", slug)
    slug = re.sub(r"[^a-z0-9_-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-_")
    return slug


def validate_slug(slug: str) -> None:
    """Validate slug syntax, length, reserved words, and prohibited terms."""
    if not slug:
        raise IdentityError("SLUG_TOO_SHORT", "Vanity slug cannot be empty")
    if slug in RESERVED_SLUGS:
        raise IdentityError("RESERVED_SLUG", f"Slug '{slug}' is reserved by system architecture")
    if len(slug) < 3:
        raise IdentityError("SLUG_TOO_SHORT", "Vanity slug must be at least 3 characters long")
    if len(slug) > 30:
        raise IdentityError("SLUG_TOO_LONG", "Vanity slug must be at most 30 characters long")
    if not SLUG_REGEX.match(slug):
        raise IdentityError("INVALID_SLUG_SYNTAX", f"Slug '{slug}' contains invalid characters or structure")
    for term in PROHIBITED_TERMS:
        if term in slug:
            raise IdentityError("PROHIBITED_SLUG_TERM", f"Slug '{slug}' contains prohibited term '{term}'")


@dataclass(frozen=True)
class CanonicalIdentity:
    """Immutable Canonical Affiliate Identity."""
    affiliate_id: str
    referral_token: str
    email: str
    public_display_name: str
    affiliate_class: str = "STANDARD"
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not CANONICAL_ID_REGEX.match(self.affiliate_id):
            raise IdentityError("INVALID_CANONICAL_ID", f"Invalid canonical ID format: {self.affiliate_id}")
        if not REFERRAL_TOKEN_REGEX.match(self.referral_token):
            raise IdentityError("INVALID_REFERRAL_TOKEN", f"Invalid referral token format: {self.referral_token}")
        if not self.email or "@" not in self.email:
            raise IdentityError("INVALID_EMAIL", "Valid email is required")
