from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.build_affiliate_workflows import build


ROOT = Path(__file__).resolve().parents[1]


class AffiliateBuildArtifactTests(unittest.TestCase):
    def test_five_feature_gates_default_off(self):
        flags = json.loads((ROOT / "config/affiliate/feature-flags.json").read_text(encoding="utf-8"))
        values = [value for key, value in flags.items() if key.startswith("affiliate_")]
        self.assertEqual([False] * 5, values)

    def test_event_contract_is_strict_v1(self):
        schema = json.loads((ROOT / "config/affiliate/bros.affiliate_event.v1.schema.json").read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual("1.0", schema["properties"]["payload_version"]["const"])

    def test_ten_n8n_workflows_generated_disabled(self):
        paths = build()
        self.assertEqual(10, len(paths))
        for path in paths:
            workflow = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(workflow["active"])
            self.assertEqual("Feature Gate OFF", workflow["nodes"][-1]["name"])

    def test_rollback_is_non_destructive(self):
        sql = (ROOT / "migrations/affiliate_mvp/rollback_disable.sql").read_text(encoding="utf-8").lower()
        self.assertNotIn("drop table", sql)
        self.assertNotIn("delete from", sql)
        self.assertIn("enabled=false", sql)

    def test_migration_has_no_destructive_statements(self):
        sql = (ROOT / "migrations/affiliate_mvp/001_affiliate_mvp_foundation.sql").read_text(encoding="utf-8").lower()
        for forbidden in ("drop table", "truncate ", "delete from", "drop schema"):
            self.assertNotIn(forbidden, sql)


if __name__ == "__main__":
    unittest.main()
