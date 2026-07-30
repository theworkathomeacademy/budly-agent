#!/usr/bin/env python3
"""Build a deterministic Budly WordPress plugin ZIP from the Git source tree."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy" / "wordpress" / "budly-sales-agent"
ARCHIVE_ROOT = "budly-sales-agent"
FIXED_TIME = (2026, 7, 30, 0, 0, 0)
DISALLOWED_NAMES = {".DS_Store", "Thumbs.db"}
DISALLOWED_SUFFIXES = {".zip", ".log", ".pyc"}


def selected_files() -> list[Path]:
    files = []
    for path in PLUGIN.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PLUGIN)
        if "__pycache__" in relative.parts:
            continue
        if path.name in DISALLOWED_NAMES or path.suffix.lower() in DISALLOWED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(PLUGIN).as_posix())


def zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, FIXED_TIME)
    info.compress_type = ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def build(output: Path, source_commit: str, release: str) -> str:
    files = selected_files()
    manifest_files = []
    for path in files:
        data = path.read_bytes()
        manifest_files.append(
            {
                "path": path.relative_to(PLUGIN).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest().upper(),
                "size": len(data),
            }
        )
    manifest = {
        "application_version": "1.3.4",
        "archive_root": ARCHIVE_ROOT,
        "release": release,
        "rules_version": "bros-rules-1.3.4.1",
        "schema_version": "1.2.0",
        "source_commit": source_commit,
        "files": manifest_files,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            name = f"{ARCHIVE_ROOT}/{path.relative_to(PLUGIN).as_posix()}"
            archive.writestr(zip_info(name), path.read_bytes())
        archive.writestr(
            zip_info(f"{ARCHIVE_ROOT}/release-manifest.json"), manifest_bytes
        )
    return hashlib.sha256(output.read_bytes()).hexdigest().upper()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--release", default="1.3.4-R1")
    args = parser.parse_args()
    print(build(args.output.resolve(), args.source_commit, args.release))


if __name__ == "__main__":
    main()
