from __future__ import annotations

from typing import Any


REQUIRED_TOOL_FIELDS = {
    "slug",
    "name",
    "description",
    "tags",
    "is_deprecated",
    "operation_type",
    "primary_entity",
    "domain",
    "required_inputs",
    "optional_inputs",
    "output_fields",
}

REQUIRED_IO_FIELDS = {
    "canonical_name",
    "description",
    "entity",
    "kind",
}

REQUIRED_INPUT_FIELDS = REQUIRED_IO_FIELDS | {"classification", "input_path", "name", "required"}
REQUIRED_OUTPUT_FIELDS = REQUIRED_IO_FIELDS | {"path", "raw_name"}

ALLOWED_KINDS = {"identifier", "email", "token", "url", "name", "unknown"}
ALLOWED_CLASSIFICATIONS = {"tool_derived", "either", "user_input", "optional_context", "ambiguous"}


def contract_markdown() -> str:
    return """
Normalized tool index contract:

Top-level tool object:
- slug: original tool slug, unchanged
- name: human-readable tool name
- description: concise tool description copied or normalized from source
- tags: list of source tags or inferred tags
- is_deprecated: boolean
- operation_type: normalized lower_snake_case verb like list, get, create, delete, find, search, update, patch
- primary_entity: normalized lower_snake_case resource name like thread, file, issue, collection, citation, event
- domain: broad product/toolkit family like gmail, drive, github, zotero, docs, generic
- required_inputs: list of normalized input fields
- optional_inputs: list of normalized input fields
- output_fields: list of normalized output fields

Normalized input field object:
- name: original source parameter name
- canonical_name: normalized field name, preferably lower_snake_case. Generic id fields should be expanded when possible, for example thread_id instead of id.
- entity: resource name associated with the field
- kind: one of identifier, email, token, url, name, unknown
- required: boolean
- description: short field description
- input_path: JSONPath-like source path, for example $.input_parameters.properties.id
- classification: one of tool_derived, either, user_input, optional_context, ambiguous

Normalized output field object:
- raw_name: original source field name
- canonical_name: normalized lower_snake_case field name
- entity: resource name associated with the field
- kind: one of identifier, email, token, url, name, unknown
- description: short field description
- path: JSONPath-like output location, for example $.data.threads[].id

Normalization rules:
- Preserve the original slug exactly.
- Use lower_snake_case for operation_type, primary_entity, domain, canonical_name.
- If a field is clearly an identifier for a resource, use canonical names like thread_id, file_id, issue_id, repo_id.
- Put authored text like subject, body, title, query, prompt into user_input unless the schema clearly says it is tool-derived.
- Put pagination, sorting, formatting, filtering, verbosity, include_* and max_* style controls into optional_context when they are not core dependencies.
- If a required field might come from either the user or another tool, classify it as either.
- Output only a single JSON object that matches this contract.
""".strip()


def _assert_type(value: Any, expected_type: type | tuple[type, ...], label: str) -> None:
    if not isinstance(value, expected_type):
        raise ValueError(f"{label} must be of type {expected_type}, got {type(value)}")


def _validate_field(field: dict[str, Any], required_fields: set[str], label: str) -> None:
    missing = required_fields - set(field)
    if missing:
        raise ValueError(f"{label} is missing fields: {sorted(missing)}")

    for key in required_fields:
        if field[key] in (None, "") and key not in {"description"}:
            raise ValueError(f"{label}.{key} must not be empty")

    if field["kind"] not in ALLOWED_KINDS:
        raise ValueError(f"{label}.kind must be one of {sorted(ALLOWED_KINDS)}")


def validate_normalized_tool(tool: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_TOOL_FIELDS - set(tool)
    if missing:
        raise ValueError(f"tool is missing fields: {sorted(missing)}")

    for key in [
        "slug",
        "name",
        "description",
        "operation_type",
        "primary_entity",
        "domain",
    ]:
        _assert_type(tool[key], str, key)

    _assert_type(tool["tags"], list, "tags")
    _assert_type(tool["is_deprecated"], bool, "is_deprecated")
    _assert_type(tool["required_inputs"], list, "required_inputs")
    _assert_type(tool["optional_inputs"], list, "optional_inputs")
    _assert_type(tool["output_fields"], list, "output_fields")

    for index, field in enumerate(tool["required_inputs"]):
        _assert_type(field, dict, f"required_inputs[{index}]")
        _validate_field(field, REQUIRED_INPUT_FIELDS, f"required_inputs[{index}]")
        if field["classification"] not in ALLOWED_CLASSIFICATIONS:
            raise ValueError(
                f"required_inputs[{index}].classification must be one of {sorted(ALLOWED_CLASSIFICATIONS)}"
            )
        if field["required"] is not True:
            raise ValueError(f"required_inputs[{index}].required must be true")

    for index, field in enumerate(tool["optional_inputs"]):
        _assert_type(field, dict, f"optional_inputs[{index}]")
        _validate_field(field, REQUIRED_INPUT_FIELDS, f"optional_inputs[{index}]")
        if field["classification"] not in ALLOWED_CLASSIFICATIONS:
            raise ValueError(
                f"optional_inputs[{index}].classification must be one of {sorted(ALLOWED_CLASSIFICATIONS)}"
            )
        if field["required"] is not False:
            raise ValueError(f"optional_inputs[{index}].required must be false")

    for index, field in enumerate(tool["output_fields"]):
        _assert_type(field, dict, f"output_fields[{index}]")
        _validate_field(field, REQUIRED_OUTPUT_FIELDS, f"output_fields[{index}]")

    return tool


def validate_tool_index(tool_index: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _assert_type(tool_index, list, "tool_index")
    seen_slugs: set[str] = set()
    for index, tool in enumerate(tool_index):
        _assert_type(tool, dict, f"tool_index[{index}]")
        validated = validate_normalized_tool(tool)
        if validated["slug"] in seen_slugs:
            raise ValueError(f"duplicate slug in tool index: {validated['slug']}")
        seen_slugs.add(validated["slug"])
    return tool_index