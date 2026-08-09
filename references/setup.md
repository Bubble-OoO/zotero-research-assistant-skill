# Manual setup and troubleshooting

The main README recommends letting Codex configure the Skill automatically. Use this document when automatic setup needs troubleshooting, when you want project-scoped discovery, or when you are configuring another Agent manually.

## Contents

1. Requirements
2. Make the Skill discoverable manually
3. Select the Python environment manually
4. Configure Zotero
5. Validate and invoke
6. Troubleshooting

## 1. Requirements

- Python 3.10 or newer
- Zotero 7 or newer for the local API and indexed full text
- An agent that can execute local terminal commands
- Zotero desktop running for local mode

In Zotero, enable **Settings → Advanced → Allow other applications on this computer to communicate with Zotero**.

This project is an Agent Skill, not an MCP server or a model runtime. Do not add MCP configuration, model API configuration, or a standalone chat process. The Agent performs all reasoning.

## 2. Make the Skill discoverable manually

Clone the repository anywhere, or download and extract the [main branch ZIP](https://github.com/Bubble-OoO/zotero-research-assistant-skill/archive/refs/heads/main.zip). Then link that source directory into the agent's discovery directory so source updates take effect without maintaining a second copy. Users may alternatively clone directly into the discovery directory.

```bash
git clone https://github.com/Bubble-OoO/zotero-research-assistant-skill.git
cd zotero-research-assistant-skill
```

### Codex personal scope

Codex currently discovers personal Skills under `~/.agents/skills/<skill-name>/`. The directory is `.agents` (plural), not `.agent` and not `.codex/skills`.

Windows PowerShell, run from the cloned repository root:

```powershell
$SkillSource = (Resolve-Path ".").Path
$SkillsRoot = Join-Path $HOME ".agents\skills"
New-Item -ItemType Directory -Force $SkillsRoot
New-Item -ItemType Junction -Path (Join-Path $SkillsRoot "zotero-research-assistant") -Target $SkillSource
```

macOS/Linux, run from the cloned repository root:

```bash
mkdir -p ~/.agents/skills
ln -s "$(pwd)" \
  ~/.agents/skills/zotero-research-assistant
```

For project-only discovery, create the same link at `<project>/.agents/skills/zotero-research-assistant` instead. Codex scans `.agents/skills` from its working directory up to the repository root.

Restart Codex only if the newly created top-level directory does not appear. Run `/skills` to confirm discovery, then invoke `$zotero-research-assistant`.

### Claude Code

Link the same source directory to either:

- Personal: `~/.claude/skills/zotero-research-assistant`
- Project: `<project>/.claude/skills/zotero-research-assistant`

Invoke it with `/zotero-research-assistant`.

### WorkBuddy and other Agents

Import the cloned repository from the Agent's Skills UI when available. If the Agent supports filesystem discovery, link the repository into its documented personal or project Skills directory. Grant terminal access to the Skill and Python interpreter. Do not configure MCP or a separate model provider for this Skill.

## 3. Select the Python environment manually

CMD and PowerShell use the `python` currently found on `PATH`:

```cmd
python -m pip install -r requirements.txt
python -c "import sys; print(sys.executable)"
```

For Conda, activate an existing environment or create one first:

```cmd
conda create -n zotero-skill python=3.12 -y
conda activate zotero-skill
python -m pip install -r requirements.txt
python -c "import sys; print(sys.executable)"
```

On macOS/Linux without Conda:

```bash
python3 -m pip install -r requirements.txt
python3 -c 'import sys; print(sys.executable)'
```

The Agent's default `python` may differ from the environment containing the dependencies. Put the exact path printed above in `.env`:

```dotenv
ZOTERO_PYTHON=C:/path/to/python.exe
```

Use forward slashes on Windows to keep the value easy to read. `scripts/run_zotero.py` starts with the agent's available Python, reads `.env`, and delegates every Zotero command to `ZOTERO_PYTHON`. If the agent's default Python already has the dependencies, leave `ZOTERO_PYTHON` empty.

## 4. Configure Zotero

Copy `.env.example` to `.env` in the Skill source directory. With a linked Skill, this remains the only configuration file.

Local read-only mode needs no API key:

```dotenv
ZOTERO_LOCAL=true
ZOTERO_DATA_DIR=~/Zotero
```

`ZOTERO_DATA_DIR` is used as a PDF fallback when indexed full text is unavailable. Change it only when the Zotero data directory is non-default.

For local reads plus confirmed cloud writes, also set:

```dotenv
ZOTERO_LIBRARY_ID=1234567
ZOTERO_LIBRARY_TYPE=user
ZOTERO_API_KEY=replace-with-a-write-capable-key
```

For cloud-only access, set `ZOTERO_LOCAL=false` and provide the same three cloud values. Never commit `.env` or paste API keys into prompts.

## 5. Validate and invoke

Manual validation is optional and intended for setup or troubleshooting:

```text
python scripts/run_zotero.py health
```

Normal Codex use requires only:

```text
$zotero-research-assistant List papers in the “Human-Computer Interaction” collection and its subcollections.
```

The Skill automatically checks the connection, resolves the collection exactly, and runs the required Zotero tools. Users do not manually run Python for ordinary library requests.

## 6. Troubleshooting

- `python_not_found`: correct `ZOTERO_PYTHON` in `.env`.
- `No module named pyzotero`: install `requirements.txt` with the interpreter named by `ZOTERO_PYTHON`.
- `connection_failed`: start Zotero and enable local application communication.
- Skill absent from `/skills`: verify the linked folder contains `SKILL.md`, confirm `.agents` is plural, and restart Codex once.
- Chinese text is garbled: use a UTF-8 terminal; the CLI emits UTF-8 JSON with `ensure_ascii=false`.
