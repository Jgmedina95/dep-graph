from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = ROOT / "googlesuper_tools.json"
DEFAULT_TOOL_INDEX_PATH = ROOT / "googlesuper_tool_index.json"
DEFAULT_RELATIONSHIP_PATH = ROOT / "googlesuper_relationships.json"
DEFAULT_SIMPLE_RELATIONSHIP_PATH = ROOT / "googlesuper_relationships_simple.json"

OPERATION_TOKENS = {
    "ACL",
    "ADD",
    "AGGREGATE",
    "APPEND",
    "AUTOCOMPLETE",
    "BATCH",
    "CALENDAR",
    "CALENDARS",
    "CHANNELS",
    "CHECK",
    "CLEAR",
    "COLORS",
    "COPY",
    "CREATE",
    "DELETE",
    "DOWNLOAD",
    "EMPTY",
    "EVENTS",
    "EXECUTE",
    "EXPORT",
    "FETCH",
    "FIND",
    "FREE",
    "GENERATE",
    "GEOCODE",
    "GET",
    "IMPORT",
    "INSERT",
    "LIST",
    "LOOKUP",
    "MODIFY",
    "MOVE",
    "MUTATE",
    "PATCH",
    "PLACE",
    "PRESENTATIONS",
    "QUERY",
    "REPLACE",
    "RUN",
    "SEARCH",
    "SEND",
    "SET",
    "SETTINGS",
    "SPREADSHEETS",
    "STOP",
    "UNTRASH",
    "UPDATE",
    "UPLOAD",
    "VALUES",
    "WATCH",
}

PRODUCER_OPERATIONS = {
    "aggregate",
    "autocomplete",
    "check",
    "copy",
    "create",
    "fetch",
    "find",
    "generate",
    "geocode",
    "get",
    "import",
    "list",
    "lookup",
    "place",
    "query",
    "run",
    "search",
    "upload",
}

DISCOVERY_OPERATIONS = {
    "fetch",
    "find",
    "get",
    "list",
    "lookup",
    "query",
    "search",
}

DESTRUCTIVE_OPERATIONS = {
    "clear",
    "delete",
    "empty",
    "stop",
    "trash",
}

USER_INPUT_FIELDS = {
    "body",
    "content",
    "description",
    "html",
    "instructions",
    "message",
    "prompt",
    "q",
    "query",
    "raw",
    "sql",
    "subject",
    "text",
    "title",
}

OPTIONAL_CONTEXT_PREFIXES = (
    "include_",
    "max_",
    "min_",
    "order_",
    "page_",
    "show_",
    "sort_",
    "supports_",
    "time_",
    "use_",
)

OPTIONAL_CONTEXT_FIELDS = {
    "fields",
    "format",
    "pretty_print",
    "single_events",
    "updated_min",
    "verbose",
}

ENTITY_RULES = [
    (("acl", "access control"), "acl_rule", "calendar"),
    (("channel", "channels"), "channel", "calendar"),
    (("setting", "settings"), "setting", "calendar"),
    (("theme", "themes"), "theme", "drive"),
    (("thread", "threads"), "thread", "gmail"),
    (("message", "messages", "gmail"), "message", "gmail"),
    (("draft", "drafts"), "draft", "gmail"),
    (("attendee", "attendees"), "attendee", "calendar"),
    (("organizer", "organizers"), "organizer", "calendar"),
    (("creator", "creators"), "creator", "calendar"),
    (("user", "users"), "user", "generic"),
    (("label", "labels"), "label", "gmail"),
    (("event", "events"), "event", "calendar"),
    (("calendar", "calendars"), "calendar", "calendar"),
    (("filter", "filters"), "filter", "gmail"),
    (("file", "files", "drive"), "file", "drive"),
    (("folder", "folders"), "folder", "drive"),
    (("permission", "permissions"), "permission", "drive"),
    (("revision", "revisions"), "revision", "drive"),
    (("comment", "comments"), "comment", "drive"),
    (("reply", "replies"), "reply", "drive"),
    (("document", "documents", "googledocs"), "document", "docs"),
    (("spreadsheet", "spreadsheets"), "spreadsheet", "sheets"),
    (("sheet", "sheets", "googlesheets"), "sheet", "sheets"),
    (("presentation", "presentations", "slides"), "presentation", "slides"),
    (("audience", "audiences"), "audience", "analytics"),
    (("property", "properties"), "property", "analytics"),
    (("report", "reports", "reporting"), "report", "analytics"),
    (("metric", "metrics"), "metric", "analytics"),
    (("dimension", "dimensions"), "dimension", "analytics"),
    (("contact", "contacts"), "contact", "people"),
    (("task", "tasks"), "task", "tasks"),
    (("place", "places"), "place", "geospatial"),
    (("geocode", "geocoding", "address"), "location", "geospatial"),
    (("drive", "team drive"), "drive", "drive"),
]

DOMAIN_TAGS = {
    "gmail": "gmail",
    "drive": "drive",
    "googledocs": "docs",
    "googlesheets": "sheets",
    "presentations": "slides",
    "Events Management": "calendar",
    "Calendars Management": "calendar",
    "reporting": "analytics",
    "Reporting": "analytics",
    "audiences": "analytics",
    "Audience Management": "analytics",
    "Geocoding & geolocation": "geospatial",
    "Places search & details": "geospatial",
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


def infer_entity(text: str, fallback: str | None = None) -> tuple[str, str | None]:
    lowered = f" {snake_case(text).replace('_', ' ')} "
    for terms, entity, domain in ENTITY_RULES:
        if any(f" {snake_case(term).replace('_', ' ')} " in lowered for term in terms):
            return entity, domain
    return normalize_entity_name(fallback), None


def infer_tool_domain(tool: dict, primary_entity: str) -> str:
    for tag in tool.get("tags", []):
        if tag in DOMAIN_TAGS:
            return DOMAIN_TAGS[tag]
    _, domain = infer_entity(" ".join([tool["slug"], tool["name"], tool.get("description", "")]), fallback=primary_entity)
    return domain or "generic"


def infer_operation_type(slug: str) -> str:
    parts = slug.split("_")[1:]
    for part in parts:
        if part in OPERATION_TOKENS:
            return snake_case(part)
    return snake_case(parts[0]) if parts else "unknown"


def infer_primary_entity(tool: dict) -> str:
    parts = [part for part in tool["slug"].split("_")[1:] if part not in OPERATION_TOKENS]
    entity, _ = infer_entity(" ".join(parts + [tool["name"]]))
    return entity


def infer_field_entity(name: str, description: str, fallback: str, context_label: str = "") -> str:
    normalized_name = snake_case(name)
    if normalized_name.endswith("_id"):
        prefix = normalized_name[:-3]
        if prefix not in {"rule"}:
            return normalize_entity_name(prefix)

    if normalized_name == "id":
        entity, _ = infer_entity(description, fallback=None)
        if entity != "resource":
            return entity

    entity, _ = infer_entity(f"{name} {description} {context_label}", fallback=fallback)
    return entity


def infer_value_kind(name: str, description: str = "") -> str:
    lowered_name = snake_case(name)
    lowered_description = description.lower()
    if lowered_name.endswith("_id") or lowered_name == "id" or " identifier" in lowered_description:
        return "identifier"
    if "email" in lowered_name or "email address" in lowered_description:
        return "email"
    if "token" in lowered_name:
        return "token"
    if lowered_name.endswith("_url") or lowered_name == "url":
        return "url"
    if lowered_name.endswith("_name") or lowered_name in {"name", "display_name", "title"}:
        return "name"
    return "unknown"


def canonicalize_field_name(name: str, entity: str, kind: str) -> str:
    canonical = snake_case(name)
    if kind == "email":
        return "email"
    if kind == "name":
        return f"{entity}_name" if canonical in {"name", "display_name", "title"} and entity != "resource" else canonical
    if kind == "identifier":
        if canonical == "id":
            return f"{entity}_id" if entity != "resource" else "id"
        if canonical.endswith("_id"):
            base = canonical[:-3]
            if base in {"rule"} and entity != "resource":
                return f"{entity}_id"
        if canonical.endswith("id") and "_" not in canonical:
            prefix = canonical[:-2]
            if prefix:
                return f"{prefix}_id"
    return canonical


def resolve_ref(schema: dict, defs: dict) -> dict:
    ref = schema.get("$ref")
    if not ref:
        return schema
    ref_name = ref.split("/")[-1]
    return defs.get(ref_name, {})


def collect_output_fields(tool: dict) -> list[dict]:
    root_schema = tool.get("output_parameters", {})
    defs = root_schema.get("$defs", {})
    results: list[dict] = []

    def walk(schema: dict, path: str, context_entity: str, context_label: str, seen_refs: set[tuple[str, str]]) -> None:
        if not schema:
            return

        if "$ref" in schema:
            ref_name = schema["$ref"].split("/")[-1]
            ref_key = (path, ref_name)
            if ref_key in seen_refs:
                return
            ref_schema = defs.get(ref_name, {})
            next_entity, _ = infer_entity(f"{ref_name} {context_label}", fallback=context_entity)
            walk(ref_schema, path, next_entity, ref_name, seen_refs | {ref_key})
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
            item_entity, _ = infer_entity(
                f"{context_label} {items.get('title', '')}", fallback=singularize(context_entity)
            )
            walk(items, f"{path}[]", item_entity, items.get("title", context_label), seen_refs)
            return

        properties = schema.get("properties", {})
        if properties:
            current_entity, _ = infer_entity(
                f"{schema.get('title', '')} {context_label} {path}", fallback=context_entity
            )
            for prop_name, prop_schema in properties.items():
                if prop_name in {"error", "successful"}:
                    continue
                prop_path = f"{path}.{prop_name}" if path else prop_name
                prop_description = prop_schema.get("description", "")
                prop_entity = infer_field_entity(
                    prop_name,
                    f"{prop_schema.get('title', '')} {prop_description}",
                    current_entity,
                    context_label,
                )
                if prop_schema.get("type") == "array":
                    items = prop_schema.get("items", {})
                    item_entity, _ = infer_entity(
                        f"{prop_name} {items.get('title', '')}", fallback=singularize(prop_entity)
                    )
                    walk(items, f"{prop_path}[]", item_entity, prop_name, seen_refs)
                    continue
                if prop_schema.get("type") == "object" or "$ref" in prop_schema or prop_schema.get("properties"):
                    walk(prop_schema, prop_path, prop_entity, prop_name, seen_refs)
                    continue

                kind = infer_value_kind(prop_name, prop_description)
                canonical_name = canonicalize_field_name(prop_name, prop_entity, kind)
                results.append(
                    {
                        "path": prop_path,
                        "raw_name": prop_name,
                        "canonical_name": canonical_name,
                        "entity": prop_entity,
                        "kind": kind,
                        "description": prop_description,
                    }
                )
            return

        kind = infer_value_kind(context_label, schema.get("description", ""))
        canonical_name = canonicalize_field_name(context_label, context_entity, kind)
        results.append(
            {
                "path": path,
                "raw_name": context_label,
                "canonical_name": canonical_name,
                "entity": context_entity,
                "kind": kind,
                "description": schema.get("description", ""),
            }
        )

    walk(root_schema, "$", tool["primary_entity"], tool["name"], set())
    deduped: dict[tuple[str, str, str], dict] = {}
    for field in results:
        key = (field["path"], field["canonical_name"], field["entity"])
        deduped[key] = field
    return list(deduped.values())


def classify_input(canonical_name: str, kind: str, description: str, required: bool) -> str:
    lowered_description = description.lower()
    if not required:
        return "optional_context"
    if canonical_name in USER_INPUT_FIELDS or any(token in canonical_name for token in USER_INPUT_FIELDS):
        return "user_input"
    if canonical_name.startswith(OPTIONAL_CONTEXT_PREFIXES) or canonical_name in OPTIONAL_CONTEXT_FIELDS:
        return "optional_context"
    if kind == "identifier":
        if canonical_name in {"user_id", "calendar_id", "email_id"}:
            return "either"
        return "tool_derived"
    if kind == "email":
        return "either"
    if "identifier" in lowered_description or "id of" in lowered_description:
        return "tool_derived"
    if any(token in canonical_name for token in ("query", "subject", "body", "text", "title", "description")):
        return "user_input"
    return "ambiguous"


def extract_input_fields(tool: dict) -> tuple[list[dict], list[dict]]:
    schema = tool.get("input_parameters", {})
    required_fields = set(schema.get("required", []))
    required: list[dict] = []
    optional: list[dict] = []

    for name, prop_schema in schema.get("properties", {}).items():
        description = prop_schema.get("description", "")
        entity = infer_field_entity(name, description, tool["primary_entity"], tool["name"])
        kind = infer_value_kind(name, description)
        canonical_name = canonicalize_field_name(name, entity, kind)
        field = {
            "name": name,
            "canonical_name": canonical_name,
            "entity": entity,
            "kind": kind,
            "required": name in required_fields,
            "description": description,
            "input_path": f"$.input_parameters.properties.{name}",
            "classification": classify_input(canonical_name, kind, description, name in required_fields),
        }
        if field["required"]:
            required.append(field)
        else:
            optional.append(field)
    return required, optional


def build_tool_index(tools: list[dict]) -> list[dict]:
    indexed_tools: list[dict] = []
    for raw_tool in tools:
        primary_entity = infer_primary_entity(raw_tool)
        tool = {
            "slug": raw_tool["slug"],
            "name": raw_tool["name"],
            "description": raw_tool.get("description", ""),
            "tags": raw_tool.get("tags", []),
            "is_deprecated": raw_tool.get("is_deprecated", False),
            "operation_type": infer_operation_type(raw_tool["slug"]),
            "primary_entity": primary_entity,
        }
        tool["domain"] = infer_tool_domain(raw_tool, primary_entity)
        required_inputs, optional_inputs = extract_input_fields(tool | {"input_parameters": raw_tool.get("input_parameters", {})})
        tool["required_inputs"] = required_inputs
        tool["optional_inputs"] = optional_inputs
        tool["output_fields"] = collect_output_fields(tool | {"output_parameters": raw_tool.get("output_parameters", {})})
        indexed_tools.append(tool)
    return indexed_tools


def score_relationship(source_tool: dict, source_field: dict, target_tool: dict, target_input: dict) -> tuple[float, list[str]]:
    if source_tool["slug"] == target_tool["slug"]:
        return 0.0, []
    if target_input["classification"] not in {"tool_derived", "either"}:
        return 0.0, []

    signals: list[str] = []
    score = 0.0

    if source_field["kind"] == target_input["kind"]:
        score += 0.15
        signals.append("kind")

    if source_field["canonical_name"] == target_input["canonical_name"]:
        score += 0.55
        signals.append("canonical_name")

    if source_field["entity"] == target_input["entity"] and target_input["entity"] != "resource":
        score += 0.25
        signals.append("entity")

    if source_tool["primary_entity"] == target_input["entity"] and target_input["entity"] != "resource":
        score += 0.15
        signals.append("source_primary_entity")

    if source_tool["domain"] == target_tool["domain"] and target_tool["domain"] != "generic":
        score += 0.1
        signals.append("domain")

    if source_tool["operation_type"] in PRODUCER_OPERATIONS:
        score += 0.1
        signals.append("producer_operation")

    if source_tool["operation_type"] in DISCOVERY_OPERATIONS:
        score += 0.08
        signals.append("discovery_operation")

    if "[]" in source_field["path"]:
        score += 0.05
        signals.append("collection_output")

    if source_tool["is_deprecated"]:
        score -= 0.25
    if source_tool["operation_type"] in DESTRUCTIVE_OPERATIONS:
        score -= 0.08

    return score, signals


def build_relationships(tool_index: list[dict], include_deprecated: bool = False) -> list[dict]:
    producer_pool = [tool for tool in tool_index if include_deprecated or not tool["is_deprecated"]]
    relationships: list[dict] = []

    for target_tool in tool_index:
        if target_tool["is_deprecated"] and not include_deprecated:
            continue

        for target_input in target_tool["required_inputs"]:
            candidates: list[dict] = []
            for source_tool in producer_pool:
                for source_field in source_tool["output_fields"]:
                    score, signals = score_relationship(source_tool, source_field, target_tool, target_input)
                    if score < 0.75:
                        continue
                    candidates.append(
                        {
                            "source": source_tool["slug"],
                            "target": target_tool["slug"],
                            "parameter": target_input["canonical_name"],
                            "target_input_name": target_input["name"],
                            "entity": target_input["entity"],
                            "source_output_path": source_field["path"],
                            "target_input_path": target_input["input_path"],
                            "relationship_type": "produces_identifier_for",
                            "confidence": round(score, 3),
                            "signals": signals,
                            "reason": (
                                f"{source_tool['slug']} exposes {source_field['canonical_name']} at {source_field['path']} "
                                f"which matches required input {target_input['name']} on {target_tool['slug']}"
                            ),
                        }
                    )

            candidates.sort(key=lambda item: (-item["confidence"], item["source"], item["source_output_path"]))
            relationships.extend(candidates[:5])
    return relationships


def build_simple_relationships(relationships: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}
    for relationship in relationships:
        key = (relationship["source"], relationship["target"])
        if key not in grouped:
            grouped[key] = {
                "source": relationship["source"],
                "target": relationship["target"],
                "parameters": [],
                "max_confidence": relationship["confidence"],
                "relationship_count": 0,
            }
        group = grouped[key]
        if relationship["parameter"] not in group["parameters"]:
            group["parameters"].append(relationship["parameter"])
        group["max_confidence"] = max(group["max_confidence"], relationship["confidence"])
        group["relationship_count"] += 1

    simple_relationships = list(grouped.values())
    for relationship in simple_relationships:
        relationship["parameters"].sort()
    simple_relationships.sort(key=lambda item: (-item["max_confidence"], item["source"], item["target"]))
    return simple_relationships


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build dependency relationships for Google Super tools")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--tool-index", type=Path, default=DEFAULT_TOOL_INDEX_PATH)
    parser.add_argument("--relationships", type=Path, default=DEFAULT_RELATIONSHIP_PATH)
    parser.add_argument("--simple-relationships", type=Path, default=DEFAULT_SIMPLE_RELATIONSHIP_PATH)
    parser.add_argument("--include-deprecated", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_tools = json.loads(args.input.read_text())
    tool_index = build_tool_index(raw_tools)
    relationships = build_relationships(tool_index, include_deprecated=args.include_deprecated)
    simple_relationships = build_simple_relationships(relationships)

    write_json(args.tool_index, tool_index)
    write_json(args.relationships, relationships)
    write_json(args.simple_relationships, simple_relationships)

    print(f"Indexed {len(tool_index)} tools")
    print(f"Wrote {len(relationships)} rich relationships to {args.relationships.name}")
    print(f"Wrote {len(simple_relationships)} simple relationships to {args.simple_relationships.name}")


if __name__ == "__main__":
    main()