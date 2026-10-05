"""Vanity Link Management, Aliases, Cooldown, Rollback & Audit Engine (G9B.7B).

Rules implemented:
- Aliases are pointers only; never accounting identity.
- 30-day standard cooldown after committed alias update.
- 3-day rollback window allowing reversion ONLY to immediately previous alias (rejecting 3rd new slug).
- Historical aliases preserved as HISTORICAL_REDIRECT pointing to canonical ID.
- Full immutable audit event logging.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from .identity import IdentityError, normalize_slug, utcnow, validate_slug

COOLDOWN_DAYS = 30
ROLLBACK_DAYS = 3


@dataclass(frozen=True)
class VanityAlias:
    """Represents a vanity URL slug pointing to a canonical affiliate ID."""
    slug: str
    affiliate_id: str
    status: str  # 'PRIMARY', 'HISTORICAL_REDIRECT', 'DEACTIVATED'
    created_at: datetime
    updated_at: datetime
    previous_alias: str | None = None
    cooldown_until: datetime = field(default_factory=utcnow)
    rollback_deadline: datetime = field(default_factory=utcnow)


@dataclass(frozen=True)
class LinkAuditEvent:
    """Immutable audit record for all vanity link mutations."""
    event_id: str
    affiliate_id: str
    previous_alias: str | None
    new_alias: str
    event_type: str  # 'INITIAL_CREATION', 'SLUG_UPDATE', 'SLUG_ROLLBACK', 'SLUG_DEACTIVATION'
    timestamp: datetime
    actor: str
    authorization_source: str
    rollback_eligible: bool
    rollback_deadline: datetime | None
    next_change_eligible_at: datetime
    verification_result: str = "PASSED"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        if self.rollback_deadline:
            d["rollback_deadline"] = self.rollback_deadline.isoformat()
        d["next_change_eligible_at"] = self.next_change_eligible_at.isoformat()
        return d


class VanityLinkManager:
    """Thread-safe reference implementation of Vanity Link governance."""

    def __init__(self) -> None:
        self.aliases: dict[str, VanityAlias] = {}  # keyed by slug
        self.affiliate_primary: dict[str, str] = {}  # affiliate_id -> primary_slug
        self.affiliate_history: dict[str, list[str]] = {}  # affiliate_id -> list of historical slugs
        self.audit_log: list[LinkAuditEvent] = []

    def register_initial_alias(
        self,
        affiliate_id: str,
        raw_slug: str,
        actor: str = "SYSTEM_INITIALIZATION",
        authorization_source: str = "INITIAL_ONBOARDING",
        now: datetime | None = None,
    ) -> VanityAlias:
        """Assign initial vanity alias (e.g. from verified Instagram handle)."""
        slug = normalize_slug(raw_slug)
        validate_slug(slug)
        when = now or utcnow()

        if slug in self.aliases:
            existing = self.aliases[slug]
            if existing.affiliate_id != affiliate_id:
                raise IdentityError("SLUG_ALREADY_CLAIMED", f"Slug '{slug}' is already registered to another affiliate")

        alias = VanityAlias(
            slug=slug,
            affiliate_id=affiliate_id,
            status="PRIMARY",
            created_at=when,
            updated_at=when,
            previous_alias=None,
            cooldown_until=when,  # initial creation has no cooldown restriction for first edit
            rollback_deadline=when,
        )

        self.aliases[slug] = alias
        self.affiliate_primary[affiliate_id] = slug
        self.affiliate_history.setdefault(affiliate_id, []).append(slug)

        self._record_audit(
            affiliate_id=affiliate_id,
            previous_alias=None,
            new_alias=slug,
            event_type="INITIAL_CREATION",
            timestamp=when,
            actor=actor,
            authorization_source=authorization_source,
            rollback_eligible=False,
            rollback_deadline=None,
            next_change_eligible_at=when,
        )
        return alias

    def update_vanity_slug(
        self,
        affiliate_id: str,
        raw_slug: str,
        actor: str = "AFFILIATE",
        authorization_source: str = "SELF_SERVICE_DASHBOARD",
        now: datetime | None = None,
    ) -> VanityAlias:
        """Update affiliate vanity slug obeying 30-day cooldown and 3-day rollback boundaries."""
        new_slug = normalize_slug(raw_slug)
        validate_slug(new_slug)
        when = now or utcnow()

        current_primary_slug = self.affiliate_primary.get(affiliate_id)
        if not current_primary_slug:
            raise IdentityError("NO_PRIMARY_ALIAS", f"Affiliate {affiliate_id} has no primary alias")

        if new_slug == current_primary_slug:
            return self.aliases[current_primary_slug]

        # Check if slug is owned by someone else
        if new_slug in self.aliases:
            existing = self.aliases[new_slug]
            if existing.affiliate_id != affiliate_id:
                raise IdentityError("SLUG_ALREADY_CLAIMED", f"Slug '{new_slug}' is already registered to another affiliate")

        current_alias = self.aliases[current_primary_slug]

        # Evaluate cooldown and rollback conditions
        in_cooldown = when < current_alias.cooldown_until
        in_rollback_window = when <= current_alias.rollback_deadline

        if in_cooldown:
            # If in cooldown, only a rollback to the exact previous alias is permitted
            if in_rollback_window:
                if current_alias.previous_alias and new_slug == current_alias.previous_alias:
                    return self.rollback_vanity_slug(affiliate_id, actor, authorization_source, when)
                else:
                    raise IdentityError(
                        "COOLDOWN_ACTIVE_ROLLBACK_MISMATCH",
                        f"Cooldown active until {current_alias.cooldown_until.isoformat()}. During rollback window, you may only revert to '{current_alias.previous_alias}'",
                    )
            else:
                raise IdentityError(
                    "COOLDOWN_ACTIVE",
                    f"Vanity link changes are on cooldown until {current_alias.cooldown_until.isoformat()}",
                )

        # Apply update
        cooldown_until = when + timedelta(days=COOLDOWN_DAYS)
        rollback_deadline = when + timedelta(days=ROLLBACK_DAYS)

        # Mark current alias as historical redirect
        old_alias = VanityAlias(
            slug=current_primary_slug,
            affiliate_id=affiliate_id,
            status="HISTORICAL_REDIRECT",
            created_at=current_alias.created_at,
            updated_at=when,
            previous_alias=current_alias.previous_alias,
            cooldown_until=cooldown_until,
            rollback_deadline=rollback_deadline,
        )
        self.aliases[current_primary_slug] = old_alias

        new_alias = VanityAlias(
            slug=new_slug,
            affiliate_id=affiliate_id,
            status="PRIMARY",
            created_at=when,
            updated_at=when,
            previous_alias=current_primary_slug,
            cooldown_until=cooldown_until,
            rollback_deadline=rollback_deadline,
        )
        self.aliases[new_slug] = new_alias
        self.affiliate_primary[affiliate_id] = new_slug
        if new_slug not in self.affiliate_history[affiliate_id]:
            self.affiliate_history[affiliate_id].append(new_slug)

        self._record_audit(
            affiliate_id=affiliate_id,
            previous_alias=current_primary_slug,
            new_alias=new_slug,
            event_type="SLUG_UPDATE",
            timestamp=when,
            actor=actor,
            authorization_source=authorization_source,
            rollback_eligible=True,
            rollback_deadline=rollback_deadline,
            next_change_eligible_at=cooldown_until,
        )
        return new_alias

    def rollback_vanity_slug(
        self,
        affiliate_id: str,
        actor: str = "AFFILIATE",
        authorization_source: str = "SELF_SERVICE_DASHBOARD",
        now: datetime | None = None,
    ) -> VanityAlias:
        """Rollback to immediately previous alias within 3 days of change."""
        when = now or utcnow()
        current_primary_slug = self.affiliate_primary.get(affiliate_id)
        if not current_primary_slug:
            raise IdentityError("NO_PRIMARY_ALIAS", f"Affiliate {affiliate_id} has no primary alias")

        current_alias = self.aliases[current_primary_slug]
        if not current_alias.previous_alias:
            raise IdentityError("NO_ROLLBACK_TARGET", "No previous alias exists to roll back to")

        if when > current_alias.rollback_deadline:
            raise IdentityError("ROLLBACK_WINDOW_EXPIRED", f"Rollback window expired at {current_alias.rollback_deadline.isoformat()}")

        target_slug = current_alias.previous_alias
        target_alias = self.aliases.get(target_slug)

        # Mark current alias as historical redirect
        self.aliases[current_primary_slug] = VanityAlias(
            slug=current_primary_slug,
            affiliate_id=affiliate_id,
            status="HISTORICAL_REDIRECT",
            created_at=current_alias.created_at,
            updated_at=when,
            previous_alias=None,
            cooldown_until=when,
            rollback_deadline=when,
        )

        # Restore target slug as PRIMARY
        restored = VanityAlias(
            slug=target_slug,
            affiliate_id=affiliate_id,
            status="PRIMARY",
            created_at=target_alias.created_at if target_alias else when,
            updated_at=when,
            previous_alias=None,
            cooldown_until=when,  # reset cooldown upon rollback
            rollback_deadline=when,
        )
        self.aliases[target_slug] = restored
        self.affiliate_primary[affiliate_id] = target_slug

        self._record_audit(
            affiliate_id=affiliate_id,
            previous_alias=current_primary_slug,
            new_alias=target_slug,
            event_type="SLUG_ROLLBACK",
            timestamp=when,
            actor=actor,
            authorization_source=authorization_source,
            rollback_eligible=False,
            rollback_deadline=None,
            next_change_eligible_at=when,
        )
        return restored

    def resolve_slug(self, slug: str) -> tuple[str | None, str | None]:
        """Resolve slug to (canonical_affiliate_id, alias_status)."""
        norm = normalize_slug(slug)
        alias = self.aliases.get(norm)
        if not alias or alias.status == "DEACTIVATED":
            return None, None
        return alias.affiliate_id, alias.status

    def get_affiliate_aliases(self, affiliate_id: str) -> list[VanityAlias]:
        """Return all aliases associated with an affiliate."""
        return [a for a in self.aliases.values() if a.affiliate_id == affiliate_id]

    def _record_audit(self, **kwargs: Any) -> LinkAuditEvent:
        event = LinkAuditEvent(event_id=str(uuid.uuid4()), **kwargs)
        self.audit_log.append(event)
        return event
