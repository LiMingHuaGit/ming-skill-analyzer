# Analysis JSON Schema

`analysis.json` is authored from `analysis-template.json`. Preserve `schema_version: 2`.

## Root fields

```json
{
  "schema_version": 2,
  "scenario": {
    "prompt": "User request being simulated",
    "invocation_mode": "automatic",
    "context_summary": "Known context and important unknowns",
    "selected_nodes": ["request", "match", "load"],
    "selected_edges": ["request-match", "match-load"]
  },
  "overview": {
    "summary": "What the Skill does and how the simulation resolves",
    "routing_score": 0,
    "routing_label": "matched",
    "strengths": ["Evidence-backed strength"],
    "risks": ["Evidence-backed risk"]
  },
  "capabilities": [],
  "input_classes": [],
  "lanes": [],
  "nodes": [],
  "edges": [],
  "findings": []
}
```

`invocation_mode` is `automatic`, `explicit`, or `unknown`. `routing_score` is an explanatory integer from 0 to 100. `routing_label` is `matched`, `not-matched`, `ambiguous`, or `unknown`. `selected_nodes` and `selected_edges` identify the representative path for the scenario.

## Capability

```json
{
  "id": "my-capability",
  "title": "Human-readable name",
  "summary": "What this capability does",
  "input_patterns": ["Typical input or trigger phrase"],
  "outputs": ["Produced artifact or decision"],
  "entry_nodes": ["node-id"],
  "evidence": []
}
```

## Input class

```json
{
  "id": "my-input-class",
  "title": "Human-readable name",
  "condition": "When this input class applies",
  "excluded_when": ["Condition that rules it out"],
  "routes_to": ["node-id"],
  "capability_ids": ["my-capability"],
  "examples": ["Example user request"],
  "evidence": []
}
```

## Lane

```json
{ "id": "routing", "label": "Routing & scope" }
```

Lanes group nodes visually in the flowchart. Assign each node a `lane` id that matches one of the declared lanes.

## Node

```json
{
  "id": "match",
  "lane": "routing",
  "column": 2,
  "row": 0,
  "type": "decision",
  "title": "Match Skill",
  "status": "matched",
  "summary": "Short outcome",
  "analysis": "Reasoned explanation",
  "entry_conditions": ["Condition that brings flow here"],
  "blockers": ["What would block this node"],
  "capability_ids": ["my-capability"],
  "inputs": ["Input or condition"],
  "outputs": ["Produced decision or data"],
  "resources": ["references/example.md"],
  "next": ["load"],
  "evidence": [
    {
      "file": "SKILL.md",
      "line_start": 2,
      "line_end": 3,
      "excerpt": "Short exact or faithful excerpt",
      "kind": "source"
    }
  ]
}
```

Node `type` is one of `start`, `terminal`, `action`, `decision`, `tool`, `gate`, `validation`, `wait`, or `blocked`. Node `status` is one of `pending`, `active`, `matched`, `skipped`, `succeeded`, `failed`, or `blocked`. `column` and `row` control SVG layout position (0-indexed integers). Evidence `kind` is `source` or `inference`. Every resource and source evidence file must exist in `facts.json`.

## Edge

```json
{
  "id": "match-load",
  "from": "match",
  "to": "load",
  "label": "Matched",
  "condition": "Positive signals exceed threshold",
  "blockers": ["What would prevent this transition"],
  "outcome": "continue",
  "variant": "emphasis",
  "evidence": []
}
```

`outcome` is one of `continue`, `branch`, `fallback`, `retry`, `wait`, `success`, or `stop`. `variant` is one of `default`, `emphasis`, `dashed`, or `security`.

## Finding

```json
{
  "id": "my-finding",
  "category": "strength",
  "severity": "info",
  "title": "Progressive resource loading",
  "analysis": "Why it improves reliability or cost",
  "evidence": []
}
```

Finding `category` is one of `strength`, `risk`, `boundary`, `maintainability`, `efficiency`, or `teaching-value`. `severity` is `info`, `low`, `medium`, or `high`. Findings use the same evidence structure as nodes.

