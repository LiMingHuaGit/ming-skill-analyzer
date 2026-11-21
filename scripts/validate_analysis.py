#!/usr/bin/env python3
"""Validate analyzer JSON and ensure evidence points to scanned source files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

NODE_STATUSES = {"pending", "active", "matched", "skipped", "succeeded", "failed", "blocked"}
ROUTING_LABELS = {"matched", "not-matched", "ambiguous", "unknown"}
INVOCATION_MODES = {"automatic", "explicit", "unknown"}
EVIDENCE_KINDS = {"source", "inference"}
REQUIRED_NODE_IDS = ["discover", "request", "match", "load", "resources", "plan", "tools", "verify", "reply"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("facts", type=Path)
    parser.add_argument("analysis", type=Path)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    args = parse_args()
    try:
        facts = load_json(args.facts)
        analysis = load_json(args.analysis)
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    errors: list[str] = []
    warnings: list[str] = []
    file_map = {item.get("path"): item for item in facts.get("files", []) if item.get("path")}
    if analysis.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    scenario = analysis.get("scenario", {})
    if scenario.get("invocation_mode") not in INVOCATION_MODES:
        errors.append("scenario.invocation_mode is invalid")
    overview = analysis.get("overview", {})
    if overview.get("routing_label") not in ROUTING_LABELS:
        errors.append("overview.routing_label is invalid")
    score = overview.get("routing_score")
    if not isinstance(score, int) or not 0 <= score <= 100:
        errors.append("overview.routing_score must be an integer from 0 to 100")

    nodes = analysis.get("nodes")
    if not isinstance(nodes, list):
        errors.append("nodes must be an array")
        nodes = []
    ids = [node.get("id") for node in nodes if isinstance(node, dict)]
    if len(ids) != len(set(ids)):
        errors.append("node ids must be unique")
    missing = [node_id for node_id in REQUIRED_NODE_IDS if node_id not in ids]
    if missing:
        errors.append("missing required nodes: " + ", ".join(missing))

    def validate_evidence(items: object, location: str) -> None:
        if not isinstance(items, list):
            errors.append(f"{location}.evidence must be an array")
            return
        for index, evidence in enumerate(items):
            prefix = f"{location}.evidence[{index}]"
            if not isinstance(evidence, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if evidence.get("kind") not in EVIDENCE_KINDS:
                errors.append(f"{prefix}.kind is invalid")
            source = evidence.get("file")
            if source not in file_map:
                errors.append(f"{prefix}.file does not exist in facts: {source}")
                continue
            line_start = evidence.get("line_start")
            line_end = evidence.get("line_end")
            line_count = file_map[source].get("line_count")
            if line_start is not None and (not isinstance(line_start, int) or line_start < 1):
                errors.append(f"{prefix}.line_start must be a positive integer")
            if line_end is not None and (not isinstance(line_end, int) or line_end < (line_start or 1)):
                errors.append(f"{prefix}.line_end must be at or after line_start")
            if isinstance(line_count, int) and isinstance(line_end, int) and line_end > line_count:
                errors.append(f"{prefix}.line_end exceeds scanned line count")

    node_id_set = set(ids)
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"nodes[{index}] must be an object")
            continue
        location = f"nodes[{index}]"
        if node.get("status") not in NODE_STATUSES:
            errors.append(f"{location}.status is invalid")
        for target in node.get("next", []):
            if target not in node_id_set:
                errors.append(f"{location}.next references unknown node: {target}")
        for resource in node.get("resources", []):
            if resource not in file_map:
                errors.append(f"{location}.resources references unknown file: {resource}")
        validate_evidence(node.get("evidence", []), location)
        if args.strict and node.get("status") != "skipped":
            if not str(node.get("summary", "")).strip():
                errors.append(f"{location}.summary is required in strict mode")
            if not str(node.get("analysis", "")).strip():
                errors.append(f"{location}.analysis is required in strict mode")

    findings = analysis.get("findings", [])
    if not isinstance(findings, list):
        errors.append("findings must be an array")
        findings = []
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"findings[{index}] must be an object")
            continue
        validate_evidence(finding.get("evidence", []), f"findings[{index}]")
        if args.strict and not str(finding.get("analysis", "")).strip():
            errors.append(f"findings[{index}].analysis is required in strict mode")

    if args.strict and not str(scenario.get("prompt", "")).strip():
        errors.append("scenario.prompt is required in strict mode")
    if args.strict and not str(overview.get("summary", "")).strip():
        errors.append("overview.summary is required in strict mode")
    if not findings:
        warnings.append("no findings were recorded")

    # Quality metrics
    total_nodes = len([n for n in nodes if isinstance(n, dict)])
    nodes_with_evidence = sum(
        1 for n in nodes if isinstance(n, dict) and n.get("evidence")
    )
    all_evidence = [
        ev
        for n in nodes if isinstance(n, dict)
        for ev in (n.get("evidence") or [])
        if isinstance(ev, dict)
    ]
    all_evidence += [
        ev
        for f in findings if isinstance(f, dict)
        for ev in (f.get("evidence") or [])
        if isinstance(ev, dict)
    ]
    inference_count = sum(1 for ev in all_evidence if ev.get("kind") == "inference")
    total_evidence = len(all_evidence)
    inference_ratio = round(inference_count / total_evidence, 4) if total_evidence else 0.0
    evidence_coverage = round(nodes_with_evidence / total_nodes, 4) if total_nodes else 0.0
    unsupported_claims = sum(
        1 for n in nodes if isinstance(n, dict) and not n.get("evidence") and n.get("status") not in {"skipped", "pending"}
    )

    if args.strict and evidence_coverage < 0.9:
        warnings.append(f"evidence_coverage {evidence_coverage:.0%} is below the 90% threshold")
    if args.strict and unsupported_claims > 0:
        warnings.append(f"{unsupported_claims} active node(s) have no evidence")

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps({
        "status": "ok",
        "nodes": len(nodes),
        "findings": len(findings),
        "warnings": len(warnings),
        "evidence_coverage": evidence_coverage,
        "inference_ratio": inference_ratio,
        "unsupported_claims": unsupported_claims,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
