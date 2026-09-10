"""Create the STS-2 n8n workflow artifact from the established REV export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CORRELATION_CODE = """const metaData = Array.isArray(body.meta_data) ? body.meta_data : [];
const metaValue = (key) => {
  const item = metaData.find((candidate) => candidate && candidate.key === key);
  return item && ['string', 'number'].includes(typeof item.value) ? String(item.value) : '';
};
const correlationId = metaValue('_budly_commerce_correlation_id');
const conversationId = metaValue('_budly_conversation_id');
const decisionId = metaValue('_budly_decision_id');
const correlationValid = /^sts2_[a-f0-9]{32}$/.test(correlationId)
  && /^(?:conv_[a-z0-9]{12,40}|[a-f0-9-]{36})$/.test(conversationId)
  && /^dec_[a-z0-9]{12,40}$/.test(decisionId);
const commerceCorrelation = correlationValid ? {
  status: 'linked',
  correlation_id: correlationId,
  conversation_id: conversationId,
  decision_id: decisionId,
} : { status: correlationId || conversationId || decisionId ? 'invalid' : 'absent' };"""


def build(source: Path, destination: Path) -> None:
    workflows = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(workflows, list) or len(workflows) != 1:
        raise ValueError("Expected exactly one established workflow export")
    workflow = workflows[0]
    if workflow.get("id") != "REVWooIntakeV1":
        raise ValueError("Unexpected workflow identity")
    node = next((item for item in workflow["nodes"] if item.get("name") == "Normalize Revenue Event v1"), None)
    if not node:
        raise ValueError("Normalize Revenue Event v1 node not found")
    code = node["parameters"]["jsCode"]
    marker = "const amount = (value) => Number(Number(value ?? 0).toFixed(2));"
    if "const commerceCorrelation =" not in code:
        if code.count(marker) != 1:
            raise ValueError("Normalizer insertion marker changed")
        code = code.replace(marker, marker + "\n" + CORRELATION_CODE)
    field_marker = "      payload_sha256: $json.payload_sha256,"
    field = "      commerce_correlation: commerceCorrelation,\n"
    if field.strip() not in code:
        if code.count(field_marker) != 1:
            raise ValueError("Revenue-event insertion marker changed")
        code = code.replace(field_marker, field + field_marker)
    node["parameters"]["jsCode"] = code
    workflow["description"] = "Production REV intake with STS-2 deterministic commerce correlation; preserves established HMAC, validation, normalization, idempotency, and Supabase RPC boundaries."
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(workflows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    build(args.source, args.destination)
