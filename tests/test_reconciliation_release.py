import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy" / "wordpress" / "budly-sales-agent"
BUILD = ROOT / "scripts" / "build_wordpress_plugin.py"


class ReconciliationReleaseTests(unittest.TestCase):
    def test_production_template_and_assets_are_integrated(self):
        php = (PLUGIN / "budly-sales-agent.php").read_text(encoding="utf-8")
        template = PLUGIN / "templates" / "ask-budly-page.php"
        self.assertTrue(template.is_file())
        self.assertIn("budly_sales_dedicated_page_template", php)
        self.assertIn("budly-cutout-v134.png", php)
        self.assertIn("budly-avatar.png", php)
        self.assertEqual(
            hashlib.sha256((PLUGIN / "assets" / "budly-avatar.png").read_bytes()).hexdigest().upper(),
            "120A7B8BF5BF67AC07647E025BB4117FA3FD8CFF4D757E8630D7121E1C8AFBC6",
        )
        self.assertEqual(
            hashlib.sha256((PLUGIN / "assets" / "budly-cutout-v134.png").read_bytes()).hexdigest().upper(),
            "F14BFAA2C3747B43FDC324C1AC76AC1DD52727F55F9CA3BF8E767BC791D8E3CB",
        )

    def test_historical_insecure_recall_and_client_recommendation_stay_superseded(self):
        tracking = (PLUGIN / "includes" / "tracking.php").read_text(encoding="utf-8")
        javascript = (PLUGIN / "assets" / "budly-sales.js").read_text(encoding="utf-8")
        self.assertNotIn("wp_ajax_nopriv_budly_sales_verify_recall", tracking)
        self.assertIn("decisionUrl", javascript)
        self.assertIn("governedDecision", javascript)
        self.assertIn("selected_product_id", javascript)

    def test_release_build_is_deterministic_and_manifested(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            command = [
                sys.executable,
                str(BUILD),
                "--source-commit",
                "TEST-COMMIT",
                "--release",
                "1.3.4-R1",
            ]
            subprocess.run(command + ["--output", str(first)], check=True, capture_output=True)
            subprocess.run(command + ["--output", str(second)], check=True, capture_output=True)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with ZipFile(first) as archive:
                names = archive.namelist()
                self.assertIn("budly-sales-agent/release-manifest.json", names)
                self.assertNotIn("budly-sales-agent/budly-sales-agent.zip", names)
                manifest = json.loads(
                    archive.read("budly-sales-agent/release-manifest.json")
                )
            self.assertEqual(manifest["application_version"], "1.8.0")
            self.assertEqual(manifest["schema_version"], "1.5.0")
            self.assertEqual(manifest["rules_version"], "bros-rules-1.5.0.0")
            self.assertEqual(manifest["source_commit"], "TEST-COMMIT")


if __name__ == "__main__":
    unittest.main()
