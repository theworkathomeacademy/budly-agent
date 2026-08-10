#!/usr/bin/env python3
"""Build and verify a deterministic Budly WordPress release artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy" / "wordpress" / "budly-sales-agent"
ARCHIVE_ROOT = "budly-sales-agent"
APPLICATION_VERSION = "1.7.1"
SCHEMA_VERSION = "1.5.0"
RULES_VERSION = "bros-rules-1.5.0.0"
COMMERCE_CONFIG_VERSION = "commerce-attribution-1.6.0.0"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
DISALLOWED_NAMES = {".DS_Store", "Thumbs.db", ".env"}
DISALLOWED_SUFFIXES = {".zip", ".log", ".pyc", ".sql", ".sqlite", ".db"}
TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".php", ".txt", ".xml"}


def selected_files(plugin: Path = PLUGIN) -> list[Path]:
    files: list[Path] = []
    for path in plugin.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(plugin)
        if "__pycache__" in relative.parts:
            continue
        if path.name in DISALLOWED_NAMES or path.suffix.lower() in DISALLOWED_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(plugin).as_posix())


def zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, FIXED_TIME)
    # Stored entries avoid platform/zlib-version variance while preserving a
    # standard WordPress-installable ZIP container.
    info.compress_type = ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def release_bytes(path: Path) -> bytes:
    """Return platform-independent bytes for a deployable source file."""
    data = path.read_bytes()
    if path.suffix.lower() in TEXT_SUFFIXES:
        return data.replace(b"\r\n", b"\n")
    return data


def build(
    output: Path,
    source_commit: str,
    release: str = APPLICATION_VERSION,
    plugin: Path = PLUGIN,
) -> str:
    files = selected_files(plugin)
    manifest_files = []
    for path in files:
        data = release_bytes(path)
        manifest_files.append(
            {
                "path": path.relative_to(plugin).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest().upper(),
                "size": len(data),
            }
        )
    manifest = {
        "application_version": APPLICATION_VERSION,
        "archive_root": ARCHIVE_ROOT,
        "release": release,
        "rules_version": RULES_VERSION,
        "commerce_configuration_version": COMMERCE_CONFIG_VERSION,
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
        "files": manifest_files,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for path in files:
            name = f"{ARCHIVE_ROOT}/{path.relative_to(plugin).as_posix()}"
            archive.writestr(zip_info(name), release_bytes(path))
        archive.writestr(zip_info(f"{ARCHIVE_ROOT}/release-manifest.json"), manifest_bytes)
    digest = hashlib.sha256(output.read_bytes()).hexdigest().upper()
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii", newline="\n"
    )
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "deploy" / "wordpress" / "budly-sales-agent.zip",
    )
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--release", default=APPLICATION_VERSION)
    args = parser.parse_args()
    print(build(args.output.resolve(), args.source_commit, args.release))


if __name__ == "__main__":
    main()
