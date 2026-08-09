import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "zotero_cli.py"
RUNNER = ROOT / "scripts" / "run_zotero.py"


def run_command(command, *, env=None):
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        env=env,
    )


class CliTests(unittest.TestCase):
    def test_help_works_without_optional_runtime_services(self):
        result = run_command([sys.executable, str(CLI), "--help"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("collection-items", result.stdout)

    def test_unconfirmed_write_is_machine_readable_and_blocked(self):
        result = run_command(
            [sys.executable, str(CLI), "add-tags", "PAPER001", "reviewed"]
        )
        payload = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "confirmation_required")

    def test_runner_uses_current_python_when_no_override_is_configured(self):
        env = os.environ.copy()
        env.pop("ZOTERO_PYTHON", None)
        env["ZOTERO_SKILL_ENV"] = str(ROOT / "tests" / "missing.env")
        result = run_command([sys.executable, str(RUNNER), "--help"], env=env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("collection-items", result.stdout)

    def test_runner_reports_invalid_configured_python_as_json(self):
        env = os.environ.copy()
        env["ZOTERO_PYTHON"] = str(ROOT / "missing-python.exe")
        env["ZOTERO_SKILL_ENV"] = str(ROOT / "tests" / "missing.env")
        result = run_command([sys.executable, str(RUNNER), "health"], env=env)
        payload = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "python_not_found")

    def test_runner_accepts_configured_python(self):
        env = os.environ.copy()
        env["ZOTERO_PYTHON"] = sys.executable
        env["ZOTERO_SKILL_ENV"] = str(ROOT / "tests" / "missing.env")
        result = run_command([sys.executable, str(RUNNER), "--help"], env=env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("collection-items", result.stdout)


if __name__ == "__main__":
    unittest.main()
