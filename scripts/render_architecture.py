#!/usr/bin/env python3
"""Generate docs/architecture.html from the Mermaid source in README.md plus a layout here.

A6 originally proposed hand-authoring the SVG, with generation named as the fallback if hand
maintenance proved too costly. Twenty-one nodes and twenty-four edges made that call
immediately: hand-placing every edge endpoint would produce a file where a single transposed
coordinate is invisible to review and where every future architecture change is a
transcription exercise. The decision is recorded in the A6 pull request rather than taken
silently.

What is authored here is the part that needs judgement: which boundary each component sits
in, where the boundaries go, and the reading order. What is derived is everything the Mermaid
source already states: the node set, the edge set, the labels, and boundary membership.
Divergence is therefore impossible by construction, and scripts/diagram_sync.py still runs in
continuous integration to catch a stale committed page.

The output is self-contained: no external stylesheet, no remote font, no script, no image.
JetBrains Mono is requested first in the font stack and falls back to the platform monospace
face, because embedding the woff2 would add roughly two hundred kilobytes of base64 to a file
whose purpose is legibility, and the font is not installed on this machine to embed.
"""

from __future__ import annotations

import html
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagram_sync import Diagram, parse_mermaid  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
OUTPUT = REPO_ROOT / "docs" / "architecture.html"

WIDTH, HEIGHT = 1400, 1010
NODE_W, NODE_H = 224, 58

# Semantic colors, matching the classDef palette in the README Mermaid source so the two
# representations read the same way.
PALETTE = {
    "ingest": ("#3d2b16", "#d29922"),
    "agentic": ("#1b2f4b", "#58a6ff"),
    "datastore": ("#2b1b40", "#a371f7"),
    "serving": ("#1f3d2b", "#3fb950"),
    "evalnode": ("#40161c", "#f85149"),
    "obsnode": ("#14313d", "#39c5cf"),
    "externalnode": ("#21262d", "#8b949e"),
}

KIND = {
    "sources": "externalnode",
    "producer": "ingest",
    "kafka": "ingest",
    "replayer": "ingest",
    "consumer": "ingest",
    "dlq": "ingest",
    "orch": "agentic",
    "classifier": "agentic",
    "retriever": "agentic",
    "drafter": "agentic",
    "policy": "agentic",
    "pg": "datastore",
    "vec": "datastore",
    "queue": "serving",
    "console": "serving",
    "labeled": "evalnode",
    "redteam": "evalnode",
    "judge": "evalnode",
    "board": "evalnode",
    "otel": "obsnode",
    "cost": "obsnode",
}

# Top-left corner of each node. Authored, because reading order is a design decision.
POSITION = {
    "sources": (60, 70),
    # Streaming plane
    "producer": (60, 190),
    "kafka": (300, 190),
    "replayer": (540, 190),
    "consumer": (300, 290),
    "dlq": (540, 290),
    # Agent workflow
    "orch": (60, 460),
    "classifier": (300, 420),
    "retriever": (300, 500),
    "drafter": (300, 580),
    "policy": (60, 580),
    # State
    "pg": (830, 190),
    "vec": (1090, 190),
    # Human loop
    "queue": (830, 330),
    "console": (1090, 330),
    # Evaluation plane
    "labeled": (830, 470),
    "redteam": (1090, 470),
    "judge": (830, 560),
    "board": (1090, 560),
    # Observability
    "otel": (60, 790),
    "cost": (300, 790),
}

# Boundary rectangles: id -> (x, y, w, h). Authored alongside POSITION.
BOUNDARY_BOX = {
    "stream": (40, 155, 744, 195),
    "workflow": (40, 385, 504, 275),
    "stores": (810, 155, 530, 125),
    "human": (810, 295, 530, 125),
    "evalplane": (810, 435, 530, 205),
    "obs": (40, 755, 504, 125),
}

# The two boundaries the build prompt calls out explicitly get a heavier stroke.
EMPHASISED = {"workflow", "evalplane"}

LEGEND_Y = 930


def _fits(text: str, size: int) -> bool:
    # Monospace advance width is close to 0.66 em once fallback faces are allowed for;
    # 16px of horizontal padding. A raster of the first version overflowed at 0.60.
    return len(text) * size * 0.66 <= NODE_W - 16


def wrap(label: str) -> list[str]:
    """Split a Mermaid label into lines that fit the node box.

    Mermaid labels carry explicit <br/> breaks, which are honoured first. A resulting line
    that is still too wide is word-wrapped, because two labels in the current diagram
    ("events, triages, citations, overrides" and "injection, contradiction, must-escalate")
    do not fit at any node width this layout can afford. Rewriting them in the Mermaid
    source instead would make the specification worse to read in order to make the picture
    easier to draw.
    """
    lines: list[str] = []
    for part in label.replace("<br/>", "\n").split("\n"):
        part = part.strip()
        if not part:
            continue
        size = 12 if not lines else 11
        if _fits(part, size):
            lines.append(part)
            continue
        current = ""
        for word in part.split():
            candidate = f"{current} {word}".strip()
            if current and not _fits(candidate, 11):
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines[:3]


def centre(node: str) -> tuple[float, float]:
    x, y = POSITION[node]
    return x + NODE_W / 2, y + NODE_H / 2


def anchor(src: str, dst: str) -> tuple[float, float, float, float]:
    """Pick edge endpoints on the facing sides of the two boxes.

    Straight lines between side midpoints rather than routed orthogonal paths: routing
    twenty-four edges well is a layout engine, and this diagram is legible without one.
    """
    sx, sy = POSITION[src]
    dx, dy = POSITION[dst]
    scx, scy = centre(src)
    dcx, dcy = centre(dst)

    if abs(dcx - scx) >= abs(dcy - scy):
        x1 = sx + NODE_W if dcx > scx else sx
        x2 = dx if dcx > scx else dx + NODE_W
        return x1, scy, x2, dcy
    y1 = sy + NODE_H if dcy > scy else sy
    y2 = dy if dcy > scy else dy + NODE_H
    return scx, y1, dcx, y2


def render(diagram: Diagram, labels: dict[str, str]) -> str:
    missing = sorted(set(diagram.nodes) - set(POSITION))
    if missing:
        raise SystemExit(
            f"No layout position for {missing}. The Mermaid source gained a node; add it to "
            "POSITION and KIND in this script, then regenerate."
        )
    unknown_kind = sorted(set(diagram.nodes) - set(KIND))
    if unknown_kind:
        raise SystemExit(f"No semantic colour for {unknown_kind}; add it to KIND.")

    # A node drawn outside the boundary it belongs to is a visual lie the structural sync
    # check cannot see: the data attributes would agree while the picture disagrees. Caught
    # exactly this way, with board sitting below the evaluation plane box.
    escaped = []
    for node, bid in diagram.boundaries.items():
        nx, ny = POSITION[node]
        bx, by, bw, bh = BOUNDARY_BOX[bid]
        if not (bx <= nx and nx + NODE_W <= bx + bw and by <= ny and ny + NODE_H <= by + bh):
            escaped.append(f"{node} at ({nx},{ny}) is outside boundary {bid} {BOUNDARY_BOX[bid]}")
    if escaped:
        raise SystemExit(
            "Layout error, nodes drawn outside their boundary:\n  " + "\n  ".join(escaped)
        )

    # Monospace advance width is close to 0.60 em. A label wider than its box is a visual
    # defect the structural sync check cannot see, and it is what a raster of the first
    # version showed: "OpenTelemetry collector" and "Pinned event sources" both overflowed.
    too_wide = []
    for node in sorted(diagram.nodes):
        for index, line in enumerate(wrap(labels[node])):
            size = 12 if index == 0 else 11  # noqa: F841 used by _fits below
            if not _fits(line, size):
                too_wide.append(
                    f"{node}: {line!r} still overflows after wrapping; shorten it in the "
                    "Mermaid source or widen NODE_W"
                )
    if too_wide:
        raise SystemExit("Layout error, labels overflow their box:\n  " + "\n  ".join(too_wide))

    clashing = []
    for (a, ra), (b, rb) in itertools.combinations(BOUNDARY_BOX.items(), 2):
        ax, ay, aw, ah = ra
        bx, by, bw, bh = rb
        if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
            clashing.append(f"{a} {ra} overlaps {b} {rb}")
    if clashing:
        raise SystemExit(
            "Layout error, boundary boxes overlap and would read as one region:\n  "
            + "\n  ".join(clashing)
        )

    overlaps = []
    for a, b in itertools.combinations(sorted(diagram.nodes), 2):
        ax, ay = POSITION[a]
        bx, by = POSITION[b]
        if ax < bx + NODE_W and bx < ax + NODE_W and ay < by + NODE_H and by < ay + NODE_H:
            overlaps.append(f"{a} overlaps {b}")
    if overlaps:
        raise SystemExit("Layout error, overlapping nodes:\n  " + "\n  ".join(overlaps))

    parts: list[str] = []

    # Boundary boxes first, so nodes and edges draw over them.
    for bid, (bx, by, bw, bh) in BOUNDARY_BOX.items():
        title = diagram.boundary_titles.get(bid, bid)
        weight = 2 if bid in EMPHASISED else 1
        dash = "" if bid in EMPHASISED else ' stroke-dasharray="6 4"'
        parts.append(
            f'  <g class="boundary" data-boundary-title="{bid}:{html.escape(title)}">\n'
            f'    <rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="10" '
            f'fill="#0f141b" stroke="#3d4450" stroke-width="{weight}"{dash}/>\n'
            f'    <text x="{bx + 14}" y="{by + 22}" class="boundary-label">'
            f"{html.escape(title)}</text>\n"
            f"  </g>"
        )

    # Edges.
    for src, dst in sorted(diagram.edges):
        x1, y1, x2, y2 = anchor(src, dst)
        parts.append(
            f'  <line data-edge="{src}->{dst}" x1="{x1:.0f}" y1="{y1:.0f}" '
            f'x2="{x2:.0f}" y2="{y2:.0f}" class="edge" marker-end="url(#arrow)"/>'
        )

    # Nodes.
    for node in sorted(diagram.nodes):
        x, y = POSITION[node]
        fill, stroke = PALETTE[KIND[node]]
        boundary = diagram.boundaries.get(node, "")
        lines = wrap(labels[node])
        start = y + NODE_H / 2 - (len(lines) - 1) * 7 + 4
        text = "\n".join(
            f'    <text x="{x + NODE_W / 2:.0f}" y="{start + i * 14:.0f}" '
            f'class="node-label{" strong" if i == 0 else ""}">{html.escape(line)}</text>'
            for i, line in enumerate(lines)
        )
        parts.append(
            f'  <g class="node" data-node="{node}" data-boundary="{boundary}">\n'
            f'    <rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="6" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
            f"{text}\n"
            f"  </g>"
        )

    # Legend, positioned below every boundary box as the build prompt requires.
    legend_items = [
        ("ingest", "Streaming"),
        ("agentic", "Agent workflow"),
        ("datastore", "State"),
        ("serving", "Human loop"),
        ("evalnode", "Evaluation"),
        ("obsnode", "Observability"),
        ("externalnode", "External"),
    ]
    lowest = max(by + bh for _, (_, by, _, bh) in BOUNDARY_BOX.items())
    if lowest >= LEGEND_Y:
        raise SystemExit(
            f"The legend at y={LEGEND_Y} overlaps a boundary ending at y={lowest}. The build "
            "prompt requires it outside all boundaries."
        )
    parts.append('  <g class="legend" data-legend="outside-all-boundaries">')
    parts.append(f'    <text x="60" y="{LEGEND_Y - 16}" class="boundary-label">Legend</text>')
    for index, (kind, label) in enumerate(legend_items):
        lx = 60 + index * 168
        fill, stroke = PALETTE[kind]
        parts.append(
            f'    <rect x="{lx}" y="{LEGEND_Y}" width="18" height="18" rx="3" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>\n'
            f'    <text x="{lx + 26}" y="{LEGEND_Y + 13}" class="legend-label">'
            f"{html.escape(label)}</text>"
        )
    parts.append("  </g>")

    body = "\n".join(parts)
    counts = (
        f"{len(diagram.nodes)} components, {len(diagram.edges)} connections, "
        f"{len(diagram.boundary_titles)} boundaries"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Anomaly Desk architecture</title>
<!--
  Generated by scripts/render_architecture.py from the Mermaid source in README.md.
  Do not edit by hand: scripts/diagram_sync.py runs in continuous integration and fails when
  this page and the Mermaid source disagree. To change the architecture, edit the Mermaid
  source, adjust POSITION and KIND in the generator, and regenerate.

  Self-contained by requirement: no external stylesheet, font, script, or image.
-->
<style>
  :root {{ color-scheme: dark; }}
  body {{
    margin: 0; padding: 2rem 1.5rem; background: #0d1117; color: #e6edf3;
    font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }}
  main {{ max-width: {WIDTH}px; margin: 0 auto; }}
  h1 {{ font-size: 1.25rem; margin: 0 0 0.25rem; }}
  p.sub {{ color: #8b949e; font-size: 0.85rem; margin: 0 0 1.5rem; }}
  svg {{ width: 100%; height: auto; display: block; }}
  .boundary-label {{ fill: #8b949e; font-size: 13px; letter-spacing: 0.04em; }}
  .node-label {{ fill: #e6edf3; font-size: 11px; text-anchor: middle; }}
  .node-label.strong {{ font-size: 12px; font-weight: 600; }}
  .legend-label {{ fill: #c9d1d9; font-size: 12px; }}
  .edge {{ stroke: #6e7681; stroke-width: 1.4; fill: none; }}
  .node rect {{ transition: filter 120ms ease; }}
  .node:hover rect {{ filter: brightness(1.45); }}
  footer {{ color: #8b949e; font-size: 0.78rem; margin-top: 1.5rem; }}
  a {{ color: #58a6ff; }}
</style>
</head>
<body>
<main>
  <h1>Anomaly Desk</h1>
  <p class="sub">
    Agentic triage of a continuous operational event stream, with two scoreboards that are
    allowed to disagree. {counts}. Generated from the Mermaid source in README.md section 2.
  </p>
  <svg viewBox="0 0 {WIDTH} {HEIGHT}" role="img"
       aria-label="Anomaly Desk system architecture, {counts}">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#6e7681"/>
    </marker>
  </defs>
{body}
  </svg>
  <footer>
    Specification: README.md section 2. Execution plan: BREAKDOWN.md. The agent workflow and
    the evaluation plane are drawn with solid boundaries; the legend sits outside every
    boundary.
  </footer>
</main>
</body>
</html>
"""


def main() -> int:
    diagram = parse_mermaid(README.read_text(encoding="utf-8"))

    # Recover labels, which parse_mermaid does not retain.
    import re

    block = re.search(r"```mermaid\n(flowchart TB\n.*?)```", README.read_text(), re.S).group(1)
    labels = {
        m.group(1): m.group(3)
        for m in (re.match(r'^\s+(\w+)(\[+\(?)"([^"]*)"', line) for line in block.splitlines())
        if m
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(diagram, labels), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
