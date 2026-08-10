"""Zero-cost, policy-first MVP for the Wake'n'Bake Lounge sales agent."""

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
DEFAULT_DB = ROOT / "data" / "sales.db"
APPLICATION_VERSION = "1.7.0"
SCHEMA_VERSION = "1.5.0"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
RISK_PATTERNS = {
    "medical": ("diagnose", "treat my", "cure", "dosage", "dose", "replace my medication"),
    "adverse_event": ("adverse event", "bad reaction", "made me sick", "hospital"),
    "legal_or_eligibility": ("is it legal", "legal in", "under 18", "under 21", "fake id"),
    "payment_or_refund_dispute": ("chargeback", "refund dispute", "unauthorized charge", "stolen card"),
    "commercial_negotiation": ("wholesale", "custom pricing", "exclusive deal", "press inquiry"),
}


@dataclass(frozen=True)
class Discovery:
    shopping_goal: str
    experience_level: str
    preferred_format: str
    budget_range: str
    purchase_timeline: str

    def validate(self) -> None:
        if not self.shopping_goal.strip():
            raise ValueError("shopping_goal is required")
        if self.experience_level not in {"new", "some_experience", "experienced", "unknown"}:
            raise ValueError("experience_level is invalid")


@dataclass(frozen=True)
class OpportunitySignals:
    need_fit: int
    purchase_intent: int
    timeline: int
    engagement: int

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if not isinstance(value, int) or not 0 <= value <= 5:
                raise ValueError(f"{name} must be an integer from 0 to 5")


class SalesAgent:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("SALES_DB_PATH") or DEFAULT_DB)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = self._load_json(ROOT / "config" / "sales.json")
        self.catalog = self._load_json(ROOT / "config" / "products.json")
        self.product_facts = self._load_json(ROOT / "config" / "product_facts.json")
        self.journeys = self._load_json(ROOT / "config" / "sales_journeys.json")
        self.policies = self._load_json(ROOT / "config" / "policies.json")
        self.rules = self._load_json(ROOT / "config" / "bros_v1_5.json")
        self._validate_rules()
        self.weights = self.rules["qualification"]["weights"]
        self._enrich_catalog()
        self.system_prompt = (ROOT / "prompts" / "sales_system.txt").read_text(encoding="utf-8")
        self._initialize_database()

    def _enrich_catalog(self) -> None:
        facts = self.product_facts.get("products", {})
        profiles = self.product_facts.get("profiles", {})
        for product in self.catalog.get("products", []):
            product_fact = facts.get(product.get("id"), {})
            profile = profiles.get(product_fact.get("profile"), {})
            product.update(profile)
            product.update(product_fact)
            product["price_display"] = self._price_display(product)

    @staticmethod
    def _price_display(product: dict[str, Any]) -> str | None:
        low, high = product.get("price_min"), product.get("price_max")
        if low is None:
            return None
        if high is not None and high != low:
            return f"${low / 100:,.2f}-${high / 100:,.2f}"
        return f"${low / 100:,.2f}"

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def _validate_rules(self) -> None:
        qualification = self.rules.get("qualification", {})
        weights = qualification.get("weights", {})
        required = {"need_fit", "purchase_intent", "timeline", "engagement"}
        if self.rules.get("status") != "active" or set(weights) != required or sum(weights.values()) != 100:
            raise ValueError("Active BROS qualification rules are invalid")
        thresholds = qualification.get("thresholds", {})
        if not 0 <= thresholds.get("nurture", -1) < thresholds.get("qualified", -1) <= 100:
            raise ValueError("BROS qualification thresholds are invalid")

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
                CREATE TABLE IF NOT EXISTS customers (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    score INTEGER,
                    discovery_json TEXT NOT NULL DEFAULT '{}',
                    recommended_product_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS escalations (
                    id TEXT PRIMARY KEY,
                    customer_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decision_evidence (
                    id TEXT PRIMARY KEY,
                    decision_type TEXT NOT NULL,
                    customer_id TEXT,
                    session_id TEXT,
                    conversation_id TEXT,
                    journey TEXT,
                    objective TEXT NOT NULL,
                    inputs_json TEXT NOT NULL,
                    rule_version TEXT NOT NULL,
                    eligible_products_json TEXT NOT NULL,
                    excluded_products_json TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    selected_product_id TEXT,
                    confidence TEXT,
                    escalation_id TEXT,
                    resulting_action TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS decision_customer_time
                    ON decision_evidence(customer_id, created_at);
                CREATE INDEX IF NOT EXISTS decision_outcome_time
                    ON decision_evidence(outcome, created_at);
                CREATE TABLE IF NOT EXISTS active_configurations (
                    config_type TEXT PRIMARY KEY,
                    version TEXT NOT NULL,
                    activated_at TEXT NOT NULL
                );
                """
            )
            for config_type in ("qualification", "recommendation", "catalog", "journeys", "escalation", "consent", "retention"):
                version = self.rules[config_type]["version"]
                db.execute(
                    "INSERT OR IGNORE INTO active_configurations(config_type,version,activated_at) VALUES (?,?,?)",
                    (config_type, version, self._now()),
                )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def normalize_email(email: str) -> str:
        value = email.strip().lower()
        if not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address")
        return value

    def _audit(self, customer_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), customer_id, event_type, json.dumps(payload, sort_keys=True), self._now()),
            )

    def _record_decision(
        self,
        decision_type: str,
        customer_id: str,
        *,
        objective: str,
        inputs: dict[str, Any],
        rule_version: str,
        outcome: str,
        journey: str = "",
        eligible_products: list[str] | None = None,
        excluded_products: list[dict[str, str]] | None = None,
        selected_product_id: str | None = None,
        confidence: str | None = None,
        escalation_id: str | None = None,
        resulting_action: str,
        session_id: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        decision_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                """INSERT INTO decision_evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    decision_id, decision_type, customer_id, session_id, conversation_id, journey,
                    objective[:1000], json.dumps(inputs, sort_keys=True),
                    rule_version, json.dumps(eligible_products or [], sort_keys=True),
                    json.dumps(excluded_products or [], sort_keys=True), outcome,
                    selected_product_id, confidence, escalation_id, resulting_action, self._now(),
                ),
            )
        self._audit(customer_id, f"decision.{decision_type}", {
            "decision_id": decision_id,
            "outcome": outcome,
            "rule_version": rule_version,
            "resulting_action": resulting_action,
        })
        return decision_id

    def decision_evidence(self, customer_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM decision_evidence WHERE customer_id=? ORDER BY created_at,id",
                (customer_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def diagnostics(self) -> dict[str, Any]:
        with self._connect() as db:
            configs = db.execute(
                "SELECT config_type,version FROM active_configurations ORDER BY config_type"
            ).fetchall()
        return {
            "application_version": APPLICATION_VERSION,
            "schema_version": SCHEMA_VERSION,
            "rule_versions": {row["config_type"]: row["version"] for row in configs},
        }

    def intake(self, *, name: str, email: str, source: str = "direct") -> dict[str, Any]:
        if not name.strip():
            raise ValueError("Name is required")
        email = self.normalize_email(email)
        now = self._now()
        with self._connect() as db:
            existing = db.execute("SELECT id FROM customers WHERE email=?", (email,)).fetchone()
            if existing:
                customer_id = existing["id"]
                db.execute(
                    "UPDATE customers SET name=?, source=?, updated_at=? WHERE id=?",
                    (name.strip(), source.strip() or "direct", now, customer_id),
                )
                event = "customer_updated"
            else:
                customer_id = str(uuid.uuid4())
                db.execute(
                    "INSERT INTO customers (id,email,name,source,stage,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                    (customer_id, email, name.strip(), source.strip() or "direct", "new", now, now),
                )
                event = "customer_created"
        self._audit(customer_id, event, {"email": email, "source": source})
        return self.get_customer(customer_id)

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        if row is None:
            raise KeyError("Customer not found")
        return dict(row)

    def record_discovery(self, customer_id: str, discovery: Discovery) -> dict[str, Any]:
        discovery.validate()
        with self._connect() as db:
            changed = db.execute(
                "UPDATE customers SET discovery_json=?, stage='discovery', updated_at=? WHERE id=?",
                (json.dumps(asdict(discovery), sort_keys=True), self._now(), customer_id),
            ).rowcount
        if not changed:
            raise KeyError("Customer not found")
        self._audit(customer_id, "discovery_completed", asdict(discovery))
        return self.get_customer(customer_id)

    def qualify(self, customer_id: str, signals: OpportunitySignals) -> dict[str, Any]:
        signals.validate()
        values = asdict(signals)
        score = round(sum((values[key] / 5) * weight for key, weight in self.weights.items()))
        thresholds = self.rules["qualification"]["thresholds"]
        stage = (
            "qualified" if score >= thresholds["qualified"]
            else "nurture" if score >= thresholds["nurture"]
            else "low_intent"
        )
        with self._connect() as db:
            changed = db.execute(
                "UPDATE customers SET score=?, stage=?, updated_at=? WHERE id=?",
                (score, stage, self._now(), customer_id),
            ).rowcount
        if not changed:
            raise KeyError("Customer not found")
        customer = self.get_customer(customer_id)
        discovery = json.loads(customer["discovery_json"] or "{}")
        self._record_decision(
            "qualification", customer_id,
            objective=discovery.get("shopping_goal", ""),
            inputs={"signals": values, "weights": self.weights},
            rule_version=self.rules["qualification"]["version"],
            outcome=stage,
            resulting_action="advance_to_recommendation" if stage == "qualified" else "continue_education",
        )
        self._audit(customer_id, "opportunity_scored", {
            "signals": values, "score": score, "stage": stage,
            "rule_version": self.rules["qualification"]["version"],
        })
        return self.get_customer(customer_id)

    @staticmethod
    def risk_category(message: str) -> str | None:
        lowered = message.lower()
        for category, patterns in RISK_PATTERNS.items():
            if any(pattern in lowered for pattern in patterns):
                return category
        return None

    def escalate(self, customer_id: str, category: str, summary: str) -> str:
        escalation_id = str(uuid.uuid4())
        with self._connect() as db:
            db.execute(
                "INSERT INTO escalations VALUES (?, ?, ?, ?, 'open', ?)",
                (escalation_id, customer_id, category, summary[:1000], self._now()),
            )
            db.execute(
                "UPDATE customers SET stage='human_review', updated_at=? WHERE id=?",
                (self._now(), customer_id),
            )
        self._audit(customer_id, "human_escalation_created", {"id": escalation_id, "category": category})
        self._record_decision(
            "escalation", customer_id, objective=summary, inputs={"category": category},
            rule_version=self.rules["escalation"]["version"], outcome="human_review",
            escalation_id=escalation_id, resulting_action="human_handoff",
        )
        return escalation_id

    def recommend(self, customer_id: str) -> dict[str, Any] | None:
        customer = self.get_customer(customer_id)
        discovery = json.loads(customer["discovery_json"] or "{}")
        goal_words = set(re.findall(r"[a-z0-9]+", discovery.get("shopping_goal", "").lower()))
        preferred = discovery.get("preferred_format", "").lower()
        all_products = self.catalog.get("products", [])
        active = [p for p in all_products if p.get("active") is True and p.get("requires_human_sales") is not True]
        excluded = []
        for product in all_products:
            reason = None
            if product.get("active") is not True:
                reason = "inactive_or_not_allowlisted"
            elif product.get("requires_human_sales") is True:
                reason = "human_sales_required"
            if reason:
                excluded.append({"product_id": str(product.get("id", "")), "reason": reason})
        ranked = []
        for product in active:
            tags = {str(tag).lower() for tag in product.get("tags", [])}
            tag_words = set().union(*(set(re.findall(r"[a-z0-9]+", tag)) for tag in tags)) if tags else set()
            score = len(goal_words & tag_words) * 2
            if {"one", "time"}.issubset(goal_words) and product.get("sale_type") == "one_time":
                score += 4
            if "monthly" in goal_words and product.get("sale_type") == "subscription":
                score += 4
            if preferred and preferred in {str(x).lower() for x in product.get("formats", [])}:
                score += 3
            ranked.append((score, str(product.get("id", "")), product))
        minimum = self.rules["recommendation"]["minimum_score"]
        if not ranked or max(item[0] for item in ranked) < minimum:
            self._record_decision(
                "recommendation", customer_id,
                objective=discovery.get("shopping_goal", ""), inputs={"discovery": discovery},
                rule_version=self.rules["recommendation"]["version"], outcome="no_match",
                eligible_products=[str(p["id"]) for p in active], excluded_products=excluded,
                confidence="insufficient", resulting_action="request_clarification_or_human_help",
            )
            self._audit(customer_id, "no_catalog_match", {
                "catalog_size": len(active), "rule_version": self.rules["recommendation"]["version"]
            })
            return None
        winning_score, _, product = max(ranked, key=lambda item: (item[0], item[1]))
        confidence_levels = self.rules["recommendation"]["confidence"]
        confidence = (
            "high" if winning_score >= confidence_levels["high"]
            else "medium" if winning_score >= confidence_levels["medium"]
            else "low"
        )
        with self._connect() as db:
            db.execute(
                "UPDATE customers SET recommended_product_id=?, stage='solution_presented', updated_at=? WHERE id=?",
                (product["id"], self._now(), customer_id),
            )
        self._record_decision(
            "recommendation", customer_id,
            objective=discovery.get("shopping_goal", ""),
            inputs={"discovery": discovery, "winning_score": winning_score},
            rule_version=self.rules["recommendation"]["version"], outcome="recommended",
            eligible_products=[str(p["id"]) for p in active], excluded_products=excluded,
            selected_product_id=str(product["id"]), confidence=confidence,
            resulting_action="present_allowlisted_product",
        )
        self._audit(customer_id, "product_recommended", {
            "product_id": product["id"], "confidence": confidence,
            "rule_version": self.rules["recommendation"]["version"],
        })
        return product

    def select_journey(self, customer_id: str) -> dict[str, Any]:
        """Route discovery into one of five controlled sales journeys."""
        customer = self.get_customer(customer_id)
        discovery = json.loads(customer["discovery_json"] or "{}")
        text = " ".join(str(value) for value in discovery.values()).lower()
        # Wholesale must win over product-format matches because it always needs a person.
        order = ("wholesale", "nft_memberships", "books_courses", "culinary", "consumer_wellness")
        scores: dict[str, int] = {}
        for journey_id in order:
            journey = self.journeys[journey_id]
            scores[journey_id] = sum(1 for signal in journey.get("entry_signals", []) if signal in text)
        winner = max(order, key=lambda journey_id: (scores[journey_id], -order.index(journey_id)))
        if scores[winner] == 0:
            winner = "consumer_wellness"
        result = {"id": winner, **self.journeys[winner]}
        self._audit(customer_id, "sales_journey_selected", {"journey_id": winner, "scores": scores})
        return result

    def recommendation_card(self, customer_id: str) -> dict[str, Any] | None:
        """Return only sales-safe, source-verified fields for presentation."""
        product = self.recommend(customer_id)
        if product is None:
            return None
        journey = self.select_journey(customer_id)
        if product.get("requires_human_sales") or product.get("compliance_status") == "human_sales_required":
            return None
        return {
            "product_id": product["id"],
            "name": product["name"],
            "price": product.get("price_display"),
            "summary": product.get("safe_summary"),
            "factual_features": product.get("factual_features", []),
            "variants": product.get("variants", []),
            "in_stock": product.get("in_stock"),
            "checkout_status": "direct" if product.get("purchasable") else "external_terms_must_be_verified",
            "product_url": product["url"],
            "journey_id": journey["id"],
            "exclusions": product.get("exclusions", []),
        }

    def local_response(self, customer: dict[str, Any], message: str) -> str:
        risk = self.risk_category(message)
        policy_response = self.policy_answer(message)
        if policy_response and risk not in {"adverse_event", "legal_or_eligibility", "payment_or_refund_dispute"}:
            self._audit(customer["id"], "approved_policy_answered", {"message": message[:500]})
            return policy_response
        if risk:
            self.escalate(customer["id"], risk, message)
            return "That needs a qualified team member. I have preserved the context for human review and will not guess."
        if not self.catalog.get("products"):
            return (
                "I can help clarify what you are looking for, but the approved product catalog has not been loaded yet. "
                "Tell me your shopping goal and preferred product format, and I can prepare a human follow-up."
            )
        stage = customer["stage"]
        if stage == "new":
            return "What are you hoping to find, and is this your first time shopping in this product category?"
        if stage == "discovery":
            return "Thanks. I can now compare that with the approved catalog and explain any relevant fit and tradeoffs."
        if stage == "qualified":
            return "You appear ready for a focused recommendation based only on the approved catalog."
        if stage == "nurture":
            return "There is no need to rush. I can share approved educational information or help you return when the timing is better."
        if stage == "low_intent":
            return "I can answer a specific product or policy question without pushing you toward a purchase."
        if stage == "solution_presented":
            return "Would you like the approved product page, a comparison, or time to consider it?"
        return "How can I help with your product decision today?"

    def policy_answer(self, message: str) -> str | None:
        """Answer routine policy questions only from owner-approved policy text."""
        text = message.lower()
        policies = self.policies.get("policies", {})
        support = self.policies.get("support_email", self.settings.get("human_sales_email", ""))
        response_time = self.policies.get("support_response_target", "")
        if any(word in text for word in ("cancel subscription", "cancel my subscription", "subscription cancel")):
            policy = policies["subscriptions"]
            return f"{policy['self_service']} {policy['assisted_cancellation']} {policy['deadline']} {policy['processed_orders']}"
        if "membership" in text and any(word in text for word in ("refund", "cancel", "start", "begin", "discount")):
            policy = policies["nft_memberships"]
            return f"{policy['activation']} {policy['summary']} {policy['usage_rule']}"
        if any(word in text for word in ("damaged", "wrong order", "incorrect order")):
            return policies["damaged_or_incorrect_orders"]["summary"] + f" Contact {support}."
        if any(word in text for word in ("digital refund", "download refund", "ebook refund")):
            return policies["digital_products"]["summary"]
        if "book" in text and any(word in text for word in ("return", "refund")):
            policy = policies["physical_books"]
            return f"{policy['summary']} {policy['return_shipping']}"
        if "course" in text and any(word in text for word in ("return", "refund", "cancel")):
            return policies["courses"]["summary"]
        if any(word in text for word in ("shipping", "ship to", "delivery time")):
            policy = policies["shipping"]
            return f"{policy['summary']} {policy['unsupported_destination']}"
        if "wholesale" in text and any(word in text for word in ("price", "minimum", "shipping", "label", "terms", "custom")):
            policy = policies["wholesale"]
            return f"{policy['summary']} {policy['contact']}"
        if any(word in text for word in ("support response", "hear back", "response time")):
            return f"Support normally responds {response_time}. You can email {support}."
        if any(word in text for word in ("return policy", "refund policy")):
            return (
                "CBD, body-care, and cooking products are final sale. Physical books may be returned within 14 days "
                "if unused and in original condition. Digital products are final sale after delivery or download. "
                f"For damaged or incorrect orders, contact {support} within 7 days of delivery with your order number and photos."
            )
        return None

    def openai_response(self, customer: dict[str, Any], message: str) -> str:
        """Optionally draft wording via Responses API; local workflow remains authoritative."""
        if self.risk_category(message) or not os.getenv("OPENAI_API_KEY"):
            return self.local_response(customer, message)
        context = {
            "customer": {k: customer[k] for k in ("name", "stage", "score", "discovery_json", "recommended_product_id")},
            "catalog": self.catalog,
            "approved_policies": self.policies,
            "settings": self.settings,
        }
        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
            "instructions": self.system_prompt,
            "input": "Authoritative context:\n" + json.dumps(context) + "\nCustomer message:\n" + message,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
            text = body.get("output_text") or "".join(
                part.get("text", "")
                for item in body.get("output", [])
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            )
            if not text.strip():
                raise ValueError("No output text")
            self._audit(customer["id"], "model_response_drafted", {"model": payload["model"]})
            return text.strip()
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
            self._audit(customer["id"], "model_fallback", {"error_type": type(error).__name__})
            return self.local_response(customer, message)

    def select_next_adaptive_question(self, known_attributes: dict[str, Any]) -> dict[str, Any] | None:
        """Select highest information value next question for adaptive discovery."""
        candidates = [
            ("shopping_goal", 10, "What are you shopping for today?"),
            ("experience_level", 8, "What is your experience level with these products?"),
            ("preferred_format", 7, "Do you prefer tinctures, edibles, gummies, or flower?"),
            ("budget_range", 5, "Do you have a target price range in mind?"),
            ("purchase_timeline", 4, "Are you looking to order today or researching for later?"),
        ]
        for attr, priority, question in candidates:
            if not known_attributes.get(attr):
                return {
                    "attribute": attr,
                    "question": question,
                    "information_value": priority / 10.0,
                }
        return None

    def explain_recommendation(self, product: dict[str, Any], discovery: Discovery | dict[str, Any]) -> dict[str, Any]:
        """Build explainable recommendation rationale based on consented customer discovery."""
        goal = discovery.shopping_goal if isinstance(discovery, Discovery) else discovery.get("shopping_goal", "your goals")
        fmt = discovery.preferred_format if isinstance(discovery, Discovery) else discovery.get("preferred_format", "your preferred format")
        return {
            "observation": f"Customer indicated interest in {goal} with preference for {fmt}.",
            "reasoning": f"{product.get('name')} matches the format ({fmt}) and aligns with experience level.",
            "recommendation": product.get("name"),
            "explanation": f"We recommend {product.get('name')} because it satisfies your stated preference for {fmt} and aligns with {goal}.",
            "confirmation_prompt": "Would you like more details or to see alternative options?",
        }

    def canonical_lifecycle_stage(self, customer: dict[str, Any]) -> str:
        """Map customer state to canonical BCAM lifecycle stage."""
        stage = customer.get("stage", "new")
        raw_score = customer.get("score")
        score = raw_score if isinstance(raw_score, (int, float)) else 0
        if stage == "closed_won":
            return "Member"
        elif stage in {"qualified", "decision"}:
            return "Explorer"
        elif score > 80:
            return "Explorer"
        return "Visitor"



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
    print("Budly Sales - zero-cost MVP")
    agent = SalesAgent()
    customer = agent.intake(name=input("Name: "), email=input("Email: "), source=input("Source: ") or "direct")
    discovery = Discovery(
        shopping_goal=input("What are you shopping for? "),
        experience_level=input("Experience (new/some_experience/experienced/unknown): ") or "unknown",
        preferred_format=input("Preferred format: "),
        budget_range=input("Budget range (optional): "),
        purchase_timeline=input("Purchase timeline: "),
    )
    customer = agent.record_discovery(customer["id"], discovery)
    customer = agent.qualify(
        customer["id"],
        OpportunitySignals(
            need_fit=_rating("Need fit"),
            purchase_intent=_rating("Purchase intent"),
            timeline=_rating("Timeline"),
            engagement=_rating("Engagement"),
        ),
    )
    product = agent.recommend(customer["id"])
    customer = agent.get_customer(customer["id"])
    print(f"\nScore: {customer['score']} | Stage: {customer['stage']}")
    print("Recommendation:", product["name"] if product else "No approved catalog match")
    print("Type 'exit' to stop.\n")
    while True:
        message = input("Customer: ").strip()
        if message.lower() in {"exit", "quit"}:
            break
        print("Budly Sales:", agent.openai_response(customer, message), "\n")


if __name__ == "__main__":
    main()
