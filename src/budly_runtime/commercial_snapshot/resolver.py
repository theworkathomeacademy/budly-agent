"""Deterministic Entity & Alias Resolver (CCS-001 / CCS-003).

Performs exact and high-confidence alias resolution according to approved authority rules.
Strictly isolates Community Memberships from Legends NFT Memberships.
Triggers deterministic clarification when customer input is ambiguous rather than guessing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .enrichment import get_all_approved_aliases

# Mandatory explicit entity alias mappings (strictly governed)
MANDATORY_CANONICAL_MAPPINGS: dict[str, str] = {
    "lounge pass": "wnb:community:lounge-pass",
    "wake'n'bake lounge pass": "wnb:community:lounge-pass",
    "free pass": "wnb:community:lounge-pass",
    "free community membership": "wnb:community:lounge-pass",
    
    "lounge member": "wnb:community:lounge-member",
    "wake'n'bake lounge member": "wnb:community:lounge-member",
    "lounge membership": "wnb:community:lounge-member",
    "monthly lounge member": "wnb:community:lounge-member",
    
    "lounge elite": "wnb:community:lounge-elite",
    "wake'n'bake lounge elite": "wnb:community:lounge-elite",
    "elite member": "wnb:community:lounge-elite",
    "vip lounge membership": "wnb:community:lounge-elite",
    
    "is cannabis right for me": "ccc:service:is-cannabis-right-for-me",
    "is cannabis right for me?": "ccc:service:is-cannabis-right-for-me",
    "cannabis consultation": "ccc:service:is-cannabis-right-for-me",
    "1-on-1 consultation": "ccc:service:is-cannabis-right-for-me",
    "consultation with budly": "ccc:service:is-cannabis-right-for-me",
    "book a consultation": "ccc:service:is-cannabis-right-for-me",
    
    "torque": "wnb:nft:torque",
    "torque nft": "wnb:nft:torque",
    "torque nft membership": "wnb:nft:torque",
    "torque legend": "wnb:nft:torque",
    "torque bronze": "wnb:nft:torque:bronze",
    "torque copper": "wnb:nft:torque:copper",
    "torque titanium": "wnb:nft:torque:titanium",
    "torque platinum": "wnb:nft:torque:platinum",

    "infused basics": "ccc:book:infused-basics",
    "infused basics book": "ccc:book:infused-basics",
    "beginner guide to infuse everything edible": "ccc:book:infused-basics",
    
    "culinary cannabis": "ccc:course:culinary-cannabis",
    "culinary cannabis course": "ccc:course:culinary-cannabis",
    "culinary cannabis class": "ccc:course:culinary-cannabis",
    
    "grow cannabis at home": "ccc:course:grow-cannabis-home",
    "grow cannabis @ home": "ccc:course:grow-cannabis-home",
    "grow cannabis home": "ccc:course:grow-cannabis-home",
    "growing class": "ccc:course:grow-cannabis-home",
    
    "cook and grow with me": "ccc:course:grow-cook-with-me",
    "cook & grow with me": "ccc:course:grow-cook-with-me",
    "grow cook with me": "ccc:course:grow-cook-with-me",
}

# Ambiguous phrases that require clarification rather than semantic guessing
AMBIGUOUS_CLARIFICATIONS: dict[str, tuple[str, list[str]]] = {
    "membership": (
        "We offer two distinct types of memberships: upcoming Wake'n'Bake Community Memberships (Lounge Pass, Lounge Member, Lounge Elite) and Wake'n'Bake Legends NFT collectible passes. Which one would you like to explore?",
        ["wnb:community:lounge-pass", "wnb:community:lounge-member", "wnb:community:lounge-elite", "wnb:nft:torque"],
    ),
    "classes": (
        "We offer two structured masterclasses: Culinary Cannabis ($1,000) and Grow Cannabis @ Home ($1,500), or a Cook & Grow With Me dual bundle ($2,500). Which focus area are you interested in?",
        ["ccc:course:culinary-cannabis", "ccc:course:grow-cannabis-home", "ccc:course:grow-cook-with-me"],
    ),
    "courses": (
        "We offer two structured masterclasses: Culinary Cannabis ($1,000) and Grow Cannabis @ Home ($1,500), or a Cook & Grow With Me dual bundle ($2,500). Which focus area are you interested in?",
        ["ccc:course:culinary-cannabis", "ccc:course:grow-cannabis-home", "ccc:course:grow-cook-with-me"],
    ),
    "payment plan": (
        "We offer 4-month installment payment plans for our courses (Culinary Cannabis at $300/mo, Grow Cannabis @ Home at $425/mo, and Cook & Grow With Me at $675/mo). Which course are you considering?",
        [
            "ccc:course:culinary-cannabis:payment-plan",
            "ccc:course:grow-cannabis-home:payment-plan",
            "ccc:course:grow-cook-with-me:payment-plan",
        ],
    ),
    "payment plans": (
        "We offer 4-month installment payment plans for our courses (Culinary Cannabis at $300/mo, Grow Cannabis @ Home at $425/mo, and Cook & Grow With Me at $675/mo). Which course are you considering?",
        [
            "ccc:course:culinary-cannabis:payment-plan",
            "ccc:course:grow-cannabis-home:payment-plan",
            "ccc:course:grow-cook-with-me:payment-plan",
        ],
    ),
}


EXCLUDED_COMMUNITY_CANONICAL_IDS: frozenset[str] = frozenset({
    "wnb:community:lounge-pass",
    "wnb:community:lounge-member",
    "wnb:community:lounge-elite",
})


@dataclass(frozen=True)
class EntityResolutionResult:
    status: str  # EXACT_MATCH, AMBIGUOUS, NO_MATCH
    canonical_id: str | None
    confidence: float
    clarification_prompt: str | None = None
    candidates: tuple[str, ...] = ()


class DeterministicEntityResolver:
    """Resolves customer text or entity keys to canonical commercial IDs with CCS-006 visibility enforcement."""

    def __init__(
        self,
        public_only: bool = True,
        excluded_ids: set[str] | frozenset[str] | None = None,
    ) -> None:
        self.public_only = public_only
        self.excluded_ids = frozenset(excluded_ids) if excluded_ids is not None else EXCLUDED_COMMUNITY_CANONICAL_IDS
        self._aliases = dict(MANDATORY_CANONICAL_MAPPINGS)
        self._aliases.update(get_all_approved_aliases())

    def resolve(self, text: str) -> EntityResolutionResult:
        """Resolve customer text deterministically. Fails closed on non-public records in public mode."""
        cleaned = self._clean(text)
        
        # 1. Exact Canonical ID match
        if cleaned.startswith("ccc:") or cleaned.startswith("wnb:"):
            if self.public_only and cleaned in self.excluded_ids:
                return EntityResolutionResult(
                    status="NO_MATCH",
                    canonical_id=None,
                    confidence=0.0,
                )
            return EntityResolutionResult(
                status="EXACT_MATCH",
                canonical_id=cleaned,
                confidence=1.0,
            )

        # 2. Exact alias match
        if cleaned in self._aliases:
            canonical_id = self._aliases[cleaned]
            if self.public_only and canonical_id in self.excluded_ids:
                return EntityResolutionResult(
                    status="NO_MATCH",
                    canonical_id=None,
                    confidence=0.0,
                )
            return EntityResolutionResult(
                status="EXACT_MATCH",
                canonical_id=canonical_id,
                confidence=1.0,
            )

        # 3. Check for specific known sub-patterns (e.g. "what is infused basics", "what is torque")
        for alias, cid in self._aliases.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", cleaned):
                # Ensure Community memberships NEVER resolve to Legends
                if "community" in cid and "nft" in cleaned:
                    continue
                if self.public_only and cid in self.excluded_ids:
                    return EntityResolutionResult(
                        status="NO_MATCH",
                        canonical_id=None,
                        confidence=0.0,
                    )
                return EntityResolutionResult(
                    status="EXACT_MATCH",
                    canonical_id=cid,
                    confidence=0.95,
                )

        # 4. Check for ambiguous generic queries
        for ambig_key, (clarification, candidates) in AMBIGUOUS_CLARIFICATIONS.items():
            if re.search(r"\b" + re.escape(ambig_key) + r"\b", cleaned):
                if self.public_only:
                    # Filter candidates to only public entities
                    filtered_candidates = [c for c in candidates if c not in self.excluded_ids]
                    if not filtered_candidates:
                        return EntityResolutionResult(status="NO_MATCH", canonical_id=None, confidence=0.0)
                    if len(filtered_candidates) == 1:
                        return EntityResolutionResult(status="EXACT_MATCH", canonical_id=filtered_candidates[0], confidence=0.85)
                    return EntityResolutionResult(
                        status="AMBIGUOUS",
                        canonical_id=None,
                        confidence=0.5,
                        clarification_prompt=clarification,
                        candidates=tuple(filtered_candidates),
                    )
                return EntityResolutionResult(
                    status="AMBIGUOUS",
                    canonical_id=None,
                    confidence=0.5,
                    clarification_prompt=clarification,
                    candidates=tuple(candidates),
                )

        return EntityResolutionResult(
            status="NO_MATCH",
            canonical_id=None,
            confidence=0.0,
        )

    @staticmethod
    def _clean(text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r"[?!.,;:'\"]+", "", t)
        t = re.sub(r"\s+", " ", t)
        return t
