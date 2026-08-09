# -*- coding: utf-8 -*-
"""Zotero access functions shared by the Skill CLI and optional chat agents.

This module deliberately contains no MCP transport.  Every public function accepts
JSON-serialisable values and returns a JSON-serialisable dictionary, which makes it
usable from any agent that can execute a local command.
"""

from __future__ import annotations

import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from pyzotero import zotero
except ImportError:  # Allow tests and --help to run before dependencies are installed.
    zotero = None

try:
    import pymupdf
except ImportError:
    pymupdf = None


NON_DOCUMENT_ITEM_TYPES = {"note", "annotation"}
DEFAULT_LIMIT = 50
MAX_LIMIT = 1000


def _ok(**payload: Any) -> dict[str, Any]:
    return {"ok": True, **payload}


def _error(message: str, *, code: str = "zotero_error", **details: Any) -> dict[str, Any]:
    return {"ok": False, "error": message, "code": code, **details}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_limit(value: int | None, default: int = DEFAULT_LIMIT) -> int:
    if value is None:
        return default
    return max(1, min(int(value), MAX_LIMIT))


def _require_pyzotero() -> None:
    if zotero is None:
        raise RuntimeError("缺少 pyzotero。请先运行：python -m pip install -r requirements.txt")


@lru_cache(maxsize=1)
def get_read_client():
    """Return the configured local or Web API client used for reads."""
    _require_pyzotero()
    local = _env_bool("ZOTERO_LOCAL", True)
    library_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "user")
    api_key = os.environ.get("ZOTERO_API_KEY") or None
    if local:
        return zotero.Zotero(
            os.environ.get("ZOTERO_LIBRARY_ID") or "0",
            library_type,
            api_key,
            local=True,
        )
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    if not library_id or not api_key:
        raise RuntimeError("云端模式需要 ZOTERO_LIBRARY_ID 和 ZOTERO_API_KEY")
    return zotero.Zotero(library_id, library_type, api_key)


@lru_cache(maxsize=1)
def get_write_client():
    """Use the Web API for writes, including hybrid local-read/cloud-write mode."""
    _require_pyzotero()
    library_id = os.environ.get("ZOTERO_LIBRARY_ID")
    api_key = os.environ.get("ZOTERO_API_KEY")
    library_type = os.environ.get("ZOTERO_LIBRARY_TYPE", "user")
    if not library_id or not api_key:
        raise RuntimeError(
            "写操作需要 ZOTERO_LIBRARY_ID 和具备写权限的 ZOTERO_API_KEY；"
            "本地读取模式可与云端写入组合使用"
        )
    return zotero.Zotero(library_id, library_type, api_key)


def clear_client_cache() -> None:
    """Clear cached clients after environment changes (mainly useful in tests)."""
    get_read_client.cache_clear()
    get_write_client.cache_clear()


def _paginate(method: Callable[..., list], limit: int, **kwargs: Any) -> list:
    wanted = _bounded_limit(limit)
    items: list = []
    start = 0
    while len(items) < wanted:
        page_size = min(100, wanted - len(items))
        page = method(limit=page_size, start=start, **kwargs) or []
        items.extend(page)
        if len(page) < page_size:
            break
        start += page_size
    return items[:wanted]


def _creator_names(creators: Iterable[dict[str, Any]]) -> list[str]:
    names = []
    for creator in creators:
        name = creator.get("name") or " ".join(
            value for value in (creator.get("firstName"), creator.get("lastName")) if value
        )
        if name:
            names.append(name)
    return names


def _simplify_item(raw: dict[str, Any]) -> dict[str, Any]:
    data = raw.get("data", raw)
    return {
        "key": data.get("key"),
        "itemType": data.get("itemType"),
        "title": data.get("title"),
        "creators": _creator_names(data.get("creators", [])),
        "date": data.get("date"),
        "publicationTitle": data.get("publicationTitle"),
        "abstractNote": data.get("abstractNote"),
        "tags": [tag.get("tag") for tag in data.get("tags", []) if tag.get("tag")],
        "collections": data.get("collections", []),
        "DOI": data.get("DOI"),
        "ISBN": data.get("ISBN"),
        "url": data.get("url"),
        "parentItem": data.get("parentItem") or None,
        "filename": data.get("filename"),
        "contentType": data.get("contentType"),
    }


def _collection_data(raw: dict[str, Any]) -> dict[str, Any]:
    return raw.get("data", raw)


def _load_collections(zot, limit: int = MAX_LIMIT) -> list[dict[str, Any]]:
    return _paginate(zot.collections, limit)


def _collection_index(collections: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {_collection_data(item).get("key"): _collection_data(item) for item in collections}


def _collection_path(key: str, by_key: dict[str, dict[str, Any]]) -> str:
    names: list[str] = []
    seen: set[str] = set()
    current = key
    while current and current not in seen:
        seen.add(current)
        data = by_key.get(current)
        if not data:
            break
        names.append(data.get("name") or current)
        current = data.get("parentCollection") or ""
    return "/".join(reversed(names))


def _collection_records(collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = _collection_index(collections)
    records = []
    for raw in collections:
        data = _collection_data(raw)
        key = data.get("key")
        records.append(
            {
                "key": key,
                "name": data.get("name"),
                "parentCollection": data.get("parentCollection") or None,
                "path": _collection_path(key, by_key),
            }
        )
    return sorted(records, key=lambda item: (item["path"].casefold(), item["key"] or ""))


def _match_collections(spec: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target = spec.strip().replace("\\", "/").strip("/").casefold()
    key_matches = [record for record in records if (record.get("key") or "").casefold() == target]
    if key_matches:
        return key_matches
    path_matches = [record for record in records if record["path"].casefold() == target]
    if path_matches:
        return path_matches
    return [record for record in records if (record.get("name") or "").casefold() == target]


def _resolve_collection(spec: str, records: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    matches = _match_collections(spec, records)
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        suggestions = [
            record for record in records if spec.casefold() in record["path"].casefold()
        ][:10]
        return None, _error(
            f"没有找到目录：{spec}", code="collection_not_found", suggestions=suggestions
        )
    return None, _error(
        f"目录名称不唯一：{spec}。请改用完整路径或 collection key",
        code="ambiguous_collection",
        matches=matches,
    )


def _descendant_keys(root_key: str, records: list[dict[str, Any]]) -> list[str]:
    result = [root_key]
    index = 0
    while index < len(result):
        parent = result[index]
        result.extend(
            record["key"]
            for record in records
            if record.get("parentCollection") == parent and record["key"] not in result
        )
        index += 1
    return result


def zotero_health() -> dict[str, Any]:
    """Check configuration and perform a minimal read request."""
    try:
        client = get_read_client()
        _paginate(client.collections, 1)
        return _ok(
            mode="local" if _env_bool("ZOTERO_LOCAL", True) else "cloud",
            writeConfigured=bool(os.environ.get("ZOTERO_LIBRARY_ID") and os.environ.get("ZOTERO_API_KEY")),
        )
    except Exception as exc:
        return _error(str(exc), code="connection_failed")


def zotero_search(
    query: str,
    item_type: str | None = None,
    limit: int = DEFAULT_LIMIT,
    collection: str | None = None,
    recursive: bool = False,
) -> dict[str, Any]:
    """Search top-level bibliographic items globally or inside a resolved collection."""
    if not query or not query.strip():
        return _error("query 不能为空", code="invalid_argument")
    try:
        zot = get_read_client()
        kwargs: dict[str, Any] = {"q": query.strip(), "qmode": "everything"}
        if item_type:
            kwargs["itemType"] = item_type
        if collection:
            result = _get_collection_items(
                zot, collection, recursive=recursive, limit=limit, query=query.strip(), item_type=item_type
            )
            if not result.get("ok"):
                return result
            result["query"] = query.strip()
            return result
        raw_items = _paginate(zot.top, limit, **kwargs)
        return _ok(query=query.strip(), count=len(raw_items), items=[_simplify_item(item) for item in raw_items])
    except Exception as exc:
        return _error(str(exc))


def zotero_list_collections(query: str | None = None, limit: int = 200) -> dict[str, Any]:
    """List collections with parent keys and full paths; optionally filter by name/path."""
    try:
        records = _collection_records(_load_collections(get_read_client(), MAX_LIMIT))
        if query:
            needle = query.casefold()
            records = [
                record
                for record in records
                if needle in (record.get("name") or "").casefold() or needle in record["path"].casefold()
            ]
        records = records[: _bounded_limit(limit, 200)]
        return _ok(count=len(records), collections=records)
    except Exception as exc:
        return _error(str(exc))


def zotero_find_collection(name_or_path: str) -> dict[str, Any]:
    """Resolve an exact collection key, name, or parent/child path without guessing."""
    try:
        records = _collection_records(_load_collections(get_read_client(), MAX_LIMIT))
        record, error = _resolve_collection(name_or_path, records)
        return error or _ok(collection=record)
    except Exception as exc:
        return _error(str(exc))


def _get_collection_items(
    zot,
    collection: str,
    *,
    recursive: bool,
    limit: int,
    query: str | None = None,
    item_type: str | None = None,
) -> dict[str, Any]:
    records = _collection_records(_load_collections(zot, MAX_LIMIT))
    resolved, error = _resolve_collection(collection, records)
    if error:
        return error
    keys = _descendant_keys(resolved["key"], records) if recursive else [resolved["key"]]
    wanted = _bounded_limit(limit, 200)
    by_item_key: dict[str, dict[str, Any]] = {}
    source_paths: dict[str, list[str]] = {}
    record_by_key = {record["key"]: record for record in records}
    for collection_key in keys:
        kwargs: dict[str, Any] = {}
        if query:
            kwargs.update(q=query, qmode="everything")
        if item_type:
            kwargs["itemType"] = item_type
        remaining = wanted - len(by_item_key)
        if remaining <= 0:
            break
        raw_items = _paginate(
            lambda **params: zot.collection_items_top(collection_key, **params),
            remaining,
            **kwargs,
        )
        for raw in raw_items:
            item = _simplify_item(raw)
            if not item.get("key") or item["itemType"] in NON_DOCUMENT_ITEM_TYPES:
                continue
            if item["itemType"] == "attachment" and item.get("parentItem"):
                continue
            if item["itemType"] == "attachment":
                item["standaloneAttachment"] = True
            by_item_key[item["key"]] = item
            source_paths.setdefault(item["key"], []).append(record_by_key[collection_key]["path"])
    items = list(by_item_key.values())
    for item in items:
        item["matchedCollectionPaths"] = source_paths.get(item["key"], [])
    return _ok(
        collection=resolved,
        recursive=recursive,
        searchedCollectionCount=len(keys),
        count=len(items),
        items=items,
    )


def zotero_get_collection_items(
    collection: str,
    recursive: bool = False,
    limit: int = 200,
    item_type: str | None = None,
) -> dict[str, Any]:
    """Return top-level bibliographic items directly in a collection, optionally including descendants."""
    try:
        return _get_collection_items(
            get_read_client(), collection, recursive=recursive, limit=limit, item_type=item_type
        )
    except Exception as exc:
        return _error(str(exc))


def zotero_get_item(item_key: str) -> dict[str, Any]:
    try:
        item = _simplify_item(get_read_client().item(item_key))
        records = _collection_records(_load_collections(get_read_client(), MAX_LIMIT))
        by_key = {record["key"]: record for record in records}
        item["collectionPaths"] = [
            by_key[key]["path"] for key in item.get("collections", []) if key in by_key
        ]
        return _ok(item=item)
    except Exception as exc:
        return _error(str(exc))


def zotero_get_children(item_key: str) -> dict[str, Any]:
    try:
        children = []
        for raw in get_read_client().children(item_key):
            data = raw.get("data", {})
            entry = {
                "key": data.get("key"),
                "itemType": data.get("itemType"),
                "filename": data.get("filename"),
                "contentType": data.get("contentType"),
                "title": data.get("title"),
            }
            if data.get("itemType") == "note":
                entry["note"] = data.get("note")
            children.append(entry)
        return _ok(count=len(children), children=children)
    except Exception as exc:
        return _error(str(exc))


def _pdf_attachments(zot, item_key: str) -> list[dict[str, Any]]:
    raw = zot.item(item_key)
    data = raw.get("data", {})
    if data.get("itemType") == "attachment":
        candidates = [data]
    else:
        candidates = [child.get("data", {}) for child in zot.children(item_key)]
    return [
        item
        for item in candidates
        if item.get("itemType") == "attachment"
        and (
            item.get("contentType") == "application/pdf"
            or (item.get("filename") or "").lower().endswith(".pdf")
        )
    ]


def _local_pdf_path(data: dict[str, Any]) -> Path | None:
    root = Path(os.environ.get("ZOTERO_DATA_DIR", "~/Zotero")).expanduser()
    folder = root / "storage" / str(data.get("key") or "")
    filename = data.get("filename")
    if filename and (folder / filename).is_file():
        return folder / filename
    return next(iter(folder.glob("*.pdf")), None) if folder.is_dir() else None


def _attachment_text(zot, attachment: dict[str, Any]) -> str:
    try:
        fulltext = zot.fulltext_item(attachment["key"])
        if isinstance(fulltext, dict) and fulltext.get("content"):
            return fulltext["content"]
    except Exception:
        pass
    local_path = _local_pdf_path(attachment)
    if local_path and pymupdf is not None:
        with pymupdf.open(local_path) as document:
            return "\n".join(page.get_text() for page in document)
    if pymupdf is None:
        raise RuntimeError("Zotero 全文索引不可用，且未安装 PyMuPDF 读取 PDF")
    content = zot.file(attachment["key"])
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        handle.write(content)
        temp_path = Path(handle.name)
    try:
        with pymupdf.open(temp_path) as document:
            return "\n".join(page.get_text() for page in document)
    finally:
        temp_path.unlink(missing_ok=True)


def zotero_read_pdf_text(
    item_key: str, start: int = 0, max_chars: int = 12000, attachment_key: str | None = None
) -> dict[str, Any]:
    """Read a repeatable text window; use hasMore/nextStart to continue through the paper."""
    try:
        zot = get_read_client()
        attachments = _pdf_attachments(zot, item_key)
        if attachment_key:
            attachments = [item for item in attachments if item.get("key") == attachment_key]
        if not attachments:
            return _error("没有找到匹配的 PDF 附件", code="pdf_not_found")
        attachment = attachments[0]
        text = _attachment_text(zot, attachment)
        start = max(0, int(start))
        max_chars = max(1000, min(int(max_chars), 50000))
        end = min(len(text), start + max_chars)
        return _ok(
            attachmentKey=attachment.get("key"),
            filename=attachment.get("filename"),
            start=start,
            end=end,
            totalChars=len(text),
            hasMore=end < len(text),
            nextStart=end if end < len(text) else None,
            text=text[start:end],
        )
    except Exception as exc:
        return _error(str(exc))


def zotero_get_annotations(item_key: str) -> dict[str, Any]:
    """Read Zotero-native annotations from every PDF attachment under an item."""
    try:
        zot = get_read_client()
        annotations = []
        for attachment in _pdf_attachments(zot, item_key):
            for raw in zot.children(attachment["key"]):
                data = raw.get("data", {})
                if data.get("itemType") != "annotation":
                    continue
                annotations.append(
                    {
                        "key": data.get("key"),
                        "attachmentKey": attachment.get("key"),
                        "type": data.get("annotationType"),
                        "text": data.get("annotationText"),
                        "comment": data.get("annotationComment"),
                        "color": data.get("annotationColor"),
                        "page": data.get("annotationPageLabel"),
                    }
                )
        return _ok(count=len(annotations), annotations=annotations)
    except Exception as exc:
        return _error(str(exc))


def _require_confirmation(confirmed: bool) -> dict[str, Any] | None:
    if confirmed:
        return None
    return _error(
        "写操作未执行：必须先向用户展示完整变更，并在获得确认后传入 confirmed=true",
        code="confirmation_required",
    )


def zotero_add_note(item_key: str, note_html: str, confirmed: bool = False) -> dict[str, Any]:
    if error := _require_confirmation(confirmed):
        return error
    try:
        client = get_write_client()
        template = client.item_template("note")
        template["note"] = note_html
        return _ok(result=client.create_items([template], item_key))
    except Exception as exc:
        return _error(str(exc))


def zotero_update_note(note_key: str, note_html: str, confirmed: bool = False) -> dict[str, Any]:
    if error := _require_confirmation(confirmed):
        return error
    try:
        client = get_write_client()
        note = client.item(note_key)
        note["data"]["note"] = note_html
        return _ok(updated=bool(client.update_item(note)))
    except Exception as exc:
        return _error(str(exc))


def zotero_add_tags(item_key: str, tags: list[str], confirmed: bool = False) -> dict[str, Any]:
    if error := _require_confirmation(confirmed):
        return error
    try:
        client = get_write_client()
        item = client.item(item_key)
        existing = {tag.get("tag") for tag in item["data"].get("tags", [])}
        added = [tag.strip() for tag in tags if tag.strip() and tag.strip() not in existing]
        item["data"]["tags"] = item["data"].get("tags", []) + [{"tag": tag} for tag in added]
        return _ok(updated=bool(client.update_item(item)), added=added)
    except Exception as exc:
        return _error(str(exc))


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "zotero_search",
            "description": "在全库或指定 Zotero 目录中检索顶层文献条目",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "item_type": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                    "collection": {"type": "string", "description": "目录 key、精确名称或完整路径"},
                    "recursive": {"type": "boolean", "default": False},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero_list_collections",
            "description": "列出或模糊筛选 Zotero 目录，并返回完整路径和父目录",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero_find_collection",
            "description": "把目录 key、精确名称或完整路径解析为唯一目录；歧义时拒绝猜测",
            "parameters": {
                "type": "object",
                "properties": {"name_or_path": {"type": "string"}},
                "required": ["name_or_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero_get_collection_items",
            "description": "获取指定目录内的顶层文献，可选择包含全部子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "collection": {"type": "string"},
                    "recursive": {"type": "boolean", "default": False},
                    "limit": {"type": "integer", "default": 200},
                    "item_type": {"type": "string"},
                },
                "required": ["collection"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero_get_item",
            "description": "读取条目元数据和所在目录路径",
            "parameters": {"type": "object", "properties": {"item_key": {"type": "string"}}, "required": ["item_key"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero_get_children",
            "description": "读取条目的附件和笔记",
            "parameters": {"type": "object", "properties": {"item_key": {"type": "string"}}, "required": ["item_key"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero_read_pdf_text",
            "description": "分段读取 PDF 全文；若 hasMore=true，使用 nextStart 继续",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_key": {"type": "string"},
                    "start": {"type": "integer", "default": 0},
                    "max_chars": {"type": "integer", "default": 12000},
                    "attachment_key": {"type": "string"},
                },
                "required": ["item_key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zotero_get_annotations",
            "description": "读取一个条目全部 PDF 附件中的 Zotero 原生批注",
            "parameters": {"type": "object", "properties": {"item_key": {"type": "string"}}, "required": ["item_key"]},
        },
    },
]


TOOL_DISPATCH = {
    "zotero_search": zotero_search,
    "zotero_list_collections": zotero_list_collections,
    "zotero_find_collection": zotero_find_collection,
    "zotero_get_collection_items": zotero_get_collection_items,
    "zotero_get_item": zotero_get_item,
    "zotero_get_children": zotero_get_children,
    "zotero_read_pdf_text": zotero_read_pdf_text,
    "zotero_get_annotations": zotero_get_annotations,
}
