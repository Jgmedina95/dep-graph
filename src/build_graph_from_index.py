from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.tool_index_contract import validate_tool_index


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = ROOT / "tool_index.json"
DEFAULT_RELATIONSHIP_PATH = ROOT / "tool_relationships.json"
DEFAULT_SIMPLE_RELATIONSHIP_PATH = ROOT / "tool_relationships_simple.json"

PRODUCER_OPERATIONS = {
    "aggregate",
    "autocomplete",
    "check",
    "copy",
    "create",
    "fetch",
    "find",
    "generate",
    "get",
    "import",
    "list",
    "lookup",
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


def score_relationship(source_tool: dict, source_field: dict, target_tool: dict, target_input: dict) -> tuple[float, list[str]]:
    if source_tool["slug"] == target_tool["slug"]:
        return 0.0, []
    if target_input["classification"] not in {"tool_derived", "either"}:
        return 0.0, []

    score = 0.0
    signals: list[str] = []

    if source_field["kind"] == target_input["kind"]:
        score += 0.15
        signals.append("kind")

    if source_field["canonical_name"] == target_input["canonical_name"]:
        score += 0.55
        signals.append("canonical_name")

    if source_field["entity"] == target_input["entity"]:
        score += 0.25
        signals.append("entity")

    if source_tool["primary_entity"] == target_input["entity"]:
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

    if target_input["classification"] == "tool_derived":
        score += 0.1
        signals.append("required_dependency")

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build graph relationships from a normalized tool index")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--relationships", type=Path, default=DEFAULT_RELATIONSHIP_PATH)
    parser.add_argument("--simple-relationships", type=Path, default=DEFAULT_SIMPLE_RELATIONSHIP_PATH)
    parser.add_argument("--include-deprecated", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tool_index = validate_tool_index(json.loads(args.input.read_text()))
    relationships = build_relationships(tool_index, include_deprecated=args.include_deprecated)
    simple_relationships = build_simple_relationships(relationships)

    args.relationships.write_text(json.dumps(relationships, indent=2), encoding="utf-8")
    args.simple_relationships.write_text(json.dumps(simple_relationships, indent=2), encoding="utf-8")

    print(f"Wrote {len(relationships)} rich relationships to {args.relationships.name}")
    print(f"Wrote {len(simple_relationships)} simple relationships to {args.simple_relationships.name}")


if __name__ == "__main__":
    main()