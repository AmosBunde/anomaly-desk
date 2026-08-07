#!/usr/bin/env python3
"""Fail when the Mermaid source in README.md and docs/architecture.html disagree.

Specification section 2 requires the two representations to stay in sync, and that any pull
request moving a component boundary, adding an agent, or changing a store updates both. A
requirement enforced only by remembering is not enforced: between A16 and A38 the
architecture changes repeatedly, and a diagram that no longer describes the system is worse
than no diagram, because it is trusted.

The comparison is structural, not visual. It asserts the two files describe the same nodes,
the same edges, and the same boundary membership. It says nothing about position, size, or
color, because a check that fails when a box moves four pixels gets switched off within a
week.

The correspondence runs through identifiers carried in both representations: the Mermaid node
identifier, and a ``data-node`` attribute on the matching SVG group.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
PAGE = REPO_ROOT / "docs" / "architecture.html"

MERMAID_BLOCK_RE = re.compile(r"```mermaid\n(flowchart TB\n.*?)```", re.S)
SUBGRAPH_RE = re.compile(r'^\s*subgraph\s+(\w+)\["([^"]+)"\]', re.M)
END_RE = re.compile(r"^\s*end\s*$", re.M)
# A declaration is an identifier followed by any bracket shape Mermaid supports:
# id["x"], id[("x")], id[["x"]]. The class suffix is optional.
DECLARATION_RE = re.compile(r'^\s+(\w+)(\[+\(?)"([^"]*)"')
# Edges may be solid or dotted, may carry a |label|, and may chain: a --> b --> c.
EDGE_SEGMENT_RE = re.compile(r"(\w+)\s*(-\.->|-->)\s*(?:\|[^|]*\|\s*)?")


@dataclass
class Diagram:
    nodes: set[str] = field(default_factory=set)
    edges: set[tuple[str, str]] = field(default_factory=set)
    boundaries: dict[str, str] = field(default_factory=dict)  # node -> boundary id
    boundary_titles: dict[str, str] = field(default_factory=dict)


def parse_mermaid(text: str) -> Diagram:
    match = MERMAID_BLOCK_RE.search(text)
    if not match:
        print("No Mermaid flowchart found in README.md", file=sys.stderr)
        sys.exit(2)

    diagram = Diagram()
    stack: list[str] = []

    for line in match.group(1).splitlines():
        if line.strip().startswith(("classDef", "flowchart", "%%")) or not line.strip():
            continue

        sub = SUBGRAPH_RE.match(line)
        if sub:
            stack.append(sub.group(1))
            diagram.boundary_titles[sub.group(1)] = sub.group(2)
            continue
        if END_RE.match(line):
            if stack:
                stack.pop()
            continue

        declaration = DECLARATION_RE.match(line)
        if declaration:
            node = declaration.group(1)
            diagram.nodes.add(node)
            if stack:
                diagram.boundaries[node] = stack[-1]
            continue

        # Edge line. Walk chained segments so a --> b --> c yields two edges.
        segments = EDGE_SEGMENT_RE.findall(line)
        if segments:
            tail = EDGE_SEGMENT_RE.sub("", line).strip()
            target = re.match(r"(\w+)", tail)
            sequence = [seg[0] for seg in segments]
            if target:
                sequence.append(target.group(1))
            for left, right in zip(sequence, sequence[1:], strict=False):
                diagram.edges.add((left, right))

    return diagram


def parse_page(text: str) -> Diagram:
    diagram = Diagram()
    for node, boundary in re.findall(r'data-node="(\w+)"(?:\s+data-boundary="(\w*)")?', text):
        diagram.nodes.add(node)
        if boundary:
            diagram.boundaries[node] = boundary
    for left, right in re.findall(r'data-edge="(\w+)->(\w+)"', text):
        diagram.edges.add((left, right))
    for boundary, title in re.findall(r'data-boundary-title="(\w+):([^"]*)"', text):
        diagram.boundary_titles[boundary] = title
    return diagram


def report(label: str, missing: set, extra: set) -> bool:
    if not missing and not extra:
        return False
    if missing:
        print(f"  {label} in README.md but not in architecture.html: {sorted(missing)}")
    if extra:
        print(f"  {label} in architecture.html but not in README.md: {sorted(extra)}")
    return True


def main() -> int:
    if not PAGE.exists():
        print(f"{PAGE.relative_to(REPO_ROOT)} does not exist", file=sys.stderr)
        return 2

    source = parse_mermaid(README.read_text(encoding="utf-8"))
    page = parse_page(PAGE.read_text(encoding="utf-8"))

    # An SVG group that looks like a component but carries no identifier would make the
    # comparison silently pass, so the absence of identifiers is itself a failure.
    if not page.nodes:
        print(
            "architecture.html declares no data-node attributes, so nothing can be "
            "compared. Every component group needs data-node and data-boundary.",
            file=sys.stderr,
        )
        return 1

    failed = False
    print("diagram_sync: comparing README.md Mermaid against docs/architecture.html")

    failed |= report("nodes", source.nodes - page.nodes, page.nodes - source.nodes)
    failed |= report("edges", source.edges - page.edges, page.edges - source.edges)

    shared = source.nodes & page.nodes
    misplaced = {
        node: (source.boundaries.get(node), page.boundaries.get(node))
        for node in shared
        if source.boundaries.get(node) != page.boundaries.get(node)
    }
    if misplaced:
        failed = True
        print("  boundary membership differs:")
        for node, (expected, actual) in sorted(misplaced.items()):
            print(f"    {node}: README says {expected!r}, page says {actual!r}")

    failed |= report(
        "boundaries",
        set(source.boundary_titles) - set(page.boundary_titles),
        set(page.boundary_titles) - set(source.boundary_titles),
    )

    if failed:
        print(
            "\nSpecification section 2 requires both representations to change together.",
            file=sys.stderr,
        )
        return 1

    print(
        f"  {len(source.nodes)} nodes, {len(source.edges)} edges, "
        f"{len(source.boundary_titles)} boundaries: in sync"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
