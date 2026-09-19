"""Integration bridge tests verifying STS-1 connected to the real Ask Budly entry and runtime path."""

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from src.conversation_service import ConversationService
from src.web_app import make_server


class TestSTS1LiveIntegrationBridge(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "live_test_sales.db"
        self.service = ConversationService(self.db_path)
        self.server = make_server(host="127.0.0.1", port=0, db_path=self.db_path)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp_dir.cleanup()

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def test_a_anonymous_purchase_intent(self):
        """TEST A — Anonymous Purchase Intent:
        - attributed Instagram session created
        - Botanical Collection PURCHASE_INTENT recognized
        - qualification becomes QUALIFIED_PURCHASE_READY
        - approved destination returned
        - journey persisted
        - lead_id remains NULL
        - no CRM Lead created
        """
        landing_url = (
            "https://www.wakenbakelounge.com/ask-budly"
            "?source=social"
            "&platform=instagram"
            "&content_id=IG-20260906-0002"
            "&campaign_id=STS-PILOT-001"
            "&cta_id=CTA-ASK-BUDLY-001"
            "&product_or_topic=BOTANICAL_COLLECTION"
        )
        intake_res = self._post("/api/intake", {"landing_input": landing_url})
        session_id = intake_res["session_id"]
        journey_id = intake_res["journey_id"]

        # User expresses purchase intent while remaining anonymous
        turn_res = self._post("/api/turn", {
            "session_id": session_id,
            "message": "I want to buy the cannabis botanical coloring collection volume 1",
        })

        self.assertEqual(turn_res["intent"], "PURCHASE_INTENT")
        self.assertEqual(turn_res["product_or_topic"], "BOTANICAL_COLLECTION")
        self.assertEqual(turn_res["qualification_state"], "QUALIFIED_PURCHASE_READY")
        self.assertEqual(
            turn_res["recommended_destination"],
            "https://cccultivate.com/product/wakenbake-lounge-cannabis-botanical-collection-volume-1/",
        )
        # CRITICAL BROS GOVERNANCE: Anonymous visitor is NOT a CRM Lead yet
        self.assertFalse(turn_res["is_lead"])
        self.assertIsNone(turn_res["lead_id"])

        # Check DB
        journey = self.service.journey_repo.get_by_session(session_id)
        self.assertIsNotNone(journey)
        self.assertEqual(journey.source, "social")
        self.assertEqual(journey.platform, "instagram")
        self.assertEqual(journey.content_id, "IG-20260906-0002")
        self.assertEqual(journey.qualification_state, "QUALIFIED_PURCHASE_READY")
        self.assertIsNone(journey.lead_id)

    def test_b_known_visitor_promotion(self):
        """TEST B — Known Visitor Promotion:
        - continue same session
        - visitor voluntarily supplies approved identity/contact information
        - existing Sales Agent/CRM intake creates or matches relationship
        - journey is promoted/linked to a Lead exactly once
        - original Instagram attribution remains intact
        - qualification and journey evidence remain intact
        """
        landing_params = {
            "source": "social",
            "platform": "instagram",
            "content_id": "IG-20260906-0002",
            "campaign_id": "STS-PILOT-001",
            "cta_id": "CTA-ASK-BUDLY-001",
            "product_or_topic": "BOTANICAL_COLLECTION",
        }
        intake_res = self._post("/api/intake", {"landing_input": landing_params})
        session_id = intake_res["session_id"]
        journey_id = intake_res["journey_id"]

        # 1. Anonymous turn
        self._post("/api/turn", {
            "session_id": session_id,
            "message": "I want to buy the botanical collection book",
        })

        # 2. User voluntarily provides identity through standard start path
        start_res = self._post("/api/start", {
            "name": "Jordan Lee",
            "email": "jordan@example.com",
            "session_id": session_id,
            "attribution": landing_params,
        })
        customer_id = start_res["customer_id"]
        self.assertIsNotNone(customer_id)

        # 3. Verify journey is linked to the canonical customer as Lead
        journey = self.service.journey_repo.get_by_session(session_id)
        self.assertIsNotNone(journey)
        self.assertEqual(journey.lead_id, customer_id)
        self.assertEqual(journey.source, "social")
        self.assertEqual(journey.platform, "instagram")
        self.assertEqual(journey.content_id, "IG-20260906-0002")
        self.assertEqual(journey.qualification_state, "QUALIFIED_PURCHASE_READY")

        # Verify lead record in CRM
        lead = self.service.journey_repo.get_lead(customer_id)
        self.assertIsNotNone(lead)
        self.assertEqual(lead.lead_id, customer_id)
        self.assertEqual(lead.journey_id, journey_id)
        self.assertEqual(lead.promotion_reason, "CONTACT_INFO_SUPPLIED")

    def test_c_idempotent_promotion(self):
        """TEST C — Idempotent Promotion:
        - repeated identity submission or repeated event does not create duplicate Leads or journeys
        """
        intake_params = {
            "source": "social",
            "platform": "instagram",
            "content_id": "IG-20260906-0002",
            "campaign_id": "STS-PILOT-001",
            "cta_id": "CTA-ASK-BUDLY-001",
        }
        res1 = self._post("/api/intake", {"landing_input": intake_params, "session_id": "sess_idem_test"})
        self.assertTrue(res1["is_new_session"])

        res2 = self._post("/api/intake", {"landing_input": intake_params, "session_id": "sess_idem_test"})
        self.assertFalse(res2["is_new_session"])
        self.assertEqual(res1["journey_id"], res2["journey_id"])

        # Multiple identity submissions on same session
        start1 = self._post("/api/start", {
            "name": "Sam Taylor",
            "email": "sam@example.com",
            "session_id": "sess_idem_test",
            "attribution": intake_params,
        })
        start2 = self._post("/api/start", {
            "name": "Sam Taylor",
            "email": "sam@example.com",
            "session_id": "sess_idem_test",
            "attribution": intake_params,
        })
        self.assertEqual(start1["customer_id"], start2["customer_id"])

        journey = self.service.journey_repo.get_by_session("sess_idem_test")
        self.assertEqual(journey.lead_id, start1["customer_id"])

    def test_d_casual_anonymous_visitor(self):
        """TEST D — Casual Anonymous Visitor:
        - remains anonymous
        - remains unpromoted
        """
        intake_res = self._post("/api/intake", {
            "landing_input": {"source": "direct", "platform": "web"}
        })
        session_id = intake_res["session_id"]

        turn_res = self._post("/api/turn", {
            "session_id": session_id,
            "message": "Hello, what is this website?",
        })
        self.assertFalse(turn_res["is_lead"])
        self.assertIsNone(turn_res["lead_id"])

        journey = self.service.journey_repo.get_by_session(session_id)
        self.assertIsNotNone(journey)
        self.assertIsNone(journey.lead_id)


if __name__ == "__main__":
    unittest.main()
