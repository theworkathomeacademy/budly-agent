#!/usr/bin/env python3
"""Validate Budly application version consistency and optional tag identity."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy" / "wordpress" / "budly-sales-agent" / "budly-sales-agent.php"
PYTHON_APP = ROOT / "src" / "sales_agent.py"
CHANGELOG = ROOT / "CHANGELOG.md"


def normalize(value: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", value)
    if not match:
        raise ValueError(f"no semantic version in {value!r}")
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def versions(root: Path = ROOT) -> dict[str, str]:
    plugin = (root / PLUGIN.relative_to(ROOT)).read_text(encoding="utf-8")
    python_app = (root / PYTHON_APP.relative_to(ROOT)).read_text(encoding="utf-8")
    changelog = (root / CHANGELOG.relative_to(ROOT)).read_text(encoding="utf-8")
    patterns = {
        "plugin_header": (plugin, r"(?m)^\s*\*\s*Version:\s*([0-9.]+)\s*$"),
        "plugin_constant": (plugin, r"BUDLY_SALES_VERSION',\s*'([0-9.]+)'"),
        "python_application": (python_app, r'APPLICATION_VERSION\s*=\s*"([0-9.]+)"'),
        "changelog": (changelog, r"(?m)^##\s+\[?([0-9.]+)\]?"),
    }
    result: dict[str, str] = {}
    for name, (text, pattern) in patterns.items():
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"missing {name} version")
        result[name] = match.group(1)
    return result


def validate(expected: str | None = None, tag: str | None = None, root: Path = ROOT) -> dict[str, str]:
    found = versions(root)
    normalized = {name: normalize(value) for name, value in found.items()}
    if len(set(normalized.values())) != 1:
        raise ValueError(f"version mismatch: {found}")
    actual = next(iter(normalized.values()))
    if expected and actual != normalize(expected):
        raise ValueError(f"expected {expected}, found {found}")
    if tag and actual != normalize(tag):
        raise ValueError(f"tag {tag} does not match {found}")
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-version")
    parser.add_argument("--tag")
    args = parser.parse_args()
    found = validate(args.expected_version, args.tag)
    print("version consistency passed:", ", ".join(f"{key}={value}" for key, value in found.items()))


if __name__ == "__main__":
    main()
