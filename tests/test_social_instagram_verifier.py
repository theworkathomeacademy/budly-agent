"""Test Suite for SOCIAL-AUTO-001 Instagram Candidate Identity Verifier."""

import pytest
from src.budly_runtime.social.instagram_verifier import (
    CandidateProfile,
    InstagramVerifier,
    MatchStatus,
    PrepareInstagramDM,
    SendApprovedInstagramDM,
    UnauthorizedActionError,
    VerificationResult,
    VerifyInstagramCandidate,
)


def test_verifier_cdp_status_unreachable():
    """Verify CDP check gracefully handles unreachable endpoint."""
    verifier = InstagramVerifier(cdp_url="http://127.0.0.1:9999")
    status = verifier.check_cdp_status()
    assert status["cdp_connected"] is False
    assert status["session_valid"] is False


def test_verify_candidate_tammy_pettigrew_verified():
    """Verify Tammy Pettigrew is deterministically VERIFIED when handle and bio match."""
    profile = CandidateProfile(
        handle="thecannabiscutie",
        display_name="Tammy Pettigrew | Cannabis Educator",
        bio="Teaching the science, history, and wellness of cannabis. The Cannabis Cutie™.",
        profile_url="https://www.instagram.com/thecannabiscutie/",
        external_urls=["https://thecannabiscutie.com"],
    )

    result = VerifyInstagramCandidate(
        candidate_name="Tammy Pettigrew",
        known_aliases=["The Cannabis Cutie", "thecannabiscutie"],
        known_handles=["thecannabiscutie"],
        public_cross_check=[profile],
    )

    assert isinstance(result, VerificationResult)
    assert result.match_status == MatchStatus.VERIFIED
    assert result.instagram_handle == "@thecannabiscutie"
    assert result.display_name == "Tammy Pettigrew | Cannabis Educator"
    assert "cannabis" in result.bio_summary.lower()
    assert result.match_evidence["score"] >= 80


def test_verify_candidate_likely_match_not_promoted_to_verified():
    """Verify LIKELY_MATCH is not promoted to VERIFIED without corroborating handle/link."""
    profile = CandidateProfile(
        handle="avi_rossum_official",
        display_name="Avi Rossum",
        bio="Community host and event advocate.",
        profile_url="https://www.instagram.com/avi_rossum_official/",
    )

    result = VerifyInstagramCandidate(
        candidate_name="Avi Rossum",
        known_aliases=["Avi"],
        known_handles=["avi.babyyyy"],  # Different from profile handle
        public_cross_check=[profile],
    )

    assert result.match_status == MatchStatus.LIKELY_MATCH
    assert result.instagram_handle == "@avi_rossum_official"


def test_verify_candidate_ambiguous_multiple_profiles():
    """Verify multiple profiles with similar scores resolve to AMBIGUOUS."""
    p1 = CandidateProfile(
        handle="kathryn_celestre_1",
        display_name="Kathryn Celestre",
        bio="Wellness enthusiast and lifestyle creator.",
        profile_url="https://www.instagram.com/kathryn_celestre_1/",
    )
    p2 = CandidateProfile(
        handle="kathryn_celestre_model",
        display_name="Kathryn Celestre",
        bio="Fashion and lifestyle.",
        profile_url="https://www.instagram.com/kathryn_celestre_model/",
    )

    result = VerifyInstagramCandidate(
        candidate_name="Kathryn Celestre",
        known_aliases=["Kathryn"],
        known_handles=[],
        public_cross_check=[p1, p2],
    )

    assert result.match_status == MatchStatus.AMBIGUOUS
    assert result.instagram_handle is None
    assert "candidates_considered" in result.match_evidence


def test_verify_candidate_not_found():
    """Verify missing candidate returns NOT_FOUND."""
    result = VerifyInstagramCandidate(
        candidate_name="Sanzidah",
        known_aliases=[],
        known_handles=[],
        public_cross_check=[],
    )

    assert result.match_status == MatchStatus.NOT_FOUND
    assert result.instagram_handle is None


def test_prepare_dm_rejects_unverified_candidate():
    """Verify PrepareInstagramDM raises error if candidate is not VERIFIED."""
    unverified_res = VerificationResult(
        candidate_name="Saleema Mansur",
        instagram_handle="@saleema",
        display_name="Saleema",
        profile_url="https://www.instagram.com/saleema/",
        bio_summary="Food & wellness",
        match_status=MatchStatus.LIKELY_MATCH,
        match_evidence={},
        verification_timestamp="2026-10-03T12:00:00Z",
    )

    with pytest.raises(ValueError, match="Only VERIFIED identities"):
        PrepareInstagramDM(unverified_res, "Hello Saleema!")


def test_prepare_dm_succeeds_for_verified_candidate():
    """Verify PrepareInstagramDM returns staged package without sending."""
    verified_res = VerificationResult(
        candidate_name="Tammy Pettigrew",
        instagram_handle="@thecannabiscutie",
        display_name="Tammy Pettigrew",
        profile_url="https://www.instagram.com/thecannabiscutie/",
        bio_summary="Cannabis Educator",
        match_status=MatchStatus.VERIFIED,
        match_evidence={},
        verification_timestamp="2026-10-03T12:00:00Z",
    )

    staged = PrepareInstagramDM(verified_res, "Hi Tammy, d-mac approved outreach.")
    assert staged["status"] == "STAGED_FOR_OWNER_APPROVAL"
    assert staged["instagram_handle"] == "@thecannabiscutie"
    assert staged["staged_copy"] == "Hi Tammy, d-mac approved outreach."


def test_send_approved_dm_hard_blocker():
    """Verify SendApprovedInstagramDM raises UnauthorizedActionError."""
    with pytest.raises(UnauthorizedActionError, match="Direct Message sending is NOT AUTHORIZED"):
        SendApprovedInstagramDM({"candidate": "Tammy"})
