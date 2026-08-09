# Local setup and agent integration

## 1. Requirements

- Python 3.10 or newer
- Zotero 7 or newer for local API and indexed full-text access
- Zotero desktop running with **Settings → Advanced → Allow other applications on this computer to communicate with Zotero** enabled

Install Python dependencies from the skill directory:

```text
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`. Keep `.env` inside the installed skill directory and never commit or expose it.

## 2. Connection modes

### Local read-only

Use:

```text
ZOTERO_LOCAL=true
ZOTERO_DATA_DIR=~/Zotero
```

No Zotero API key is required. Zotero desktop must remain open.

### Hybrid local-read/cloud-write

Keep `ZOTERO_LOCAL=true` and additionally set `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE`, and a write-capable `ZOTERO_API_KEY`. Reads use the local API; confirmed writes use the Web API.

### Cloud

Set `ZOTERO_LOCAL=false` plus `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE`, and `ZOTERO_API_KEY`.

Validate after configuration:

```text
python scripts/zotero_cli.py health
python scripts/zotero_cli.py collections --limit 5
```

## 3. Install as a Skill

Copy the entire `zotero-research-assistant` directory, not only `SKILL.md`.

- Codex personal skill: `~/.codex/skills/zotero-research-assistant/`
- Claude Code personal skill: `~/.claude/skills/zotero-research-assistant/`
- Claude Code project skill: `.claude/skills/zotero-research-assistant/`
- WorkBuddy: import this local skill directory/package in the Skills UI. Installations that use filesystem discovery commonly use `~/.workbuddy/skills/zotero-research-assistant/`.

The integration is transport-neutral: the agent reads `SKILL.md` and executes the local JSON CLI using its terminal capability. Do not add an MCP server configuration.

## 4. Invocation examples

- Codex: `$zotero-research-assistant 列出“人机交互”目录及其子目录中的论文`
- Claude Code: `/zotero-research-assistant 列出“人机交互”目录及其子目录中的论文`
- WorkBuddy: mention Zotero naturally or select/import the skill in the Skills panel.

If the agent cannot execute Python, grant its terminal tool access to this skill directory. Do not copy API keys into prompts.
