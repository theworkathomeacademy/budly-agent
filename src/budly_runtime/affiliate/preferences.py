"""Structured Affiliate Preference Storage & Audit Engine (G9B.7B).

Preference Classes:
- PUBLIC_NAME
- CHANNEL
- PRODUCT
- CAMPAIGN
- CONTENT
- LINK

Each record preserves:
- affiliate_id
- preference_type
- preference_key
- preference_value
- source
- created_at
- updated_at
- current_status ('ACTIVE', 'OVERRIDDEN', 'DELETED')
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

ALLOWED_PREFERENCE_TYPES = frozenset({
    "PUBLIC_NAME", "CHANNEL", "PRODUCT", "CAMPAIGN", "CONTENT", "LINK"
})


class PreferenceError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AffiliatePreference:
    id: str
    affiliate_id: str
    preference_type: str
    preference_key: str
    preference_value: Any
    source: str
    created_at: datetime
    updated_at: datetime
    current_status: str = "ACTIVE"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return d


class AffiliatePreferenceStore:
    """In-memory reference store for structured affiliate preferences."""

    def __init__(self) -> None:
        self.preferences: dict[str, AffiliatePreference] = {}  # keyed by id
        self.by_affiliate: dict[str, dict[tuple[str, str], str]] = {}  # affiliate_id -> (type, key) -> pref_id
        self.audit_log: list[dict[str, Any]] = []

    def set_preference(
        self,
        affiliate_id: str,
        preference_type: str,
        preference_key: str,
        preference_value: Any,
        source: str = "AFFILIATE_DASHBOARD",
        actor: str = "AFFILIATE",
        now: datetime | None = None,
    ) -> AffiliatePreference:
        """Create or update a structured affiliate preference."""
        if preference_type not in ALLOWED_PREFERENCE_TYPES:
            raise PreferenceError("INVALID_PREFERENCE_TYPE", f"Unknown preference type: {preference_type}")
        if not preference_key or not preference_key.strip():
            raise PreferenceError("INVALID_PREFERENCE_KEY", "Preference key cannot be empty")

        when = now or utcnow()
        aff_prefs = self.by_affiliate.setdefault(affiliate_id, {})
        key_tuple = (preference_type, preference_key.strip().lower())

        existing_id = aff_prefs.get(key_tuple)
        if existing_id:
            old_pref = self.preferences[existing_id]
            # Mark previous as OVERRIDDEN
            self.preferences[existing_id] = AffiliatePreference(
                id=old_pref.id,
                affiliate_id=affiliate_id,
                preference_type=preference_type,
                preference_key=key_tuple[1],
                preference_value=old_pref.preference_value,
                source=old_pref.source,
                created_at=old_pref.created_at,
                updated_at=when,
                current_status="OVERRIDDEN",
            )
            created_at = old_pref.created_at
        else:
            created_at = when

        pref_id = str(uuid.uuid4())
        pref = AffiliatePreference(
            id=pref_id,
            affiliate_id=affiliate_id,
            preference_type=preference_type,
            preference_key=key_tuple[1],
            preference_value=preference_value,
            source=source,
            created_at=created_at,
            updated_at=when,
            current_status="ACTIVE",
        )
        self.preferences[pref_id] = pref
        aff_prefs[key_tuple] = pref_id

        self.audit_log.append({
            "event_id": str(uuid.uuid4()),
            "affiliate_id": affiliate_id,
            "action": "PREFERENCE_SET",
            "preference_type": preference_type,
            "preference_key": key_tuple[1],
            "preference_value": preference_value,
            "previous_id": existing_id,
            "actor": actor,
            "source": source,
            "timestamp": when.isoformat(),
        })
        return pref

    def get_preference(self, affiliate_id: str, preference_type: str, preference_key: str) -> Any | None:
        """Get the active preference value for a specific key."""
        aff_prefs = self.by_affiliate.get(affiliate_id, {})
        key_tuple = (preference_type, preference_key.strip().lower())
        pref_id = aff_prefs.get(key_tuple)
        if not pref_id:
            return None
        pref = self.preferences.get(pref_id)
        if not pref or pref.current_status != "ACTIVE":
            return None
        return pref.preference_value

    def get_all_preferences(self, affiliate_id: str) -> list[AffiliatePreference]:
        """Return all active preferences for an affiliate."""
        aff_prefs = self.by_affiliate.get(affiliate_id, {})
        results = []
        for pref_id in aff_prefs.values():
            pref = self.preferences.get(pref_id)
            if pref and pref.current_status == "ACTIVE":
                results.append(pref)
        return results

    def delete_preference(
        self,
        affiliate_id: str,
        preference_type: str,
        preference_key: str,
        actor: str = "AFFILIATE",
        now: datetime | None = None,
    ) -> bool:
        """Delete / Deactivate a preference."""
        when = now or utcnow()
        aff_prefs = self.by_affiliate.get(affiliate_id, {})
        key_tuple = (preference_type, preference_key.strip().lower())
        pref_id = aff_prefs.get(key_tuple)
        if not pref_id:
            return False

        pref = self.preferences[pref_id]
        self.preferences[pref_id] = AffiliatePreference(
            id=pref.id,
            affiliate_id=affiliate_id,
            preference_type=pref.preference_type,
            preference_key=pref.preference_key,
            preference_value=pref.preference_value,
            source=pref.source,
            created_at=pref.created_at,
            updated_at=when,
            current_status="DELETED",
        )
        del aff_prefs[key_tuple]

        self.audit_log.append({
            "event_id": str(uuid.uuid4()),
            "affiliate_id": affiliate_id,
            "action": "PREFERENCE_DELETED",
            "preference_type": preference_type,
            "preference_key": key_tuple[1],
            "actor": actor,
            "timestamp": when.isoformat(),
        })
        return True
