# -*- coding: utf-8 -*-
"""Launch the Zotero JSON CLI with the configured Python interpreter.

This bootstrapper only uses the Python standard library.  It lets an agent invoke
the Skill with its default ``python`` command while the actual Zotero dependencies
live in a different Conda or virtual environment selected by ``ZOTERO_PYTHON``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


SKILL_ROOT = Path(__file__).resolve().parent.parent
CLI = SKILL_ROOT / "scripts" / "zotero_cli.py"


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name:
            os.environ.setdefault(name, value)


def _python_executable() -> str:
    configured = os.environ.get("ZOTERO_PYTHON", "").strip()
    if not configured:
        return sys.executable
    expanded = os.path.expandvars(os.path.expanduser(configured))
    candidate = Path(expanded)
    if not candidate.is_file():
        raise FileNotFoundError(f"ZOTERO_PYTHON does not exist: {candidate}")
    return str(candidate.resolve())


def main() -> int:
    env_path = Path(os.environ.get("ZOTERO_SKILL_ENV", SKILL_ROOT / ".env"))
    _load_env(env_path)
    try:
        executable = _python_executable()
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "code": "python_not_found", "error": str(exc)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    completed = subprocess.run([executable, str(CLI), *sys.argv[1:]], check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
