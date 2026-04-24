# dep-graph

This repo builds dependency graphs for tool systems.

The core idea is:

1. Fetch or load a raw tool dump.
2. Normalize each tool into a shared schema.
3. Infer dependencies from produced outputs to required inputs.
4. Render the result as an interactive HTML graph.

The current codebase includes two normalization paths:

- a deterministic path that works well for GitHub-style tool dumps
- an LLM-based path that is more general across toolkits

## What You Need

- Python 3.12 recommended
- `uv` recommended for environment management, though plain `pip` also works
- A `COMPOSIO_API_KEY` if you want to fetch fresh raw tool definitions from Composio
- An `OPENROUTER_API_KEY` only if you want to use the LLM-based normalization pipeline

## Setup

Using `uv`:

```bash
uv venv
source .venv/bin/activate
uv pip install composio networkx pyvis
```

Using `pip`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install composio networkx pyvis
```

## API Keys

There are two ways to set keys.

### Option 1: Create `.env` yourself

Create a `.env` file in the repo root:

```bash
cat > .env <<'EOF'
COMPOSIO_API_KEY=your_composio_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
EOF
```

Notes:

- `COMPOSIO_API_KEY` is required for `src/index.py` because that script fetches raw tools from Composio.
- `OPENROUTER_API_KEY` is required only for `src/generate_tool_index_with_llm.py`.
- If you only use the deterministic GitHub flow with an already available raw JSON file, you can skip OpenRouter entirely.

### Option 2: Use `scaffold.sh`

If you already have a Composio key and want the repo to request an OpenRouter key automatically:

```bash
export COMPOSIO_API_KEY=your_composio_key_here
sh scaffold.sh
```

That writes a `.env` file with both:

- `COMPOSIO_API_KEY`
- `OPENROUTER_API_KEY`

## Typical Workflows

Prefer passing explicit input and output paths instead of relying on defaults. It makes reruns easier and keeps generated files in one place.

Start by creating output folders:

```bash
mkdir -p artifacts/data artifacts/graphs
```

### Workflow A: Deterministic GitHub Graph

1. Fetch raw GitHub tools from Composio:

```bash
python3 src/index.py --toolkit github
```

This writes `github_tools.json` in the repo root.

2. Normalize the raw dump without using an LLM:

```bash
python3 src/generate_tool_index_deterministic.py \
  --input github_tools.json \
  --output artifacts/data/github_tool_index.json
```

3. Infer graph relationships:

```bash
python3 src/build_graph_from_index.py \
  --input artifacts/data/github_tool_index.json \
  --relationships artifacts/data/github_relationships.json \
  --simple-relationships artifacts/data/github_relationships_simple.json
```

4. Render the interactive graph:

```bash
python3 src/visualize_relationships.py \
  --input artifacts/data/github_relationships.json \
  --tool-index artifacts/data/github_tool_index.json \
  --output artifacts/graphs/github_relationship_graph.html \
  --title "GitHub Tool Dependency Graph"
```

### Workflow B: Generic LLM-Based Graph

Use this path when you want to normalize a toolkit with the LLM-based contract instead of the deterministic GitHub-specific rules.

1. Fetch raw tools:

```bash
python3 src/index.py --toolkit googlesuper
```

2. Normalize with OpenRouter:

```bash
python3 src/generate_tool_index_with_llm.py \
  --input googlesuper_tools.json \
  --output artifacts/data/googlesuper_tool_index.json \
  --max-workers 8
```

3. Build relationships:

```bash
python3 src/build_graph_from_index.py \
  --input artifacts/data/googlesuper_tool_index.json \
  --relationships artifacts/data/googlesuper_relationships.json \
  --simple-relationships artifacts/data/googlesuper_relationships_simple.json
```

4. Render the graph:

```bash
python3 src/visualize_relationships.py \
  --input artifacts/data/googlesuper_relationships.json \
  --tool-index artifacts/data/googlesuper_tool_index.json \
  --output artifacts/graphs/googlesuper_relationship_graph.html \
  --title "Google Super Tool Dependency Graph"
```

## Running Tests

The tests use the standard library `unittest` runner.

```bash
python3 -m unittest discover -s tests
```

There is also an optional live OpenRouter test in the suite. It only runs if both of these are set:

- `RUN_OPENROUTER_LIVE_TESTS=1`
- `OPENROUTER_API_KEY`

## Useful Files

- `src/index.py`: fetch raw tools from Composio
- `src/generate_tool_index_deterministic.py`: deterministic normalization, mainly for GitHub
- `src/generate_tool_index_with_llm.py`: LLM-based normalization via OpenRouter
- `src/build_graph_from_index.py`: infer tool-to-tool dependencies
- `src/visualize_relationships.py`: render interactive HTML graphs with legends and click-focus behavior
- `submission/graphs/`: cleaned graph outputs that were prepared for sharing

## Notes

- The repo tracks source code and final submission graphs, but ignores local `.env`, virtualenvs, raw dumps, and scratch artifacts.
- `src/index.ts` is kept from the original scaffold, but the main working pipeline in this repo is Python-based.
- If you already have a raw tool dump, you can skip `src/index.py` and start directly from normalization.