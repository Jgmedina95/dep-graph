from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import threading
from pathlib import Path
from typing import Protocol

from src.env_utils import load_env_file
from src.openrouter_client import OpenRouterClient
from src.tool_index_contract import (
    ALLOWED_CLASSIFICATIONS,
    ALLOWED_KINDS,
    contract_markdown,
    validate_normalized_tool,
    validate_tool_index,
)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = ROOT / ".env"
DEFAULT_INPUT_PATH = ROOT / "googlesuper_tools.json"
DEFAULT_OUTPUT_PATH = ROOT / "tool_index.json"
DEFAULT_SYSTEM_PROMPT_PATH = ROOT / "prompts" / "tool_schema_system.md"
DEFAULT_USER_PROMPT_PATH = ROOT / "prompts" / "tool_schema_user.md"
DEFAULT_MODEL = "openai/gpt-4.1-mini"
DEFAULT_MAX_WORKERS = min(16, max(4, (os.cpu_count() or 4) * 2))


class ChatClient(Protocol):
    def complete(self, system_prompt: str, user_prompt: str, model: str) -> str: ...


class ProgressBar:
    def __init__(self, total: int, enabled: bool = True) -> None:
        self.total = total
        self.enabled = enabled and total > 0
        self.completed = 0
        self._lock = threading.Lock()

    def update(self, label: str = "") -> None:
        if not self.enabled:
            return

        with self._lock:
            self.completed += 1
            width = 28
            ratio = self.completed / self.total
            filled = int(width * ratio)
            bar = "#" * filled + "-" * (width - filled)
            suffix = f" {label}" if label else ""
            sys.stderr.write(f"\r[{bar}] {self.completed}/{self.total}{suffix}")
            sys.stderr.flush()
            if self.completed == self.total:
                sys.stderr.write("\n")


def normalize_kind(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in ALLOWED_KINDS:
        return lowered
    if "email" in lowered:
        return "email"
    if lowered in {"id", "integer", "int", "number", "uuid", "identifier"}:
        return "identifier"
    if "token" in lowered:
        return "token"
    if "url" in lowered or "uri" in lowered:
        return "url"
    if lowered in {"display_name", "name", "enum", "method"}:
        return "name"
    return "unknown"


def normalize_classification(value: str, required: bool) -> str:
    lowered = value.strip().lower()
    if lowered in ALLOWED_CLASSIFICATIONS:
        return lowered
    if lowered in {"direct_user_input", "manual_input", "provided_by_user"}:
        return "user_input"
    if lowered in {"derived", "tool_output", "dependency"}:
        return "tool_derived"
    if lowered in {"context", "request_context", "filter", "pagination", "config"}:
        return "optional_context"
    return "ambiguous" if required else "optional_context"


def sanitize_normalized_tool(normalized_tool: dict) -> dict:
    for field_group in ("required_inputs", "optional_inputs", "output_fields"):
        for field in normalized_tool.get(field_group, []):
            if "kind" in field and isinstance(field["kind"], str):
                field["kind"] = normalize_kind(field["kind"])
            if field_group != "output_fields" and "classification" in field and isinstance(field["classification"], str):
                field["classification"] = normalize_classification(field["classification"], bool(field.get("required")))
    return normalized_tool


def repair_tool_response(
    raw_tool: dict,
    invalid_response_text: str,
    validation_error: Exception,
    client: ChatClient,
    model: str,
    system_template: str,
) -> dict:
    repair_system_prompt = system_template.format(schema_contract=contract_markdown())
    repair_user_prompt = (
        "The previous normalization output violated the contract. Repair it and return only one corrected JSON object.\n\n"
        f"Validation error:\n{validation_error}\n\n"
        "Raw tool JSON:\n"
        f"{json.dumps(raw_tool, indent=2)}\n\n"
        "Previous invalid normalized JSON:\n"
        f"{invalid_response_text}\n"
    )
    repaired_text = client.complete(repair_system_prompt, repair_user_prompt, model)
    repaired_tool = json.loads(strip_json_fence(repaired_text))
    return sanitize_normalized_tool(repaired_tool)


def strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def render_prompts(system_template: str, user_template: str, raw_tool: dict) -> tuple[str, str]:
    system_prompt = system_template.format(schema_contract=contract_markdown())
    user_prompt = user_template.format(raw_tool_json=json.dumps(raw_tool, indent=2), schema_contract=contract_markdown())
    return system_prompt, user_prompt


def normalize_tool(raw_tool: dict, client: ChatClient, model: str, system_template: str, user_template: str) -> dict:
    system_prompt, user_prompt = render_prompts(system_template, user_template, raw_tool)
    response_text = client.complete(system_prompt=system_prompt, user_prompt=user_prompt, model=model)
    normalized_tool = sanitize_normalized_tool(json.loads(strip_json_fence(response_text)))
    try:
        validated = validate_normalized_tool(normalized_tool)
    except Exception as exc:
        repaired_tool = repair_tool_response(raw_tool, response_text, exc, client, model, system_template)
        validated = validate_normalized_tool(repaired_tool)
    if validated["slug"] != raw_tool["slug"]:
        raise ValueError(f"Normalized slug mismatch: expected {raw_tool['slug']}, got {validated['slug']}")
    return validated


def normalize_tools(
    raw_tools: list[dict],
    client: ChatClient,
    model: str,
    system_template: str,
    user_template: str,
    max_workers: int = 1,
    show_progress: bool = False,
) -> list[dict]:
    if max_workers <= 1:
        progress = ProgressBar(total=len(raw_tools), enabled=show_progress)
        normalized_tools = []
        for tool in raw_tools:
            normalized_tools.append(normalize_tool(tool, client, model, system_template, user_template))
            progress.update(tool["slug"])

        return validate_tool_index(normalized_tools)

    progress = ProgressBar(total=len(raw_tools), enabled=show_progress)
    normalized_tools: list[dict | None] = [None] * len(raw_tools)

    def worker(index_and_tool: tuple[int, dict]) -> tuple[int, dict]:
        index, tool = index_and_tool
        normalized_tool = normalize_tool(tool, client, model, system_template, user_template)
        return index, normalized_tool

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(worker, (index, tool)): (index, tool["slug"])
            for index, tool in enumerate(raw_tools)
        }

        for future in concurrent.futures.as_completed(futures):
            index, slug = futures[future]
            completed_index, normalized_tool = future.result()
            if completed_index != index:
                raise ValueError(f"Worker index mismatch for {slug}: expected {index}, got {completed_index}")
            normalized_tools[index] = normalized_tool
            progress.update(slug)

    finalized_tools = [tool for tool in normalized_tools if tool is not None]
    if len(finalized_tools) != len(raw_tools):
        raise ValueError("Parallel normalization did not produce a result for every input tool")

    return validate_tool_index(finalized_tools)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a normalized tool index using OpenRouter")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--system-prompt", type=Path, default=DEFAULT_SYSTEM_PROMPT_PATH)
    parser.add_argument("--user-prompt", type=Path, default=DEFAULT_USER_PROMPT_PATH)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_PATH)
    parser.add_argument("--max-tools", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=DEFAULT_MAX_WORKERS)
    parser.add_argument("--no-progress", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    load_env_file(args.env_file)

    raw_tools = json.loads(args.input.read_text())
    if args.max_tools is not None:
        raw_tools = raw_tools[: args.max_tools]

    system_template = args.system_prompt.read_text()
    user_template = args.user_prompt.read_text()
    client = OpenRouterClient()

    normalized_tools = normalize_tools(
        raw_tools,
        client,
        args.model,
        system_template,
        user_template,
        max_workers=max(1, args.max_workers),
        show_progress=not args.no_progress,
    )
    args.output.write_text(json.dumps(normalized_tools, indent=2), encoding="utf-8")

    print(f"Wrote normalized tool index with {len(normalized_tools)} tools to {args.output.name}")


if __name__ == "__main__":
    main()