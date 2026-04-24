from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from string import Template

import networkx as nx
from pyvis.network import Network


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = ROOT / "artifacts" / "data" / "googlesuper_relationships.json"
DEFAULT_TOOL_INDEX_PATH = ROOT / "artifacts" / "data" / "googlesuper_tool_index.json"
DEFAULT_OUTPUT_PATH = ROOT / "artifacts" / "graphs" / "googlesuper_relationship_graph.html"

DISCOVERY_PREFIXES = ("LIST", "GET", "FIND", "SEARCH", "FETCH", "QUERY", "LOOKUP")
WRITE_PREFIXES = ("CREATE", "UPDATE", "PATCH", "INSERT", "ADD", "MOVE", "SEND", "WATCH")
DESTRUCTIVE_PREFIXES = ("DELETE", "CLEAR", "TRASH", "UNTRASH", "STOP", "EMPTY")


def node_style(slug: str) -> tuple[str, str]:
    if slug.startswith("USER_INPUT_"):
        return "#82e0aa", "star"

    parts = slug.split("_")
    token = parts[1] if len(parts) > 1 else parts[0]
    if token in DISCOVERY_PREFIXES:
        return "#5dade2", "ellipse"
    if token in WRITE_PREFIXES:
        return "#f5b041", "box"
    if token in DESTRUCTIVE_PREFIXES:
        return "#ec7063", "diamond"
    return "#aab7b8", "dot"


def aggregate_relationships(relationships: list[dict], min_confidence: float, max_edges: int | None) -> list[dict]:
    filtered = [item for item in relationships if item["confidence"] >= min_confidence]
    filtered.sort(key=lambda item: (-item["confidence"], item["source"], item["target"], item["parameter"]))

    if max_edges is not None:
        filtered = filtered[:max_edges]

    grouped: dict[tuple[str, str], dict] = {}
    for item in filtered:
        key = (item["source"], item["target"])
        if key not in grouped:
            grouped[key] = {
                "source": item["source"],
                "target": item["target"],
                "parameters": [],
                "entities": [],
                "max_confidence": item["confidence"],
                "count": 0,
                "reasons": [],
            }

        edge = grouped[key]
        if item["parameter"] not in edge["parameters"]:
            edge["parameters"].append(item["parameter"])
        if item["entity"] not in edge["entities"]:
            edge["entities"].append(item["entity"])
        if item["reason"] not in edge["reasons"] and len(edge["reasons"]) < 3:
            edge["reasons"].append(item["reason"])
        edge["max_confidence"] = max(edge["max_confidence"], item["confidence"])
        edge["count"] += 1

    aggregated = list(grouped.values())
    aggregated.sort(key=lambda item: (-item["max_confidence"], -item["count"], item["source"], item["target"]))
    return aggregated


def build_user_seed_relationships(tool_index: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], dict] = {}

    for tool in tool_index:
        for field in tool.get("required_inputs", []):
            if field["classification"] not in {"user_input", "either"}:
                continue

            source = f"USER_INPUT_{field['canonical_name'].upper()}"
            target = tool["slug"]
            key = (source, target)

            if key not in grouped:
                grouped[key] = {
                    "source": source,
                    "target": target,
                    "parameters": [],
                    "entities": [],
                    "max_confidence": 1.0,
                    "count": 0,
                    "reasons": [],
                    "relationship_type": "user_input_seed",
                }

            edge = grouped[key]
            if field["canonical_name"] not in edge["parameters"]:
                edge["parameters"].append(field["canonical_name"])
            if field["entity"] not in edge["entities"]:
                edge["entities"].append(field["entity"])

            reason = (
                f"{tool['slug']} requires {field['name']} and its classification is {field['classification']}, "
                f"so the user can seed {field['canonical_name']} directly."
            )
            if reason not in edge["reasons"] and len(edge["reasons"]) < 3:
                edge["reasons"].append(reason)

            edge["count"] += 1

    seed_relationships = list(grouped.values())
    seed_relationships.sort(key=lambda item: (item["source"], item["target"]))
    return seed_relationships


def build_graph(aggregated_relationships: list[dict]) -> nx.DiGraph:
    graph = nx.DiGraph()
    indegree_counter: defaultdict[str, int] = defaultdict(int)
    outdegree_counter: defaultdict[str, int] = defaultdict(int)

    for edge in aggregated_relationships:
        outdegree_counter[edge["source"]] += 1
        indegree_counter[edge["target"]] += 1

    for edge in aggregated_relationships:
        for node in (edge["source"], edge["target"]):
            if graph.has_node(node):
                continue
            color, shape = node_style(node)
            degree = indegree_counter[node] + outdegree_counter[node]
            title = (
                f"Node: {node}<br>"
                f"Incoming edges: {indegree_counter[node]}<br>"
                f"Outgoing edges: {outdegree_counter[node]}<br>"
                f"Total degree: {degree}"
            )
            graph.add_node(
                node,
                label=node,
                color=color,
                shape=shape,
                size=12 + min(degree * 1.5, 28),
                title=title,
            )

        title = (
            f"Source: {edge['source']}<br>"
            f"Target: {edge['target']}<br>"
            f"Parameters: {', '.join(edge['parameters'])}<br>"
            f"Entities: {', '.join(edge['entities'])}<br>"
            f"Relationship count: {edge['count']}<br>"
            f"Max confidence: {edge['max_confidence']:.2f}<br>"
            f"Examples:<br>- " + "<br>- ".join(edge["reasons"])
        )

        edge_color = "#58d68d" if edge.get("relationship_type") == "user_input_seed" else "#7fb3d5"
        edge_dashes = edge.get("relationship_type") == "user_input_seed"

        graph.add_edge(
            edge["source"],
            edge["target"],
            title=title,
            value=max(1.0, edge["max_confidence"] * 2 + edge["count"] * 0.35),
            color=edge_color,
            dashes=edge_dashes,
            arrows="to",
        )

    return graph


def render_graph(graph: nx.DiGraph, output_path: Path, title: str) -> None:
        net = Network(height="900px", width="100%", directed=True, bgcolor="#111827", font_color="#f9fafb")
        net.from_nx(graph)
        net.set_options(
                """
                var options = {
                    "nodes": {
                        "font": {
                            "size": 14,
                            "face": "Helvetica"
                        },
                        "borderWidth": 1.5
                    },
                    "edges": {
                        "smooth": {
                            "type": "dynamic"
                        },
                        "color": {
                            "inherit": false
                        },
                        "font": {
                            "size": 10,
                            "align": "middle"
                        }
                    },
                    "interaction": {
                        "hover": true,
                        "navigationButtons": true,
                        "keyboard": true,
                        "zoomView": true,
                        "dragView": true
                    },
                    "physics": {
                        "barnesHut": {
                            "gravitationalConstant": -4200,
                            "centralGravity": 0.15,
                            "springLength": 180,
                            "springConstant": 0.035,
                            "damping": 0.12,
                            "avoidOverlap": 0.2
                        },
                        "minVelocity": 0.75
                    }
                }
                """
        )
        net.heading = title
        net.write_html(str(output_path), open_browser=False, notebook=False)

        html = output_path.read_text(encoding="utf-8")
        html = inject_legend(html)
        html = inject_click_focus(html)
        output_path.write_text(html, encoding="utf-8")


def inject_legend(html: str) -> str:
        legend_markup = """<div id="graph-legend" style="position: absolute; top: 16px; right: 16px; z-index: 999; background: rgba(17, 24, 39, 0.92); color: #f9fafb; border: 1px solid #374151; border-radius: 12px; padding: 14px 16px; width: 250px; box-shadow: 0 12px 30px rgba(0, 0, 0, 0.28); font-family: Helvetica, Arial, sans-serif; font-size: 13px; line-height: 1.45;">
            <div style="font-size: 14px; font-weight: 700; margin-bottom: 10px;">Legend</div>
            <div style="margin-bottom: 10px;">
                <div style="font-weight: 600; margin-bottom: 6px;">Node Types</div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;"><span style="width: 12px; height: 12px; border-radius: 999px; display: inline-block; background: #5dade2;"></span><span>Discovery tool</span></div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;"><span style="width: 12px; height: 12px; display: inline-block; background: #f5b041; border-radius: 2px;"></span><span>Write / mutation tool</span></div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;"><span style="width: 0; height: 0; border-left: 7px solid transparent; border-right: 7px solid transparent; border-bottom: 12px solid #ec7063; display: inline-block; transform: rotate(45deg);"></span><span>Destructive tool</span></div>
                <div style="display: flex; align-items: center; gap: 8px;"><span style="color: #82e0aa; font-size: 16px; line-height: 1;">★</span><span>User input seed</span></div>
            </div>
            <div style="margin-bottom: 10px;">
                <div style="font-weight: 600; margin-bottom: 6px;">Edge Types</div>
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 5px;"><span style="width: 22px; height: 0; border-top: 2px solid #7fb3d5; display: inline-block;"></span><span>Tool dependency</span></div>
                <div style="display: flex; align-items: center; gap: 8px;"><span style="width: 22px; height: 0; border-top: 2px dashed #58d68d; display: inline-block;"></span><span>User-provided seed</span></div>
            </div>
            <div style="border-top: 1px solid #374151; padding-top: 8px; color: #d1d5db;">
                Click a node to focus the graph on it.<br>Use the mouse wheel or trackpad to adjust zoom.
            </div>
        </div>"""

        marker = "<body>"
        if marker not in html:
                return html
        return html.replace(marker, f"{marker}\n{legend_markup}", 1)


def inject_click_focus(html: str) -> str:
        script_template = Template(
                """
<script type="text/javascript">
    (function() {
        function attachNodeFocus() {
            if (typeof network === 'undefined') {
                window.setTimeout(attachNodeFocus, 150);
                return;
            }

            network.on('click', function(params) {
                if (!params.nodes || params.nodes.length === 0) {
                    return;
                }

                var nodeId = params.nodes[0];
                network.focus(nodeId, {
                    scale: $focus_scale,
                    animation: {
                        duration: 450,
                        easingFunction: 'easeInOutQuad'
                    }
                });
            });

            network.on('doubleClick', function(params) {
                if (!params.nodes || params.nodes.length === 0) {
                    return;
                }

                var nodeId = params.nodes[0];
                network.focus(nodeId, {
                    scale: $double_click_scale,
                    animation: {
                        duration: 550,
                        easingFunction: 'easeInOutQuad'
                    }
                });
            });
        }

        attachNodeFocus();
    })();
</script>
                """
        )

        script = script_template.substitute(focus_scale="1.18", double_click_scale="1.32").strip()
        marker = "</body>"
        if marker not in html:
                return html
        return html.replace(marker, f"{script}\n{marker}", 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize tool relationships with Pyvis")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--tool-index", type=Path, default=DEFAULT_TOOL_INDEX_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--min-confidence", type=float, default=1.0)
    parser.add_argument("--max-edges", type=int, default=None)
    parser.add_argument("--without-user-seeds", action="store_true")
    parser.add_argument("--title", type=str, default="Google Super Tool Dependency Graph")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    relationships = json.loads(args.input.read_text())
    aggregated_relationships = aggregate_relationships(relationships, args.min_confidence, args.max_edges)
    user_seed_relationships: list[dict] = []
    if not args.without_user_seeds and args.tool_index.exists():
        tool_index = json.loads(args.tool_index.read_text())
        user_seed_relationships = build_user_seed_relationships(tool_index)
        aggregated_relationships.extend(user_seed_relationships)

    graph = build_graph(aggregated_relationships)
    render_graph(graph, args.output, args.title)

    print(f"Loaded {len(relationships)} raw relationships")
    print(f"Rendered {len(aggregated_relationships)} aggregated edges")
    print(f"Added {len(user_seed_relationships)} user seed edges")
    print(f"Rendered {graph.number_of_nodes()} nodes")
    print(f"Wrote graph HTML to {args.output.name}")


if __name__ == "__main__":
    main()