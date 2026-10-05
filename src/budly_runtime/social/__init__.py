"""Social automation and verification package for Budly / Wake'n'Bake Lounge."""

from .instagram_verifier import (
    MatchStatus,
    VerificationResult,
    VerifyInstagramCandidate,
    InstagramVerifier,
    CandidateProfile,
    PrepareInstagramDM,
    SendApprovedInstagramDM,
)

__all__ = [
    "MatchStatus",
    "VerificationResult",
    "VerifyInstagramCandidate",
    "InstagramVerifier",
    "CandidateProfile",
    "PrepareInstagramDM",
    "SendApprovedInstagramDM",
]
