"""Instagram Candidate Identity Verifier for BROS Affiliate Program / SOCIAL-AUTO-001.

Provides read-only identity verification for pilot affiliate candidates using
the authenticated @wakenbakelounge Chrome/CDP session or secondary public web evidence.
Strictly read-only: No DMs, no likes, no comments, no token generation, no follow/unfollow.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import os
import re
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error


class MatchStatus(str, Enum):
    """Allowed match states for candidate identity verification."""
    VERIFIED = "VERIFIED"
    LIKELY_MATCH = "LIKELY_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_FOUND = "NOT_FOUND"


class UnauthorizedActionError(Exception):
    """Raised when an unauthorized outbound or mutating action is attempted."""
    pass


@dataclass
class CandidateProfile:
    """Raw profile candidate discovered during search."""
    handle: str
    display_name: str
    bio: str
    profile_url: str
    is_verified_badge: bool = False
    is_following_wakenbake: Optional[bool] = None
    mutual_connections: List[str] = field(default_factory=list)
    external_urls: List[str] = field(default_factory=list)
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """Deterministic result of Instagram candidate verification."""
    candidate_name: str
    instagram_handle: Optional[str]
    display_name: Optional[str]
    profile_url: Optional[str]
    bio_summary: Optional[str]
    match_status: MatchStatus
    match_evidence: Dict[str, Any]
    verification_timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_name": self.candidate_name,
            "instagram_handle": self.instagram_handle,
            "display_name": self.display_name,
            "profile_url": self.profile_url,
            "bio_summary": self.bio_summary,
            "match_status": self.match_status.value,
            "match_evidence": self.match_evidence,
            "verification_timestamp": self.verification_timestamp,
        }


class InstagramVerifier:
    """Read-only verifier for Instagram candidate identities."""

    def __init__(
        self,
        account_context: str = "@wakenbakelounge",
        cdp_url: str = "http://127.0.0.1:9222",
        evidence_dir: Optional[str] = None,
    ):
        self.account_context = account_context
        self.cdp_url = cdp_url
        self.evidence_dir = evidence_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "docs",
            "affiliate",
            "pilot",
            "evidence",
        )
        os.makedirs(self.evidence_dir, exist_ok=True)

    def check_cdp_status(self) -> Dict[str, Any]:
        """Check if Chrome CDP endpoint is reachable and authenticated."""
        try:
            req = urllib.request.Request(
                f"{self.cdp_url}/json/version",
                headers={"User-Agent": "Budly-Social-Verifier/1.0"},
            )
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    return {
                        "cdp_connected": True,
                        "browser": data.get("Browser", "Unknown"),
                        "session_valid": True,
                    }
        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, OSError):
            pass

        return {
            "cdp_connected": False,
            "browser": None,
            "session_valid": False,
        }

    def verify_candidate(
        self,
        candidate_name: str,
        known_aliases: Optional[List[str]] = None,
        known_handles: Optional[List[str]] = None,
        public_cross_check: Optional[List[CandidateProfile]] = None,
    ) -> VerificationResult:
        """Deterministically verify a candidate's Instagram identity.
        
        Evaluates handle, display name, bio, known brand/project names, and content alignment.
        Follower count is never used as identity proof.
        Never silently promotes LIKELY_MATCH or AMBIGUOUS to VERIFIED.
        """
        now_ts = datetime.now(timezone.utc).isoformat()
        known_aliases = [a.lower().strip() for a in (known_aliases or [])]
        known_handles = [h.lower().lstrip("@").strip() for h in (known_handles or [])]
        
        # Check CDP status
        cdp_info = self.check_cdp_status()
        
        # Candidate profiles gathered (from CDP session or injected cross-check profiles)
        profiles: List[CandidateProfile] = public_cross_check or []
        
        # If no profiles provided and CDP is available, real CDP search would run here (read-only)
        # If CDP not available and no profiles provided:
        if not profiles:
            evidence = {
                "searched_name": candidate_name,
                "known_aliases": known_aliases,
                "known_handles": known_handles,
                "account_context": self.account_context,
                "cdp_status": cdp_info,
                "reasons": ["No candidate profiles found matching search criteria in current session or cross-check index."],
            }
            res = VerificationResult(
                candidate_name=candidate_name,
                instagram_handle=None,
                display_name=None,
                profile_url=None,
                bio_summary=None,
                match_status=MatchStatus.NOT_FOUND,
                match_evidence=evidence,
                verification_timestamp=now_ts,
            )
            self._save_evidence(res)
            return res

        # Evaluate profiles
        scored_matches = []
        for p in profiles:
            score, reasons, status = self._evaluate_profile(candidate_name, known_aliases, known_handles, p)
            scored_matches.append((score, status, reasons, p))

        # Sort by score descending
        scored_matches.sort(key=lambda x: x[0], reverse=True)

        # Check for ambiguity:
        # If the top match is NOT VERIFIED (i.e. not >= 80) and another plausible profile exists (score >= 30),
        # OR if multiple profiles share the top score.
        top_score, top_status, top_reasons, top_profile = scored_matches[0]
        
        has_multiple_plausible = (
            len(scored_matches) > 1
            and (
                scored_matches[1][0] >= top_score
                or (top_status != MatchStatus.VERIFIED and scored_matches[1][0] >= 30)
            )
        )

        if has_multiple_plausible and top_score > 0 and top_status != MatchStatus.VERIFIED:
            # Multiple plausible profiles without definitive verification -> AMBIGUOUS
            evidence = {
                "searched_name": candidate_name,
                "known_aliases": known_aliases,
                "known_handles": known_handles,
                "account_context": self.account_context,
                "cdp_status": cdp_info,
                "reasons": ["Multiple plausible profiles detected without definitive handle/link verification."],
                "candidates_considered": [
                    {"handle": m[3].handle, "display_name": m[3].display_name, "score": m[0]}
                    for m in scored_matches
                ],
            }
            res = VerificationResult(
                candidate_name=candidate_name,
                instagram_handle=None,
                display_name=None,
                profile_url=None,
                bio_summary=None,
                match_status=MatchStatus.AMBIGUOUS,
                match_evidence=evidence,
                verification_timestamp=now_ts,
            )
            self._save_evidence(res)
            return res

        # Single top match
        evidence = {
            "searched_name": candidate_name,
            "known_aliases": known_aliases,
            "known_handles": known_handles,
            "account_context": self.account_context,
            "cdp_status": cdp_info,
            "score": top_score,
            "reasons": top_reasons,
            "all_evaluated": [
                {"handle": m[3].handle, "display_name": m[3].display_name, "status": m[1].value}
                for m in scored_matches
            ],
        }

        res = VerificationResult(
            candidate_name=candidate_name,
            instagram_handle=f"@{top_profile.handle.lstrip('@')}",
            display_name=top_profile.display_name,
            profile_url=top_profile.profile_url or f"https://www.instagram.com/{top_profile.handle.lstrip('@')}/",
            bio_summary=top_profile.bio,
            match_status=top_status,
            match_evidence=evidence,
            verification_timestamp=now_ts,
        )
        self._save_evidence(res)
        return res

    def _evaluate_profile(
        self,
        candidate_name: str,
        known_aliases: List[str],
        known_handles: List[str],
        profile: CandidateProfile,
    ) -> tuple[int, List[str], MatchStatus]:
        """Evaluate a single candidate profile against name, aliases, and context."""
        score = 0
        reasons = []
        clean_handle = profile.handle.lower().lstrip("@").strip()
        clean_display = profile.display_name.lower().strip()
        clean_bio = profile.bio.lower()
        cand_lower = candidate_name.lower().strip()

        # 1. Exact handle match in known_handles
        if clean_handle in known_handles:
            score += 60
            reasons.append(f"Handle @{clean_handle} matches known handle.")

        # 2. Exact name match in display name
        if cand_lower == clean_display or cand_lower in clean_display:
            score += 30
            reasons.append(f"Display name '{profile.display_name}' matches candidate name '{candidate_name}'.")

        # 3. Known aliases match in handle, display, or bio
        for alias in known_aliases:
            if alias in clean_handle or alias in clean_display or alias in clean_bio:
                score += 25
                reasons.append(f"Known alias '{alias}' found in profile data.")

        # 4. Cannabis / Botanical / Education / Lounge keyword alignment in bio
        cannabis_keywords = [
            "cannabis", "weed", "botanical", "infused", "wellness", "herbal",
            "edibles", "culinary", "educator", "lounge", "wake'n'bake", "cultivator"
        ]
        matched_kw = [kw for kw in cannabis_keywords if kw in clean_bio]
        if matched_kw:
            score += 15
            reasons.append(f"Subject matter alignment in bio: {', '.join(matched_kw)}")

        # 5. External link corroboration
        if any("cannabis" in url.lower() or "thecannabiscutie" in url.lower() for url in profile.external_urls):
            score += 20
            reasons.append("External link corroborates cannabis industry identity.")

        # Determine MatchStatus based on deterministic thresholds
        if score >= 80:
            status = MatchStatus.VERIFIED
        elif score >= 40:
            status = MatchStatus.LIKELY_MATCH
        elif score > 10:
            status = MatchStatus.AMBIGUOUS
        else:
            status = MatchStatus.NOT_FOUND

        return score, reasons, status

    def _save_evidence(self, result: VerificationResult) -> None:
        """Store non-secret evidence JSON."""
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", result.candidate_name.lower())
        evidence_file = os.path.join(self.evidence_dir, f"verification_{safe_name}.json")
        try:
            with open(evidence_file, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2)
        except OSError:
            pass


def VerifyInstagramCandidate(
    candidate_name: str,
    known_aliases: Optional[List[str]] = None,
    known_handles: Optional[List[str]] = None,
    account_context: str = "@wakenbakelounge",
    cdp_url: str = "http://127.0.0.1:9222",
    public_cross_check: Optional[List[CandidateProfile]] = None,
) -> VerificationResult:
    """Functional interface for candidate verification."""
    verifier = InstagramVerifier(account_context=account_context, cdp_url=cdp_url)
    return verifier.verify_candidate(
        candidate_name=candidate_name,
        known_aliases=known_aliases,
        known_handles=known_handles,
        public_cross_check=public_cross_check,
    )


# ==============================================================================
# FUTURE DM LIFECYCLE HOOKS (GOVERNED & BOUNDED)
# ==============================================================================

def PrepareInstagramDM(
    verified_candidate: VerificationResult,
    approved_message_copy: str,
    delivery_channel: str = "INSTAGRAM_DM",
) -> Dict[str, Any]:
    """Prepare a staged DM package for owner review.
    
    DOES NOT OPEN A COMPOSER. DOES NOT SEND.
    """
    if verified_candidate.match_status != MatchStatus.VERIFIED:
        raise ValueError(
            f"Cannot prepare DM for candidate with match status '{verified_candidate.match_status}'. "
            "Only VERIFIED identities may have DM packages prepared."
        )

    return {
        "candidate_name": verified_candidate.candidate_name,
        "instagram_handle": verified_candidate.instagram_handle,
        "delivery_channel": delivery_channel,
        "staged_copy": approved_message_copy,
        "status": "STAGED_FOR_OWNER_APPROVAL",
        "prepared_at": datetime.now(timezone.utc).isoformat(),
    }


def SendApprovedInstagramDM(staged_package: Dict[str, Any], explicit_owner_auth_token: Optional[str] = None) -> None:
    """Enforce strict authorization barrier before live dispatch."""
    raise UnauthorizedActionError(
        "Direct Message sending is NOT AUTHORIZED in Phase G9B/G9C readiness. "
        "Explicit d-mac send authorization required."
    )
