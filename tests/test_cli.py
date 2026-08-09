import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "zotero_cli.py"


class CliTests(unittest.TestCase):
    def test_help_works_without_optional_runtime_services(self):
        result = subprocess.run(
            [sys.executable, str(CLI), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("collection-items", result.stdout)

    def test_unconfirmed_write_is_machine_readable_and_blocked(self):
        result = subprocess.run(
            [sys.executable, str(CLI), "add-tags", "PAPER001", "reviewed"],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["code"], "confirmation_required")


if __name__ == "__main__":
    unittest.main()
