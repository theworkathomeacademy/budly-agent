#!/usr/bin/env python3
"""Build a deterministic, secret-free Budly conversational runtime archive."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_ROOT = "budly-runtime"
RUNTIME_VERSION = "1.8.0"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
FILES = (
    "src/budly_runtime/__init__.py",
    "src/budly_runtime/config.py",
    "src/budly_runtime/events.py",
    "src/budly_runtime/http_service.py",
    "src/budly_runtime/model.py",
    "src/budly_runtime/personality.py",
    "src/budly_runtime/preference_registry.py",
    "src/budly_runtime/production_knowledge.py",
    "src/budly_runtime/production_runtime.py",
    "src/budly_runtime/prompt.py",
    "src/budly_runtime/relationship_registry.py",
    "src/budly_runtime/session.py",
    "src/budly_runtime/tool_gateway.py",
    "config/budly_runtime/education-corpus-v0.1.json",
    "config/budly_runtime/personality-package-v0.1.json",
    "config/budly_runtime/runtime.production.example.json",
    "config/policies.json",
    "config/products.json",
    "config/tool_gateway/tg-p05a-preference-registry.json",
    "config/tool_gateway/tg-p05b-relationship-fact-registry.json",
    "deploy/runtime/budly-runtime.Dockerfile",
)


def info(name: str) -> ZipInfo:
    result = ZipInfo(name, FIXED_TIME)
    result.compress_type = ZIP_STORED
    result.create_system = 3
    result.external_attr = 0o100644 << 16
    return result


def normalized(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def build(output: Path, source_commit: str) -> str:
    entries = []
    for relative in FILES:
        data = normalized(ROOT / relative)
        entries.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest().upper(), "size": len(data)})
    manifest = {
        "runtime_version": RUNTIME_VERSION,
        "source_commit": source_commit,
        "archive_root": ARCHIVE_ROOT,
        "durable_memory_enabled": False,
        "entrypoint": "python -m src.budly_runtime.http_service",
        "files": entries,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", ZIP_STORED) as archive:
        for entry in entries:
            archive.writestr(info(f"{ARCHIVE_ROOT}/{entry['path']}"), normalized(ROOT / entry["path"]))
        archive.writestr(info(f"{ARCHIVE_ROOT}/runtime-manifest.json"),
                         (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode())
    digest = hashlib.sha256(output.read_bytes()).hexdigest().upper()
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    print(build(args.output.resolve(), args.source_commit))


if __name__ == "__main__":
    main()
