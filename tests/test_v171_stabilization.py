import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHP = os.environ.get("BUDLY_PHP_BINARY", "php")


class V171PhpStabilizationTests(unittest.TestCase):
    def test_production_php_security_and_behavior(self):
        result = subprocess.run(
            [PHP, str(ROOT / "tests" / "php" / "v171_stabilization.php")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_bootstrap_loads_v17_modules(self):
        result = subprocess.run(
            [PHP, str(ROOT / "tests" / "php" / "v171_bootstrap_load.php")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
