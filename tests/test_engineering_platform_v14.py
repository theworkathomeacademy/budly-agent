import json
import re
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts import build_plugin, validate_repository, validate_versions


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deploy/wordpress/budly-sales-agent"


def static_plugin_dependencies():
    """Return literal plugin-local PHP dependencies declared with require/include."""
    dependencies = set()
    plugin_constant = re.compile(
        r"\b(?:require|require_once|include|include_once)\s+"
        r"BUDLY_SALES_DIR\s*\.\s*['\"]([^'\"]+)['\"]\s*;"
    )
    current_directory = re.compile(
        r"\b(?:require|require_once|include|include_once)\s+"
        r"__DIR__\s*\.\s*['\"]([^'\"]+)['\"]\s*;"
    )
    for php_file in PLUGIN.rglob("*.php"):
        source = php_file.read_text(encoding="utf-8")
        for relative in plugin_constant.findall(source):
            dependencies.add(Path(relative.replace("\\", "/")))
        for relative in current_directory.findall(source):
            dependencies.add(
                (php_file.parent.relative_to(PLUGIN) / relative.lstrip("/\\"))
            )
    return dependencies


class EngineeringPlatformV14Tests(unittest.TestCase):
    def test_version_sources_are_consistent(self):
        found = validate_versions.validate("1.8.1")
        self.assertEqual(set(found.values()), {"1.8.1"})

    def test_tag_patch_zero_is_semantically_equivalent(self):
        self.assertEqual(validate_versions.normalize("budly-v1.4"), (1, 4, 0))

    def test_version_mismatch_is_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "deploy/wordpress/budly-sales-agent").mkdir(parents=True)
            (root / "src").mkdir()
            (root / "deploy/wordpress/budly-sales-agent/budly-sales-agent.php").write_text(
                " * Version: 1.4.0\nBUDLY_SALES_VERSION', '1.4.1'\n", encoding="utf-8"
            )
            (root / "src/sales_agent.py").write_text(
                'APPLICATION_VERSION = "1.4.0"\n', encoding="utf-8"
            )
            (root / "CHANGELOG.md").write_text("## 1.4.0\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "version mismatch"):
                validate_versions.validate(root=root)

    def test_repository_validation_passes(self):
        tracked = validate_repository.validate()
        self.assertIn("deploy/wordpress/budly-sales-agent/budly-sales-agent.php", tracked)

    def test_forbidden_repository_file_is_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for required in validate_repository.REQUIRED_PROJECT_FILES:
                path = root / required
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test\n", encoding="utf-8")
            for required in validate_repository.REQUIRED_PLUGIN_FILES:
                path = root / validate_repository.PLUGIN / required
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test\n", encoding="utf-8")
            (root / "customer.db").write_bytes(b"not allowed")
            with self.assertRaisesRegex(ValueError, "forbidden tracked file"):
                validate_repository.validate(root)

    def test_build_is_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.zip"
            second = Path(directory) / "second.zip"
            first_hash = build_plugin.build(first, "TEST-COMMIT")
            second_hash = build_plugin.build(second, "TEST-COMMIT")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(first_hash, second_hash)

    def test_build_has_single_plugin_root_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.zip"
            build_plugin.build(output, "TEST-COMMIT")
            with ZipFile(output) as archive:
                names = archive.namelist()
                self.assertTrue(all(name.startswith("budly-sales-agent/") for name in names))
                self.assertIn("budly-sales-agent/release-manifest.json", names)

    def test_static_local_php_dependencies_exist_in_source_and_release(self):
        dependencies = static_plugin_dependencies()
        self.assertTrue(dependencies, "no static plugin-local PHP dependencies found")
        missing_source = sorted(
            path.as_posix() for path in dependencies if not (PLUGIN / path).is_file()
        )
        self.assertEqual(missing_source, [], "missing source PHP dependencies")

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.zip"
            build_plugin.build(output, "TEST-COMMIT")
            with ZipFile(output) as archive:
                packaged = set(archive.namelist())
        missing_release = sorted(
            path.as_posix()
            for path in dependencies
            if f"budly-sales-agent/{path.as_posix()}" not in packaged
        )
        self.assertEqual(missing_release, [], "missing packaged PHP dependencies")

    def test_manifest_records_versions_source_and_file_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.zip"
            build_plugin.build(output, "abc123")
            with ZipFile(output) as archive:
                manifest = json.loads(archive.read("budly-sales-agent/release-manifest.json"))
            self.assertEqual(manifest["application_version"], "1.8.1")
            self.assertEqual(manifest["schema_version"], "1.5.0")
            self.assertEqual(manifest["rules_version"], "bros-rules-1.5.0.0")
            self.assertEqual(manifest["source_commit"], "abc123")
            self.assertTrue(all(item["sha256"] and item["size"] > 0 for item in manifest["files"]))

    def test_release_excludes_development_and_secret_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.zip"
            build_plugin.build(output, "TEST-COMMIT")
            with ZipFile(output) as archive:
                names = archive.namelist()
            self.assertFalse(any(name.endswith((".py", ".db", ".env", ".zip")) for name in names))

    def test_release_normalizes_text_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin = Path(directory) / "plugin"
            plugin.mkdir()
            source = plugin / "sample.php"
            source.write_bytes(b"<?php\r\necho 'Budly';\r\n")
            output = Path(directory) / "release.zip"
            build_plugin.build(output, "TEST-COMMIT", plugin=plugin)
            with ZipFile(output) as archive:
                packaged = archive.read("budly-sales-agent/sample.php")
            self.assertEqual(packaged, b"<?php\necho 'Budly';\n")

    def test_checksum_sidecar_matches_release(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "release.zip"
            digest = build_plugin.build(output, "TEST-COMMIT")
            self.assertEqual(
                output.with_suffix(".zip.sha256").read_text(encoding="ascii"),
                f"{digest}  release.zip\n",
            )

    def test_pull_request_build_uses_head_commit_provenance(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow)
        self.assertIn('--source-commit "$SOURCE_COMMIT"', workflow)


if __name__ == "__main__":
    unittest.main()
