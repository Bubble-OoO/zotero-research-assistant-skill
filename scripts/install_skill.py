# -*- coding: utf-8 -*-
"""Install this portable Skill into a supported agent's personal skill folder."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


SKILL_NAME = "zotero-research-assistant"
SOURCE = Path(__file__).resolve().parent.parent


def default_target(agent: str) -> Path:
    home = Path.home()
    if agent == "codex":
        codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
        return codex_home / "skills" / SKILL_NAME
    if agent == "claude":
        return home / ".claude" / "skills" / SKILL_NAME
    if agent == "workbuddy":
        return home / ".workbuddy" / "skills" / SKILL_NAME
    raise ValueError(agent)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the Zotero Skill without MCP")
    parser.add_argument("agent", choices=("codex", "claude", "workbuddy"))
    parser.add_argument("--target-dir", type=Path, help="Override the complete destination directory")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = (args.target_dir or default_target(args.agent)).expanduser().resolve()
    print(f"source={SOURCE}")
    print(f"target={target}")
    if args.dry_run:
        return 0

    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        SOURCE,
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns(".env", ".venv", "__pycache__", "*.pyc"),
    )
    print("installed=true")
    print(f"next=copy {target / '.env.example'} to {target / '.env'} and run the health command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
