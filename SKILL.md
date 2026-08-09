---
name: zotero-research-assistant
description: Access and configure a user's local or cloud Zotero library without MCP by executing the bundled JSON CLI. Use for Skill setup or troubleshooting, Zotero connection configuration, collection/folder browsing, exact collection item retrieval, library search, paper metadata, PDF full text, annotations, notes, tags, comparisons, and literature reviews. Trigger when the user mentions Zotero, a Zotero collection/folder such as “目录下的论文”, papers in their library, PDF annotations, adding Zotero notes/tags, or fixing this Skill. Never invent library contents; ground every claim in CLI output.
---

# Zotero Research Assistant

Use the bundled `scripts/run_zotero.py`; do not require or configure MCP. Resolve the absolute path of this skill directory before running it. The runner can delegate to a Conda or virtual-environment interpreter configured with `ZOTERO_PYTHON`. Read `references/setup.md` only when placing, configuring, or troubleshooting the Skill.

## Setup and troubleshooting behavior

When asked to install, configure, validate, or repair the Skill, perform all safe and reversible terminal and file operations directly. Do not tell the user to run commands or edit `.env` manually. Detect the operating system and available Python 3.10+ or Conda environments, preserve existing configuration and credentials, request approval for protected filesystem or package-install operations when required, and validate with `health` afterward. Ask the user only for actions the Agent cannot safely complete, such as enabling Zotero desktop communication, supplying a missing secret through a secure local method, or approving an external write. Never print secrets.

## Required behavior

1. Run `python <skill-dir>/scripts/run_zotero.py health` before the first Zotero operation in a task. If it returns `ok: false`, report the error and stop; do not answer from memory.
2. Treat `ok: false` from every command as a hard failure. Never transform an error or empty result into a positive claim.
3. Cite each mentioned library item as `[First author, year, Zotero key]` when those fields exist.
4. Distinguish a Zotero collection from a topic query. Never search the whole library using a collection name as a keyword.

## Route requests

### Collection or folder requests

When the user says “目录/分类/文件夹中的论文”:

1. Resolve the collection exactly:

   `python <skill-dir>/scripts/run_zotero.py find-collection "<name-or-path>"`

2. If the result is ambiguous, show the returned paths and ask the user to choose. Do not guess.
3. Read its bibliographic items:

   `python <skill-dir>/scripts/run_zotero.py collection-items "<collection-key>" --recursive --limit 200`

Use `--recursive` for the natural-language meaning “目录下” unless the user explicitly requests only items directly filed in that collection. Report the resolved collection path and whether subcollections were included.

### Topic, title, author, or keyword requests

Search top-level bibliographic items:

`python <skill-dir>/scripts/run_zotero.py search "<query>" --limit 50`

To search only inside a known collection, pass `--collection "<key-or-path>"`; add `--recursive` when subcollections are in scope.

### Paper details and source text

- Metadata: `python <skill-dir>/scripts/run_zotero.py item <item-key>`
- Attachments and notes: `python <skill-dir>/scripts/run_zotero.py children <item-key>`
- Annotations: `python <skill-dir>/scripts/run_zotero.py annotations <item-key>`
- PDF text: `python <skill-dir>/scripts/run_zotero.py read <item-key> --start 0 --max-chars 12000`

For summaries, comparisons, quotations, or literature reviews, read source text rather than inferring from titles. If `hasMore` is true and later sections matter, continue with `--start <nextStart>`. State the coverage used; do not call a partial window the full paper.

## Write safety

Treat notes and tags as external writes.

1. Prepare and display the complete note, replacement text, or tag list.
2. Wait for explicit user confirmation in a later message.
3. Only then run the matching command with `--confirm-write`:

   - `add-note <item-key> "<html>" --confirm-write`
   - `update-note <note-key> "<html>" --confirm-write`
   - `add-tags <item-key> <tag>... --confirm-write`

Never infer confirmation from the original request. Never add `--confirm-write` before the user has seen the exact change.

## Output discipline

- Preserve Zotero keys, collection paths, result counts, and error messages.
- Exclude child attachments, notes, and annotations when the user asks for papers. Include parentless standalone PDFs as documents and clearly label `standaloneAttachment: true` because they may lack author, year, and other bibliographic metadata.
- If no result is returned, say that no matching item was found under the stated scope.
- For multi-paper synthesis, identify the candidate set first, then read each selected paper or its stored abstract before drawing conclusions.
