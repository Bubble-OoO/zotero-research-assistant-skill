# -*- coding: utf-8 -*-
"""JSON command-line interface for agent-neutral Zotero access."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _load_env(path: Path) -> None:
    """Load a small .env subset without requiring python-dotenv."""
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


_load_env(Path(os.environ.get("ZOTERO_SKILL_ENV", SKILL_ROOT / ".env")))

from zotero_tools import (  # noqa: E402
    zotero_add_note,
    zotero_add_tags,
    zotero_find_collection,
    zotero_get_annotations,
    zotero_get_children,
    zotero_get_collection_items,
    zotero_get_item,
    zotero_health,
    zotero_list_collections,
    zotero_read_pdf_text,
    zotero_search,
    zotero_update_note,
)


def _add_common_limit(parser: argparse.ArgumentParser, default: int) -> None:
    parser.add_argument("--limit", type=int, default=default)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Zotero Research Assistant JSON CLI (no MCP)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="检查配置和 Zotero 连接")

    collections = sub.add_parser("collections", help="列出或筛选目录")
    collections.add_argument("--query")
    _add_common_limit(collections, 200)

    find_collection = sub.add_parser("find-collection", help="精确解析目录")
    find_collection.add_argument("name_or_path")

    collection_items = sub.add_parser("collection-items", help="读取目录内文献")
    collection_items.add_argument("collection", help="目录 key、精确名称或 parent/child 路径")
    collection_items.add_argument("--recursive", action="store_true", help="包含全部子目录")
    collection_items.add_argument("--item-type")
    _add_common_limit(collection_items, 200)

    search = sub.add_parser("search", help="搜索顶层文献")
    search.add_argument("query")
    search.add_argument("--collection", help="只在指定目录中搜索")
    search.add_argument("--recursive", action="store_true", help="目录搜索时包含全部子目录")
    search.add_argument("--item-type")
    _add_common_limit(search, 50)

    item = sub.add_parser("item", help="读取条目元数据")
    item.add_argument("item_key")

    children = sub.add_parser("children", help="读取附件和笔记")
    children.add_argument("item_key")

    read = sub.add_parser("read", help="分段读取 PDF 全文")
    read.add_argument("item_key")
    read.add_argument("--attachment-key")
    read.add_argument("--start", type=int, default=0)
    read.add_argument("--max-chars", type=int, default=12000)

    annotations = sub.add_parser("annotations", help="读取全部 PDF 批注")
    annotations.add_argument("item_key")

    add_note = sub.add_parser("add-note", help="新增笔记（需要显式确认）")
    add_note.add_argument("item_key")
    add_note.add_argument("note_html")
    add_note.add_argument("--confirm-write", action="store_true")

    update_note = sub.add_parser("update-note", help="更新笔记（需要显式确认）")
    update_note.add_argument("note_key")
    update_note.add_argument("note_html")
    update_note.add_argument("--confirm-write", action="store_true")

    add_tags = sub.add_parser("add-tags", help="添加标签（需要显式确认）")
    add_tags.add_argument("item_key")
    add_tags.add_argument("tags", nargs="+")
    add_tags.add_argument("--confirm-write", action="store_true")
    return parser


def dispatch(args: argparse.Namespace) -> dict:
    if args.command == "health":
        return zotero_health()
    if args.command == "collections":
        return zotero_list_collections(query=args.query, limit=args.limit)
    if args.command == "find-collection":
        return zotero_find_collection(args.name_or_path)
    if args.command == "collection-items":
        return zotero_get_collection_items(
            args.collection,
            recursive=args.recursive,
            item_type=args.item_type,
            limit=args.limit,
        )
    if args.command == "search":
        return zotero_search(
            args.query,
            item_type=args.item_type,
            limit=args.limit,
            collection=args.collection,
            recursive=args.recursive,
        )
    if args.command == "item":
        return zotero_get_item(args.item_key)
    if args.command == "children":
        return zotero_get_children(args.item_key)
    if args.command == "read":
        return zotero_read_pdf_text(
            args.item_key,
            start=args.start,
            max_chars=args.max_chars,
            attachment_key=args.attachment_key,
        )
    if args.command == "annotations":
        return zotero_get_annotations(args.item_key)
    if args.command == "add-note":
        return zotero_add_note(args.item_key, args.note_html, confirmed=args.confirm_write)
    if args.command == "update-note":
        return zotero_update_note(args.note_key, args.note_html, confirmed=args.confirm_write)
    if args.command == "add-tags":
        return zotero_add_tags(args.item_key, args.tags, confirmed=args.confirm_write)
    raise AssertionError(f"Unhandled command: {args.command}")


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = dispatch(args)
    except Exception as exc:  # Keep stdout machine-readable even for unexpected failures.
        result = {"ok": False, "code": "cli_failure", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
