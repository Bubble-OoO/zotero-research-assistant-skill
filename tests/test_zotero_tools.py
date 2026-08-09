import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import zotero_tools as tools


def collection(key, name, parent=""):
    return {"data": {"key": key, "name": name, "parentCollection": parent}}


def item(key, title, item_type="journalArticle", collections=None):
    return {
        "data": {
            "key": key,
            "title": title,
            "itemType": item_type,
            "creators": [{"firstName": "Ada", "lastName": "Lovelace"}],
            "collections": collections or [],
            "tags": [],
        }
    }


class FakeClient:
    def __init__(self):
        self._collections = [
            collection("ROOT0001", "人机交互"),
            collection("CHILD001", "方法", "ROOT0001"),
            collection("ROOT0002", "另一项目"),
            collection("CHILD002", "方法", "ROOT0002"),
        ]
        self._items = {
            "ROOT0001": [
                item("PAPER001", "Direct paper", collections=["ROOT0001"]),
                item("ATTACH01", "PDF", "attachment", ["ROOT0001"]),
            ],
            "CHILD001": [
                item("PAPER002", "Nested paper", collections=["CHILD001"]),
                item("PAPER001", "Direct paper", collections=["ROOT0001", "CHILD001"]),
            ],
            "ROOT0002": [],
            "CHILD002": [],
        }

    @staticmethod
    def _page(values, limit, start):
        return values[start : start + limit]

    def collections(self, limit=25, start=0, **kwargs):
        return self._page(self._collections, limit, start)

    def collection_items_top(self, key, limit=25, start=0, **kwargs):
        values = self._items[key]
        query = kwargs.get("q")
        if query:
            values = [value for value in values if query.casefold() in value["data"]["title"].casefold()]
        return self._page(values, limit, start)

    def top(self, limit=25, start=0, **kwargs):
        values = [item("GLOBAL01", "Global result")]
        return self._page(values, limit, start)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.patcher = patch.object(tools, "get_read_client", return_value=self.client)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_exact_collection_path(self):
        result = tools.zotero_find_collection("人机交互/方法")
        self.assertTrue(result["ok"])
        self.assertEqual(result["collection"]["key"], "CHILD001")

    def test_duplicate_collection_name_is_ambiguous(self):
        result = tools.zotero_find_collection("方法")
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "ambiguous_collection")
        self.assertEqual(len(result["matches"]), 2)

    def test_recursive_collection_items_are_bibliographic_and_deduplicated(self):
        result = tools.zotero_get_collection_items("人机交互", recursive=True)
        self.assertTrue(result["ok"])
        self.assertEqual(
            {entry["key"] for entry in result["items"]},
            {"PAPER001", "PAPER002", "ATTACH01"},
        )
        standalone = next(entry for entry in result["items"] if entry["key"] == "ATTACH01")
        self.assertTrue(standalone["standaloneAttachment"])
        self.assertEqual(result["searchedCollectionCount"], 2)
        direct = next(entry for entry in result["items"] if entry["key"] == "PAPER001")
        self.assertEqual(
            direct["matchedCollectionPaths"],
            ["人机交互", "人机交互/方法"],
        )

    def test_search_inside_collection_does_not_use_global_results(self):
        result = tools.zotero_search("Nested", collection="人机交互", recursive=True)
        self.assertTrue(result["ok"])
        self.assertEqual([entry["key"] for entry in result["items"]], ["PAPER002"])


class WriteSafetyTests(unittest.TestCase):
    def test_write_requires_confirmation_before_client_is_opened(self):
        with patch.object(tools, "get_write_client") as get_client:
            result = tools.zotero_add_tags("PAPER001", ["reviewed"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["code"], "confirmation_required")
        get_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
