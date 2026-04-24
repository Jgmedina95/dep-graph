from __future__ import annotations

import json
import unittest
from pathlib import Path

from src.build_graph_from_index import build_relationships, build_simple_relationships
from src.tool_index_contract import validate_tool_index


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class GraphFromIndexTest(unittest.TestCase):
    def test_builds_expected_thread_dependency(self) -> None:
        tool_index = validate_tool_index(json.loads((FIXTURES / "expected_normalized_subset.json").read_text()))
        relationships = build_relationships(tool_index)
        simple_relationships = build_simple_relationships(relationships)

        rich_match = next(
            item
            for item in relationships
            if item["source"] == "GOOGLESUPER_LIST_THREADS" and item["target"] == "GOOGLESUPER_DELETE_THREAD"
        )
        self.assertEqual(rich_match["parameter"], "thread_id")
        self.assertEqual(rich_match["entity"], "thread")
        self.assertGreaterEqual(rich_match["confidence"], 1.0)

        simple_match = next(
            item
            for item in simple_relationships
            if item["source"] == "GOOGLESUPER_LIST_THREADS" and item["target"] == "GOOGLESUPER_DELETE_THREAD"
        )
        self.assertEqual(simple_match["parameters"], ["thread_id"])


if __name__ == "__main__":
    unittest.main()