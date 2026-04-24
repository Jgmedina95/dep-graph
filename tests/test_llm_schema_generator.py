from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from src.generate_tool_index_with_llm import normalize_tools, render_prompts
from src.openrouter_client import OpenRouterClient
from src.tool_index_contract import validate_tool_index


FIXTURES = Path(__file__).resolve().parent / "fixtures"
PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


class FakeClient:
    def __init__(self, responses_by_slug: dict[str, dict]) -> None:
        self.responses_by_slug = responses_by_slug
        self.calls: list[dict[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str, model: str) -> str:
        self.calls.append({"system": system_prompt, "user": user_prompt, "model": model})
        for slug, payload in self.responses_by_slug.items():
            if slug in user_prompt:
                return json.dumps(payload)
        raise AssertionError("No fake response found for tool in prompt")


class SchemaGeneratorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_tools = json.loads((FIXTURES / "raw_tool_subset.json").read_text())
        self.expected = json.loads((FIXTURES / "expected_normalized_subset.json").read_text())
        self.system_template = (PROMPTS / "tool_schema_system.md").read_text()
        self.user_template = (PROMPTS / "tool_schema_user.md").read_text()

    def test_prompt_render_includes_contract_and_raw_json(self) -> None:
        system_prompt, user_prompt = render_prompts(self.system_template, self.user_template, self.raw_tools[0])
        self.assertIn("Normalized tool index contract", system_prompt)
        self.assertIn(self.raw_tools[0]["slug"], user_prompt)
        self.assertIn("Raw tool JSON", user_prompt)

    def test_fake_llm_normalization_matches_contract(self) -> None:
        fake_client = FakeClient({tool["slug"]: tool for tool in self.expected})
        normalized_tools = normalize_tools(
            self.raw_tools,
            fake_client,
            model="fake/model",
            system_template=self.system_template,
            user_template=self.user_template,
        )
        validate_tool_index(normalized_tools)
        self.assertEqual([tool["slug"] for tool in normalized_tools], [tool["slug"] for tool in self.expected])
        delete_thread = next(tool for tool in normalized_tools if tool["slug"] == "GOOGLESUPER_DELETE_THREAD")
        self.assertEqual(delete_thread["required_inputs"][0]["canonical_name"], "thread_id")
        self.assertEqual(delete_thread["required_inputs"][0]["classification"], "tool_derived")

    def test_parallel_fake_llm_normalization_processes_each_tool_once(self) -> None:
        fake_client = FakeClient({tool["slug"]: tool for tool in self.expected})
        normalized_tools = normalize_tools(
            self.raw_tools,
            fake_client,
            model="fake/model",
            system_template=self.system_template,
            user_template=self.user_template,
            max_workers=3,
            show_progress=False,
        )

        validate_tool_index(normalized_tools)
        self.assertEqual(len(normalized_tools), len(self.raw_tools))
        self.assertEqual(len(fake_client.calls), len(self.raw_tools))
        self.assertEqual(
            sorted(tool["slug"] for tool in normalized_tools),
            sorted(tool["slug"] for tool in self.expected),
        )


@unittest.skipUnless(
    os.environ.get("RUN_OPENROUTER_LIVE_TESTS") == "1" and os.environ.get("OPENROUTER_API_KEY"),
    "Set RUN_OPENROUTER_LIVE_TESTS=1 and OPENROUTER_API_KEY to run live OpenRouter normalization tests.",
)
class LiveSchemaGeneratorTest(unittest.TestCase):
    def test_openrouter_normalizes_subset(self) -> None:
        raw_tools = json.loads((FIXTURES / "raw_tool_subset.json").read_text())[:2]
        system_template = (PROMPTS / "tool_schema_system.md").read_text()
        user_template = (PROMPTS / "tool_schema_user.md").read_text()

        normalized_tools = normalize_tools(
            raw_tools,
            OpenRouterClient(),
            model="openai/gpt-4.1-mini",
            system_template=system_template,
            user_template=user_template,
        )

        validate_tool_index(normalized_tools)
        by_slug = {tool["slug"]: tool for tool in normalized_tools}

        self.assertEqual(by_slug["GOOGLESUPER_LIST_THREADS"]["operation_type"], "list")
        self.assertEqual(by_slug["GOOGLESUPER_LIST_THREADS"]["primary_entity"], "thread")
        self.assertTrue(
            any(field["canonical_name"] == "thread_id" for field in by_slug["GOOGLESUPER_LIST_THREADS"]["output_fields"])
        )

        delete_thread = by_slug["GOOGLESUPER_DELETE_THREAD"]
        self.assertEqual(delete_thread["required_inputs"][0]["canonical_name"], "thread_id")
        self.assertEqual(delete_thread["required_inputs"][0]["classification"], "tool_derived")


if __name__ == "__main__":
    unittest.main()