#!/usr/bin/env python3
"""Validate the source repository and deployable plugin boundary."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = Path("deploy/wordpress/budly-sales-agent")
REQUIRED_PROJECT_FILES = {
    "README.md", "CHANGELOG.md", "PROJECT_STATUS.md", "ARCHITECTURE.md",
    "IMPLEMENTATION_STATUS.md", "ROADMAP.md", "SECURITY.md", "CONTRIBUTING.md",
    "docs/RELEASE_CHECKLIST.md", "docs/DEVELOPMENT_WORKFLOW.md",
}
REQUIRED_PLUGIN_FILES = {
    "budly-sales-agent.php",
    "assets/budly-sales.css",
    "assets/budly-sales.js",
    "assets/budly-cutout-v134.png",
    "templates/ask-budly-page.php",
}
FORBIDDEN_SUFFIXES = {".sql", ".sqlite", ".db", ".pem", ".key", ".p12", ".pfx", ".log", ".pyc"}
FORBIDDEN_NAMES = {".env", ".DS_Store", "Thumbs.db", "id_rsa", "id_ed25519"}


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=False
    )
    if result.returncode == 0:
        return [line.replace("\\", "/") for line in result.stdout.splitlines() if line]
    return [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(root).parts
    ]


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    tracked = tracked_files(root)
    tracked_set = set(tracked)
    for required in sorted(REQUIRED_PROJECT_FILES):
        if not (root / required).is_file():
            errors.append(f"missing project file: {required}")
    for required in sorted(REQUIRED_PLUGIN_FILES):
        if not (root / PLUGIN / required).is_file():
            errors.append(f"missing plugin file: {required}")
    for name in tracked:
        path = Path(name)
        lowered = path.name.lower()
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"forbidden tracked file: {name}")
        if lowered.startswith(".env.") and lowered != ".env.example":
            errors.append(f"forbidden tracked environment file: {name}")
        if name.startswith(f"{PLUGIN.as_posix()}/") and path.suffix.lower() == ".zip":
            errors.append(f"nested plugin archive: {name}")
    package = "deploy/wordpress/budly-sales-agent.zip"
    if package in tracked_set:
        errors.append(f"generated release archive must not be tracked: {package}")
    screenshots = [
        name for name in tracked
        if name.startswith(f"{PLUGIN.as_posix()}/")
        and ("screenshot" in Path(name).name.lower() or "template-screenshot" in Path(name).name.lower())
    ]
    for name in screenshots:
        errors.append(f"template screenshot must not be packaged: {name}")
    if errors:
        raise ValueError("\n".join(errors))
    return tracked


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    tracked = validate()
    print(f"repository validation passed: {len(tracked)} tracked files checked")


if __name__ == "__main__":
    main()
