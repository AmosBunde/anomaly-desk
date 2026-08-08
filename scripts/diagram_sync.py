#!/usr/bin/env python3
"""Fail when the Mermaid source in README.md and the Archify specifications disagree.

Specification section 2 requires the diagrams to describe the same system, and requires any
pull request that moves a boundary, adds an agent, or changes a store to update both. A
requirement enforced only by remembering is not enforced: between A16 and A38 the
architecture changes repeatedly, and a diagram that no longer describes the system is worse
than no diagram, because it is trusted.

A6 compared the Mermaid source against ``data-node`` attributes in a page my own generator
emitted. A41 replaced that generator with Archify, whose output markup is not mine to depend
on, so the comparison now runs against the Archify **specifications**. That is the more
honest boundary: the specification's own diagram against the specification that claims to
render it, with the rendered HTML guaranteed by Archify's own showcase validation.

Archify's showcase profile favours roughly twelve primary nodes against the Mermaid source's
twenty-one, so some nodes are merged. Every merge is declared in
``architecture/consolidations.json`` with a reason, which lets this check tell an intended
consolidation apart from an accidental omission. That distinction is the whole point: a
silent drop and a reviewed merge look identical to a set comparison.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"
ARCH_SPEC = REPO_ROOT / "architecture" / "system.architecture.json"
SEQ_SPEC = REPO_ROOT / "architecture" / "triage.sequence.json"
CONSOLIDATIONS = REPO_ROOT / "architecture" / "consolidations.json"

FLOWCHART_RE = re.compile(r"```mermaid\n(flowchart TB\n.*?)```", re.S)
SEQUENCE_RE = re.compile(r"```mermaid\n(sequenceDiagram\n.*?)```", re.S)
SUBGRAPH_RE = re.compile(r'^\s*subgraph\s+(\w+)\["([^"]+)"\]', re.M)
END_RE = re.compile(r"^\s*end\s*$", re.M)
DECLARATION_RE = re.compile(r'^\s+(\w+)\[+\(?"([^"]*)"')
EDGE_SEGMENT_RE = re.compile(r"(\w+)\s*(-\.->|-->)\s*(?:\|[^|]*\|\s*)?")
PARTICIPANT_RE = re.compile(r"^\s*participant\s+(\w+)\s+as\s+(.+)$", re.M)
ACTOR_RE = re.compile(r"^\s*actor\s+(\w+)\s+as\s+(.+)$", re.M)

# Boundaries the build prompt names explicitly. Their Archify labels must exist.
REQUIRED_BOUNDARIES = ["Agent workflow boundary", "Evaluation plane"]


@dataclass
class Flowchart:
    nodes: set[str] = field(default_factory=set)
    edges: set[tuple[str, str]] = field(default_factory=set)
    boundaries: dict[str, str] = field(default_factory=dict)
    boundary_titles: dict[str, str] = field(default_factory=dict)


def parse_flowchart(text: str) -> Flowchart:
    match = FLOWCHART_RE.search(text)
    if not match:
        print("No Mermaid flowchart found in README.md", file=sys.stderr)
        sys.exit(2)

    chart = Flowchart()
    stack: list[str] = []
    for line in match.group(1).splitlines():
        if not line.strip() or line.strip().startswith(("classDef", "flowchart", "%%")):
            continue
        sub = SUBGRAPH_RE.match(line)
        if sub:
            stack.append(sub.group(1))
            chart.boundary_titles[sub.group(1)] = sub.group(2)
            continue
        if END_RE.match(line):
            if stack:
                stack.pop()
            continue
        declaration = DECLARATION_RE.match(line)
        if declaration:
            chart.nodes.add(declaration.group(1))
            if stack:
                chart.boundaries[declaration.group(1)] = stack[-1]
            continue
        segments = EDGE_SEGMENT_RE.findall(line)
        if segments:
            tail = EDGE_SEGMENT_RE.sub("", line).strip()
            target = re.match(r"(\w+)", tail)
            sequence = [s[0] for s in segments]
            if target:
                sequence.append(target.group(1))
            for left, right in zip(sequence, sequence[1:], strict=False):
                chart.edges.add((left, right))
    return chart


def parse_sequence_participants(text: str) -> set[str]:
    match = SEQUENCE_RE.search(text)
    if not match:
        print("No Mermaid sequenceDiagram found in README.md", file=sys.stderr)
        sys.exit(2)
    block = match.group(1)
    return {m.group(1) for m in PARTICIPANT_RE.finditer(block)} | {
        m.group(1) for m in ACTOR_RE.finditer(block)
    }


def check_architecture(chart: Flowchart, spec: dict, mapping: dict) -> list[str]:
    problems: list[str] = []
    node_map: dict[str, str | None] = mapping["map"]
    reasons: dict[str, str] = mapping["reasons"]
    components = {c["id"] for c in spec["components"]}

    unmapped = sorted(chart.nodes - set(node_map))
    if unmapped:
        problems.append(
            f"Mermaid nodes with no entry in consolidations.json: {unmapped}. Add each to the "
            "map, pointing at an Archify component, or at null with a reason if it is carried "
            "in a card."
        )

    stale = sorted(set(node_map) - chart.nodes)
    if stale:
        problems.append(
            f"consolidations.json maps nodes that no longer exist in the Mermaid source: "
            f"{stale}. Remove them."
        )

    for node, target in sorted(node_map.items()):
        if target is not None and target not in components:
            problems.append(
                f"Mermaid node {node!r} maps to Archify component {target!r}, which the "
                f"specification does not define."
            )

    claimed = {t for t in node_map.values() if t is not None}
    orphans = sorted(components - claimed)
    if orphans:
        problems.append(
            f"Archify components no Mermaid node claims: {orphans}. Either add the node to the "
            "specification diagram or remove the component; an unclaimed component means the "
            "picture asserts something the specification does not."
        )

    # A merge or a drop must carry a reason, so a silent omission cannot pass as a decision.
    targets: dict[str | None, list[str]] = {}
    for node, target in node_map.items():
        targets.setdefault(target, []).append(node)
    for target, nodes in sorted(targets.items(), key=lambda kv: str(kv[0])):
        merged = len(nodes) > 1
        dropped = target is None
        if not (merged or dropped):
            continue
        for node in sorted(nodes):
            # The node that keeps its own identity needs no justification.
            if not dropped and node == target:
                continue
            if node not in reasons:
                problems.append(
                    f"Mermaid node {node!r} is "
                    + ("dropped to a card" if dropped else f"merged into {target!r}")
                    + " with no entry in reasons. Every consolidation is reviewed, so state why."
                )

    labels = {b["label"] for b in spec.get("boundaries", [])}
    for required in REQUIRED_BOUNDARIES:
        if required not in labels:
            problems.append(
                f"Boundary {required!r} is required by the build prompt and is missing from the "
                f"Archify boundaries: {sorted(labels)}"
            )

    # Every Mermaid edge must survive as a relationship between the mapped components, unless
    # both ends collapsed into one component, in which case it became internal.
    connections = {(c["from"], c["to"]) for c in spec.get("connections", [])}
    for left, right in sorted(chart.edges):
        target_left = node_map.get(left)
        target_right = node_map.get(right)
        if target_left is None or target_right is None:
            continue
        if target_left == target_right:
            continue
        if (target_left, target_right) not in connections:
            problems.append(
                f"Mermaid edge {left} -> {right} maps to {target_left} -> {target_right}, which "
                "the Archify specification does not connect."
            )
    return problems


def check_sequence(participants: set[str], spec: dict, mapping: dict) -> list[str]:
    problems: list[str] = []
    seq_map: dict[str, str | None] = mapping["sequence_map"]
    reasons: dict[str, str] = mapping["sequence_reasons"]
    declared = {p["id"] for p in spec["participants"]}

    unmapped = sorted(participants - set(seq_map))
    if unmapped:
        problems.append(f"Mermaid sequence participants with no mapping: {unmapped}")
    stale = sorted(set(seq_map) - participants)
    if stale:
        problems.append(f"sequence_map references participants that no longer exist: {stale}")

    for source, target in sorted(seq_map.items()):
        if target is not None and target not in declared:
            problems.append(
                f"Sequence participant {source!r} maps to {target!r}, which the Archify "
                f"sequence does not declare."
            )

    claimed = {t for t in seq_map.values() if t is not None}
    orphans = sorted(declared - claimed)
    if orphans:
        problems.append(f"Archify sequence participants no Mermaid lifeline claims: {orphans}")

    targets: dict[str | None, list[str]] = {}
    for source, target in seq_map.items():
        targets.setdefault(target, []).append(source)
    for target, sources in targets.items():
        if len(sources) > 1 or target is None:
            for source in sorted(sources):
                if source not in reasons:
                    problems.append(
                        f"Sequence participant {source!r} is consolidated with no reason given."
                    )
    return problems


def main() -> int:
    for path in (ARCH_SPEC, SEQ_SPEC, CONSOLIDATIONS):
        if not path.exists():
            print(f"{path.relative_to(REPO_ROOT)} does not exist", file=sys.stderr)
            return 2

    readme = README.read_text(encoding="utf-8")
    chart = parse_flowchart(readme)
    participants = parse_sequence_participants(readme)
    arch = json.loads(ARCH_SPEC.read_text(encoding="utf-8"))
    seq = json.loads(SEQ_SPEC.read_text(encoding="utf-8"))
    mapping = json.loads(CONSOLIDATIONS.read_text(encoding="utf-8"))

    print("diagram_sync: comparing README.md Mermaid against the Archify specifications")
    problems = check_architecture(chart, arch, mapping)
    problems += check_sequence(participants, seq, mapping)

    if problems:
        for problem in problems:
            print(f"  {problem}")
        print(
            "\nSpecification section 2 requires both representations to change together.",
            file=sys.stderr,
        )
        return 1

    merges = sum(1 for v in mapping["map"].values() if v is not None)
    print(
        f"  flowchart: {len(chart.nodes)} Mermaid nodes -> "
        f"{len(arch['components'])} Archify components "
        f"({merges - len(arch['components'])} merged, "
        f"{sum(1 for v in mapping['map'].values() if v is None)} carried in cards)"
    )
    print(
        f"  sequence:  {len(participants)} Mermaid lifelines -> "
        f"{len(seq['participants'])} Archify participants"
    )
    print(f"  {len(chart.edges)} Mermaid edges all present as Archify relationships")
    print("  in sync")
    return 0


if __name__ == "__main__":
    sys.exit(main())
