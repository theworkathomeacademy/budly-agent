import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/"docs"/"budly-secure-memory"
PLUGIN=ROOT/"deploy"/"wordpress"/"budly-sales-agent"/"budly-sales-agent.php"

class Phase10DocumentationTests(unittest.TestCase):
 def test_required_handoff_documents_exist_and_are_linked(self):
  names=("phase-3-api-inventory.md","phase-3-database-schema.md","phase-3-security-and-threat-controls.md","phase-3-operations.md","phase-3-runtime-acceptance.md","phase-3-final-implementation-report.md")
  readme=(DOCS/"README.md").read_text(encoding="utf-8")
  for name in names:
   self.assertTrue((DOCS/name).is_file(),name);self.assertIn(name,readme)
 def test_candidate_truthfully_records_runtime_and_remaining_gate_f_work(self):
  acceptance=(DOCS/"phase-3-runtime-acceptance.md").read_text(encoding="utf-8")
  report=(DOCS/"phase-3-final-implementation-report.md").read_text(encoding="utf-8")
  self.assertIn("Gate F remains failed",acceptance);self.assertIn("not deployed",report);self.assertIn("Gates A–E pass",report);self.assertIn("LocalWP WordPress",report)
 def test_runtime_plan_covers_all_critical_acceptance_domains(self):
  plan=(DOCS/"phase-3-runtime-acceptance.md").read_text(encoding="utf-8").lower()
  for domain in ("migration","replay","cross-customer","consent","start fresh","deletion","cleanup","accessibility","smtp","backup","rollback"):self.assertIn(domain,plan)
 def test_release_version_is_1_5_0(self):
  plugin=PLUGIN.read_text(encoding="utf-8");self.assertIn("Version: 1.8.1",plugin);self.assertIn("BUDLY_SALES_VERSION', '1.8.1'",plugin)

if __name__=="__main__":unittest.main()
