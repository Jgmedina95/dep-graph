Normalize this raw tool definition into the contract below.

Important requirements:
- Preserve slug exactly.
- Use lower_snake_case for operation_type, primary_entity, domain, and canonical_name.
- Every required source input must appear in required_inputs.
- Every optional source input that matters for execution should appear in optional_inputs.
- Include output fields that are useful for downstream tool chaining, especially identifiers, names, emails, tokens, and URLs.
- Prefer JSONPath-like source paths.

Contract reminder:
{schema_contract}

Raw tool JSON:
{raw_tool_json}