from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REQUIRED_MODULES = (
    "BUDLY.IDENTITY.v1.0", "BUDLY.VOICE.v1.0", "BUDLY.CURIOSITY.v1.0", "BUDLY.EMPATHY.v1.0",
    "BUDLY.HUMOR.v1.0", "BUDLY.SALES_STYLE.v1.0", "BUDLY.EDUCATION_STYLE.v1.0",
    "BUDLY.RELATIONSHIP_STYLE.v1.0", "BUDLY.CONVERSATION_RULES.v1.0", "BUDLY.CONVERSATION_MOMENTUM.v1.0",
)


class PersonalityPackageLoader:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self, package_id: str = "BUDLY.PERSONALITY_PACKAGE.v0.1") -> dict[str, Any]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("package_id") != package_id:
            raise ValueError("personality package version not found")
        modules = data.get("modules", {})
        missing = set(REQUIRED_MODULES) - set(modules)
        if missing:
            raise ValueError(f"missing personality modules: {sorted(missing)}")
        return data
