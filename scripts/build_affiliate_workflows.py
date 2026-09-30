"""Generate disabled n8n orchestration shells from the ratified AFF manifest."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "deploy" / "n8n" / "AFF-001-workflow-manifest.json"
OUTPUT = ROOT / "deploy" / "n8n" / "affiliate"


def build() -> list[Path]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    paths = []
    for spec in manifest["workflows"]:
        workflow = {
            "name": f"{spec['id']} — {spec['name']} [NON-PRODUCTION]",
            "active": False,
            "settings": {"executionOrder": "v1", "saveDataErrorExecution": "all", "saveDataSuccessExecution": "all"},
            "meta": {"templateCredsSetupCompleted": False},
            "tags": [{"name": "AFF-001"}, {"name": "NON-PRODUCTION"}],
            "nodes": [
                {"id": "manual", "name": "Manual Test Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [0, 0], "parameters": {}},
                {"id": "contract", "name": "Governed Contract", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [240, 0], "parameters": {"jsCode": "return [{json:{workflow_id:'%s',active:false,scope:'NON_PRODUCTION_TEST_ONLY',input:$json}}];" % spec["id"]}},
                {"id": "disabled", "name": "Feature Gate OFF", "type": "n8n-nodes-base.stopAndError", "typeVersion": 1, "position": [480, 0], "parameters": {"errorMessage": "AFF-001 workflow is disabled by default; governed test activation required."}},
            ],
            "connections": {"Manual Test Trigger": {"main": [[{"node": "Governed Contract", "type": "main", "index": 0}]]}, "Governed Contract": {"main": [[{"node": "Feature Gate OFF", "type": "main", "index": 0}]]}},
            "pinData": {},
        }
        path = OUTPUT / f"{spec['id']}.json"
        path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


if __name__ == "__main__":
    for generated in build():
        print(generated.relative_to(ROOT))
