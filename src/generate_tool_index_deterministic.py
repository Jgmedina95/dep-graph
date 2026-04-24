from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from src.tool_index_contract import validate_tool_index


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = ROOT / "github_tools.json"
DEFAULT_OUTPUT_PATH = ROOT / "github_tool_index.json"

OPERATION_ALIASES = {
    "ADD": "add",
    "APPROVE": "approve",
    "ARCHIVE": "archive",
    "ASSIGN": "assign",
    "ABORT": "abort",
    "CANCEL": "cancel",
    "CHECK": "check",
    "CLEAR": "clear",
    "CLOSE": "close",
    "CONVERT": "convert",
    "CREATE": "create",
    "DECLINE": "decline",
    "DELETE": "delete",
    "DISABLE": "disable",
    "DISMISS": "dismiss",
    "DOWNLOAD": "download",
    "ENABLE": "enable",
    "FIND": "find",
    "FOLLOW": "follow",
    "FORK": "fork",
    "GENERATE": "generate",
    "GET": "get",
    "LIST": "list",
    "LOOKUP": "lookup",
    "MARK": "mark",
    "MERGE": "merge",
    "MOVE": "move",
    "REMOVE": "remove",
    "REOPEN": "reopen",
    "REQUEST": "request",
    "REVIEW": "review",
    "RESTORE": "restore",
    "SEARCH": "search",
    "SET": "set",
    "START": "start",
    "SUBMIT": "submit",
    "SYNC": "sync",
    "TRANSFER": "transfer",
    "UNARCHIVE": "unarchive",
    "UNASSIGN": "unassign",
    "UNFOLLOW": "unfollow",
    "UNLOCK": "unlock",
    "UNPIN": "unpin",
    "UPDATE": "update",
    "UPLOAD": "upload",
}

ENTITY_HINTS = [
    ("pull request", "pull_request", "github"),
    ("pull requests", "pull_request", "github"),
    ("repository migration", "repository_migration", "github"),
    ("repository ruleset", "repository_ruleset", "github"),
    ("ruleset", "ruleset", "github"),
    ("deployment protection rule", "deployment_protection_rule", "github"),
    ("branch protection rule", "branch_protection_rule", "github"),
    ("discussion comment", "discussion_comment", "github"),
    ("discussion", "discussion", "github"),
    ("issue comment", "issue_comment", "github"),
    ("issue", "issue", "github"),
    ("label", "label", "github"),
    ("milestone", "milestone", "github"),
    ("release", "release", "github"),
    ("repository", "repository", "github"),
    ("repo", "repository", "github"),
    ("organization", "organization", "github"),
    ("org", "organization", "github"),
    ("team", "team", "github"),
    ("member", "member", "github"),
    ("user", "user", "github"),
    ("gist", "gist", "github"),
    ("project", "project", "github"),
    ("project item", "project_item", "github"),
    ("project field", "project_field", "github"),
    ("workflow run", "workflow_run", "github"),
    ("workflow", "workflow", "github"),
    ("commit", "commit", "github"),
    ("check run", "check_run", "github"),
    ("check suite", "check_suite", "github"),
    ("review", "review", "github"),
    ("reaction", "reaction", "github"),
    ("comment", "comment", "github"),
    ("migration", "migration", "github"),
    ("secret", "secret", "github"),
    ("variable", "variable", "github"),
    ("code scanning alert", "code_scanning_alert", "github"),
    ("alert", "alert", "github"),
    ("notification", "notification", "github"),
]

OPTIONAL_CONTEXT_PREFIXES = (
    "per_page",
    "page",
    "sort",
    "direction",
    "since",
    "before",
    "after",
    "include",
    "exclude",
)

OPTIONAL_CONTEXT_FIELDS = {
    "cursor",
    "first",
    "last",
    "order_by",
    "page_size",
    "query",
    "state",
    "visibility",
}

USER_INPUT_FIELDS = {
    "body",
    "comment",
    "content",
    "message",
    "name",
    "query",
    "text",
    "title",
}


def snake_case(value: str) -> str:
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value)
    return value.strip("_").lower()


def singularize(value: str) -> str:
    if value.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"
    if value.endswith("ses") and len(value) > 3:
        return value[:-2]
    if value.endswith("s") and not value.endswith("ss") and len(value) > 3:
        return value[:-1]
    return value


def normalize_entity_name(value: str | None) -> str:
    if not value:
        return "resource"
    return singularize(snake_case(value))


def infer_entity(text: str, fallback: str | None = None) -> tuple[str, str]:
    lowered = f" {snake_case(text).replace('_', ' ')} "
    for term, entity, domain in ENTITY_HINTS:
        normalized_term = f" {snake_case(term).replace('_', ' ')} "
        if normalized_term in lowered:
            return entity, domain
    return normalize_entity_name(fallback), "github"


def infer_operation_type(slug: str) -> str:
    parts = slug.split("_")[1:]
    if not parts:
        return "unknown"
    return OPERATION_ALIASES.get(parts[0], snake_case(parts[0]))


def infer_primary_entity(tool: dict) -> tuple[str, str]:
    parts = tool["slug"].split("_")[2:]
    entity, domain = infer_entity(" ".join(parts + [tool["name"], tool.get("description", "")]), fallback=parts[0] if parts else None)
    return entity, domain


def infer_value_kind(name: str, description: str = "") -> str:
    lowered_name = snake_case(name)
    lowered_description = description.lower()
    if lowered_name.endswith("_id") or lowered_name in {"id", "number", "node_id"} or " id" in lowered_description:
        return "identifier"
    if "email" in lowered_name or "email" in lowered_description:
        return "email"
    if "token" in lowered_name:
        return "token"
    if lowered_name.endswith("_url") or lowered_name == "url" or "url" in lowered_description:
        return "url"
    if lowered_name.endswith("_name") or lowered_name in {"name", "title", "login"}:
        return "name"
    return "unknown"


def infer_field_entity(name: str, description: str, fallback: str) -> str:
    normalized_name = snake_case(name)
    if normalized_name.endswith("_id"):
        return normalize_entity_name(normalized_name[:-3])
    if normalized_name.endswith("_number"):
        return normalize_entity_name(normalized_name[:-7])
    if normalized_name == "id":
        entity, _ = infer_entity(description, fallback=fallback)
        return entity
    entity, _ = infer_entity(f"{name} {description}", fallback=fallback)
    return entity


def canonicalize_field_name(name: str, entity: str, kind: str) -> str:
    canonical = snake_case(name)
    if kind == "email":
        return "email"
    if kind == "name" and canonical in {"name", "title", "login"}:
        return f"{entity}_name" if entity != "resource" else canonical
    if kind == "identifier":
        if canonical == "id":
            return f"{entity}_id" if entity != "resource" else "id"
        if canonical == "number":
            return f"{entity}_number" if entity != "resource" else "number"
        if canonical.endswith("id") and "_" not in canonical and canonical != "id":
            return f"{canonical[:-2]}_id"
    return canonical


def classify_input(canonical_name: str, kind: str, description: str, required: bool, entity: str) -> str:
    lowered_description = description.lower()
    if not required:
        if canonical_name.startswith(OPTIONAL_CONTEXT_PREFIXES) or canonical_name in OPTIONAL_CONTEXT_FIELDS:
            return "optional_context"
        if canonical_name in USER_INPUT_FIELDS:
            return "user_input"
        return "optional_context"

    if canonical_name in {"owner", "repo", "repository", "organization", "org", "username", "user"}:
        return "user_input"
    if canonical_name in USER_INPUT_FIELDS:
        return "user_input"
    if kind == "email":
        return "user_input"
    if kind == "identifier":
        if canonical_name in {"repository_id", "organization_id", "user_id", "issue_number", "pull_request_number"}:
            return "either"
        return "tool_derived"
    if "query" in canonical_name or "search" in lowered_description:
        return "user_input"
    if entity in {"organization", "repository", "user"}:
        return "user_input"
    return "ambiguous"


def resolve_ref(schema: dict, defs: dict) -> dict:
    ref = schema.get("$ref")
    if not ref:
        return schema
    ref_name = ref.split("/")[-1]
    return defs.get(ref_name, {})


def collect_output_fields(tool: dict, output_schema: dict) -> list[dict]:
    defs = output_schema.get("$defs", {})
    results: list[dict] = []

    def walk(schema: dict, path: str, context_entity: str, context_label: str, seen_refs: set[tuple[str, str]]) -> None:
        if not schema:
            return

        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            ref_key = (path, ref_name)
            if ref_key in seen_refs:
                return
            walk(defs.get(ref_name, {}), path, infer_entity(ref_name, context_entity)[0], ref_name, seen_refs | {ref_key})
            return

        if "anyOf" in schema:
            for item in schema["anyOf"]:
                walk(item, path, context_entity, context_label, seen_refs)
            return

        if "oneOf" in schema:
            for item in schema["oneOf"]:
                walk(item, path, context_entity, context_label, seen_refs)
            return

        if schema.get("type") == "array":
            items = schema.get("items", {})
            item_entity = infer_entity(f"{context_label} {items.get('title', '')}", singularize(context_entity))[0]
            walk(items, f"{path}[]", item_entity, items.get("title", context_label), seen_refs)
            return

        properties = schema.get("properties", {})
        if properties:
            current_entity = infer_entity(f"{schema.get('title', '')} {context_label}", context_entity)[0]
            for prop_name, prop_schema in properties.items():
                if prop_name in {"error", "errors", "successful", "extensions"}:
                    continue
                prop_path = f"{path}.{prop_name}" if path else prop_name
                prop_description = prop_schema.get("description", "")
                prop_entity = infer_field_entity(prop_name, f"{prop_schema.get('title', '')} {prop_description}", current_entity)
                if prop_schema.get("type") == "array":
                    items = prop_schema.get("items", {})
                    item_entity = infer_entity(f"{prop_name} {items.get('title', '')}", singularize(prop_entity))[0]
                    walk(items, f"{prop_path}[]", item_entity, prop_name, seen_refs)
                    continue
                if prop_schema.get("type") == "object" or "$ref" in prop_schema or prop_schema.get("properties"):
                    walk(prop_schema, prop_path, prop_entity, prop_name, seen_refs)
                    continue
                kind = infer_value_kind(prop_name, prop_description)
                results.append(
                    {
                        "raw_name": prop_name,
                        "canonical_name": canonicalize_field_name(prop_name, prop_entity, kind),
                        "entity": prop_entity,
                        "kind": kind,
                        "description": prop_description,
                        "path": prop_path,
                    }
                )

    walk(output_schema, "$", tool["primary_entity"], tool["name"], set())

    deduped: dict[tuple[str, str], dict] = {}
    for field in results:
        key = (field["path"], field["canonical_name"])
        deduped[key] = field
    return list(deduped.values())


def build_tool_index(raw_tools: list[dict]) -> list[dict]:
    normalized_tools: list[dict] = []

    for raw_tool in raw_tools:
        primary_entity, domain = infer_primary_entity(raw_tool)
        tool = {
            "slug": raw_tool["slug"],
            "name": raw_tool["name"],
            "description": raw_tool.get("description", ""),
            "tags": raw_tool.get("tags", []),
            "is_deprecated": raw_tool.get("is_deprecated", False),
            "operation_type": infer_operation_type(raw_tool["slug"]),
            "primary_entity": primary_entity,
            "domain": domain,
            "required_inputs": [],
            "optional_inputs": [],
            "output_fields": [],
        }

        input_schema = raw_tool.get("input_parameters", {})
        required_names = set(input_schema.get("required", []))
        for field_name, field_schema in input_schema.get("properties", {}).items():
            description = field_schema.get("description", "")
            entity = infer_field_entity(field_name, description, primary_entity)
            kind = infer_value_kind(field_name, description)
            normalized_field = {
                "name": field_name,
                "canonical_name": canonicalize_field_name(field_name, entity, kind),
                "entity": entity,
                "kind": kind,
                "required": field_name in required_names,
                "description": description,
                "input_path": f"$.input_parameters.properties.{field_name}",
                "classification": classify_input(
                    canonicalize_field_name(field_name, entity, kind),
                    kind,
                    description,
                    field_name in required_names,
                    entity,
                ),
            }
            if normalized_field["required"]:
                tool["required_inputs"].append(normalized_field)
            else:
                tool["optional_inputs"].append(normalized_field)

        tool["output_fields"] = collect_output_fields(tool, raw_tool.get("output_parameters", {}))
        normalized_tools.append(tool)

    return validate_tool_index(normalized_tools)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a normalized tool index deterministically from raw tool JSON")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_tools = json.loads(args.input.read_text())
    normalized_tools = build_tool_index(raw_tools)
    args.output.write_text(json.dumps(normalized_tools, indent=2), encoding="utf-8")
    print(f"Wrote normalized tool index with {len(normalized_tools)} tools to {args.output.name}")


if __name__ == "__main__":
    main()