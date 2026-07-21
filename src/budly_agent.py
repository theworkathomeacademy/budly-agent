"""Dependency-free Phase 1 implementation of Budly Agent #7."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "budly.db"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ESCALATION_PATTERNS = {
    "legal_or_regulatory": ("legal", "lawyer", "regulation", "regulatory", "is this legal"),
    "medical_or_safety": ("medical advice", "diagnose", "dosage", "adverse event", "side effect"),
    "payment_or_commission": ("missing payout", "commission dispute", "payment dispute", "unpaid"),
    "strategic_partnership": ("exclusive partnership", "negotiate terms", "custom commission"),
}


@dataclass(frozen=True)
class Qualification:
    mission_alignment: int
    engagement_quality: int
    consistency: int
    willingness_to_learn: int
    audience_fit: int
    affiliate_experience: int

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or not 0 <= value <= 5:
                raise ValueError(f"{name} must be an integer from 0 to 5")


class BudlyAgent:
    weights = {
        "mission_alignment": 25,
        "engagement_quality": 20,
        "consistency": 15,
        "willingness_to_learn": 15,
        "audience_fit": 15,
        "affiliate_experience": 10,
    }

    def __init__(self, db_path: str | Path | None = None) -> None:
        configured = db_path or os.getenv("BUDLY_DB_PATH") or DEFAULT_DB
        self.db_path = Path(configured)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.system_prompt = (ROOT / "prompts" / "system.txt").read_text(encoding="utf-8")
        self._initialize_database()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS prospects (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    niche TEXT NOT NULL,
                    score INTEGER,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    prospect_id TEXT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS escalations (
                    id TEXT PRIMARY KEY,
                    prospect_id TEXT,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def normalize_email(email: str) -> str:
        normalized = email.strip().lower()
        if not EMAIL_RE.match(normalized):
            raise ValueError("Enter a valid email address")
        return normalized

    def _audit(self, prospect_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), prospect_id, event_type, json.dumps(payload, sort_keys=True), self._now()),
            )

    def intake(self, *, name: str, email: str, source: str, platform: str, niche: str) -> dict[str, Any]:
        clean_email = self.normalize_email(email)
        if not name.strip():
            raise ValueError("Name is required")
        now = self._now()
        with self._connect() as db:
            existing = db.execute("SELECT * FROM prospects WHERE email = ?", (clean_email,)).fetchone()
            if existing:
                db.execute(
                    "UPDATE prospects SET name=?, source=?, platform=?, niche=?, updated_at=? WHERE id=?",
                    (name.strip(), source.strip(), platform.strip(), niche.strip(), now, existing["id"]),
                )
                prospect_id = existing["id"]
                event = "prospect_updated"
            else:
                prospect_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO prospects VALUES (?, ?, ?, ?, ?, ?, NULL, 'new', ?, ?)",
                    (prospect_id, clean_email, name.strip(), source.strip(), platform.strip(), niche.strip(), now, now),
                )
                event = "prospect_created"
        self._audit(prospect_id, event, {"email": clean_email, "source": source})
        return self.get_prospect(prospect_id)

    def get_prospect(self, prospect_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        if row is None:
            raise KeyError("Prospect not found")
        return dict(row)

    def qualify(self, prospect_id: str, qualification: Qualification) -> dict[str, Any]:
        qualification.validate()
        values = asdict(qualification)
        score = round(sum((values[key] / 5) * weight for key, weight in self.weights.items()))
        status = "invite_to_apply" if score >= 70 else "nurture" if score >= 40 else "monitor"
        with self._connect() as db:
            changed = db.execute(
                "UPDATE prospects SET score=?, status=?, updated_at=? WHERE id=?",
                (score, status, self._now(), prospect_id),
            ).rowcount
        if not changed:
            raise KeyError("Prospect not found")
        self._audit(prospect_id, "prospect_qualified", {"factors": values, "score": score, "status": status})
        return self.get_prospect(prospect_id)

    @staticmethod
    def escalation_category(message: str) -> str | None:
        lowered = message.lower()
        for category, phrases in ESCALATION_PATTERNS.items():
            if any(phrase in lowered for phrase in phrases):
                return category
        return None

    def escalate(self, prospect_id: str, category: str, summary: str) -> str:
        escalation_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                "INSERT INTO escalations VALUES (?, ?, ?, ?, 'open', ?)",
                (escalation_id, prospect_id, category, summary[:1000], self._now()),
            )
            db.execute(
                "UPDATE prospects SET status='human_review', updated_at=? WHERE id=?",
                (self._now(), prospect_id),
            )
        self._audit(prospect_id, "human_escalation_created", {"id": escalation_id, "category": category})
        return escalation_id

    def local_response(self, prospect: dict[str, Any], message: str) -> str:
        category = self.escalation_category(message)
        if category:
            self.escalate(prospect["id"], category, message)
            return (
                "That needs a qualified team member. I’ve recorded the context for human review "
                "and won’t guess or make a promise on the brand’s behalf."
            )
        status = prospect["status"]
        if status == "invite_to_apply":
            return (
                f"Thanks, {prospect['name']}. Your focus on {prospect['niche']} appears aligned with "
                "our education-and-community approach. The next step is an affiliate application; "
                "approval and results are never guaranteed."
            )
        if status == "nurture":
            return (
                "There may be a fit, and there’s no need to rush. I recommend learning the mission, "
                "product fundamentals, responsible-promotion guidelines, and how affiliate tracking works first."
            )
        if status == "monitor":
            return (
                "Thanks for your interest. The best next step is to build consistent, authentic engagement "
                "with your community and learn our education-first approach before applying."
            )
        return "I’d like to learn about your audience, primary platform, niche, and what interests you about the mission."

    def openai_response(self, prospect: dict[str, Any], message: str) -> str:
        """Draft a response via the Responses API, retaining local policy authority."""
        category = self.escalation_category(message)
        if category:
            return self.local_response(prospect, message)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return self.local_response(prospect, message)
        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            "instructions": self.system_prompt,
            "input": (
                "Structured prospect context (authoritative):\n"
                + json.dumps({k: prospect[k] for k in ("name", "platform", "niche", "score", "status")})
                + "\nProspect message:\n"
                + message
                + "\nDraft one concise response. Do not alter or contradict the structured status."
            ),
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            text = body.get("output_text")
            if not text:
                chunks = []
                for item in body.get("output", []):
                    for content in item.get("content", []):
                        if content.get("type") == "output_text":
                            chunks.append(content.get("text", ""))
                text = "".join(chunks)
            if not text:
                raise ValueError("Response contained no output text")
            self._audit(prospect["id"], "model_response_drafted", {"model": payload["model"]})
            return text.strip()
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
            self._audit(prospect["id"], "model_fallback", {"error_type": type(error).__name__})
            return self.local_response(prospect, message)


def _rating(label: str) -> int:
    while True:
        try:
            value = int(input(f"{label} (0-5): ").strip())
            if 0 <= value <= 5:
                return value
        except ValueError:
            pass
        print("Enter a whole number from 0 to 5.")


def main() -> None:
    print("Budly Agent #7 - Phase 1 Affiliate Recruiter")
    agent = BudlyAgent()
    prospect = agent.intake(
        name=input("Name: "),
        email=input("Email: "),
        source=input("How did they find us? ") or "direct",
        platform=input("Primary platform: ") or "unknown",
        niche=input("Content niche: ") or "unknown",
    )
    assessment = Qualification(
        mission_alignment=_rating("Mission alignment"),
        engagement_quality=_rating("Engagement quality"),
        consistency=_rating("Consistency"),
        willingness_to_learn=_rating("Willingness to learn"),
        audience_fit=_rating("Audience fit"),
        affiliate_experience=_rating("Affiliate experience"),
    )
    prospect = agent.qualify(prospect["id"], assessment)
    print(f"\nScore: {prospect['score']} | Route: {prospect['status']}")
    print("Type 'exit' to end.\n")
    while True:
        message = input("Prospect: ").strip()
        if message.lower() in {"exit", "quit"}:
            break
        print("Budly:", agent.openai_response(prospect, message), "\n")


if __name__ == "__main__":
    main()
