# Building a Dependency Graph for Any Tool System with Composio

When you build an agent system, one of the most useful things you can have is intuition about the paths the agent can follow.

A dependency graph helps with exactly that. It shows which tools unlock other tools, where the likely bottlenecks are, which actions are isolated, and where dead ends appear. Instead of treating a toolset like a flat list of capabilities, you start to see it as a navigable system.

When an agent uses tools, the hard part is usually not calling a tool. The hard part is knowing what has to happen before that tool can be called.

For example, replying to an email thread requires a `thread_id`. Updating a GitHub issue requires an issue identifier. Moving a file requires a file ID and sometimes a parent folder ID. In all of these cases, an agent needs to understand whether the missing value should come from the user or from another tool.

That was the problem I wanted to solve here: turn a raw set of Composio tools into a dependency graph that shows how tools connect to each other.

I built this project from scratch in about two hours. In practice it took a little longer wall-clock time because I had to pause in the middle to go grab groceries and handle real life for a bit, but the actual build was still a compact sprint from zero to working graphs.

The code for the project is here: [github.com/Jgmedina95/dep-graph](https://github.com/Jgmedina95/dep-graph).

## The Goal

I wanted a system that could:

1. Read a raw tool dump from Composio.
2. Extract the important entities and parameters from each tool.
3. Infer relationships between tools based on required inputs and produced outputs.
4. Visualize those relationships as an interactive graph.
5. Generalize beyond one toolkit, so the same pipeline could work for Google Super, GitHub, and eventually others.

## How I Designed It

I broke the problem into two stages.

### 1. Normalize the Raw Tool Schemas

Raw tool definitions are rich, but not always easy to compare directly. So the first step was to normalize each tool into a smaller schema with fields like:

- `operation_type`
- `primary_entity`
- `required_inputs`
- `optional_inputs`
- `output_fields`

This makes it much easier to ask useful questions like:

- Does this tool require a `thread_id`?
- Does another tool produce a `thread_id`?
- Is this value something the user should provide directly?

I initially explored an LLM-based normalization pipeline so the same idea could adapt to different toolkits automatically. I also added a deterministic fallback path, which was useful when I wanted a faster or more controllable run.

### 2. Build a Graph from the Normalized Schema

Once the tools share a common format, the graph construction becomes much simpler.

The graph builder looks for cases where:

- Tool A outputs a value like `issue_number`, `thread_id`, or `calendar_id`
- Tool B requires that same value to run

That becomes a directed edge:

`Tool A -> Tool B`

I also explicitly modeled user-provided values, so inputs like `query`, `title`, `body`, or `owner` can appear as seed nodes in the graph when useful.

## Why This Design Matters

The key idea is that the graph builder does not need to know anything special about Google Super or GitHub.

Once a toolkit is normalized into the same intermediate schema, the same dependency logic can run on top of it. That means the expensive part is schema understanding, not graph generation.

This is useful for agent systems because it creates a reusable routing layer:

- If a required parameter is missing, the agent can ask the user for it.
- If another tool can produce that parameter, the agent can call that tool first.
- If there are multiple candidate upstream tools, the graph exposes those alternatives.

## What I Built

I generated dependency graphs for two toolkits:

- Google Super
- GitHub

For exploration, I created fuller graphs with more edges and user seed nodes. For presentation, I also created cleaner filtered versions that are much easier to load and inspect.

## Simplified Graphs

These are the lightweight versions I would embed or link from a portfolio page:

- [Google Super Cleaner Graph](graphs/googlesuper_relationship_graph_clean.html)
- [GitHub Cleaner Graph](graphs/github_relationship_graph_clean.html)

These cleaner versions use stronger filtering so the graph is easier to read and does not overwhelm the browser.

## If I Extended This Further

There are a few things I would improve next:

1. Add a reachability layer so I can ask whether one tool is reachable from another through valid dependency paths.
2. Improve ranking so weak or noisy relationships get down-weighted automatically.
3. Use the LLM path selectively only when a schema is ambiguous, and keep deterministic logic for straightforward tools.
4. Add graph clustering or community detection to make large toolkits easier to navigate visually.

## Final Thought

The main takeaway from this project is that tool orchestration gets easier once you stop thinking only about individual tools and start thinking about the dependency structure between them.

Composio provides the raw tool surface. The missing layer is a system that explains how those tools connect. That is the layer I focused on here.

If your portfolio supports embedded HTML, the cleaner graph versions above can also be embedded directly as interactive demos instead of linked separately.