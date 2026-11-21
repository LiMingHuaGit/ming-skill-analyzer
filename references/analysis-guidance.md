# Analysis Guidance

## Goal

Explain how the target Skill is likely to participate in an Agent workflow while keeping observed facts separate from interpretation. The report should help a reader learn why the Skill is useful, where its boundaries are, and what evidence supports each conclusion.

## Language

Write all semantic analysis content — node titles, summaries, analysis text, capability descriptions, input class conditions and examples, finding titles and analysis — in the **same language as the user's request**. If the request is in English, write in English. If in Chinese, write in Chinese. The scanner output (`facts.json`) is language-neutral and does not change. After completing the analysis, pass the matching `--lang` flag to `render_report.py` so the report UI also matches.

## Schema version

`analysis.json` uses **schema version 2**. The root object must include `schema_version: 2` and the following arrays (may be empty but must be present): `capabilities`, `input_classes`, `lanes`, `nodes`, `edges`, `findings`. See `references/analysis-schema.md` for the full field specification.

## Capabilities and input classes

Before writing nodes, enumerate the target Skill's capability families and input classes from `facts.json` signals and `SKILL.md` body content.

**Capability** — a coherent group of things the Skill can do, sharing the same entry points and evidence:
- Give it a stable `id` (kebab-case), a short `title`, and a `summary`.
- List representative `input_patterns`, expected `outputs`, and `entry_nodes` (node ids where this capability enters the flow).
- Attach at least one source evidence item.

**Input class** — a distinct kind of user request and what it routes to:
- Give it a stable `id`, a `condition` (when it applies), and `excluded_when` (conditions that rule it out).
- List `routes_to` node ids and `capability_ids` it activates.
- Attach source evidence.

## Lanes and graph layout

Declare one lane per logical phase (e.g. `routing`, `preparation`, `execution`, `quality`, `outcome`). Each node gets a `lane` id, a `column` (0-indexed, left to right within the lane), and a `row` (0-indexed, top to bottom for parallel paths).

## Required flow nodes

Use these node identifiers and keep them in this order unless a node is genuinely inapplicable:

1. `discover` — where the Skill is found and which metadata is resident.
2. `request` — the simulated user request and available context.
3. `match` — direct invocation or metadata-based selection.
4. `load` — full `SKILL.md` instructions, boundaries, and stop conditions.
5. `resources` — references, scripts, assets, templates, or other Skills selected on demand.
6. `plan` — the next actions and important branches.
7. `tools` — commands, MCP tools, APIs, or file operations that would be used.
8. `verify` — completion evidence and the failure-to-plan loop.
9. `reply` — result, risks, unresolved items, and feedback entering the next turn.

Use `skipped` when the stage does not apply. Use `blocked` when required evidence or capability is missing. Do not remove a stage merely to make the diagram look successful.

Each node must include `entry_conditions`, `blockers`, and `capability_ids` in addition to the standard fields. Set `type` to one of `start`, `terminal`, `action`, `decision`, `tool`, `gate`, `validation`, `wait`, or `blocked`.

## Edges

For every meaningful transition between nodes, declare an edge with `from`, `to`, `label`, `condition`, `blockers`, `outcome`, and `variant`. Declare branch edges (decisions, retries, fallbacks) explicitly — they power the flowchart and the flow tree. `outcome` is one of `continue`, `branch`, `fallback`, `retry`, `wait`, `success`, or `stop`. `variant` is `default`, `emphasis`, `dashed`, or `security`.

## Routing Analysis

- Treat explicit invocation as a deterministic routing signal.
- For automatic matching, compare the scenario with frontmatter `name` and `description` first.
- Use body instructions to explain behavior after selection, not to invent resident routing metadata.
- State positive signals, negative boundaries, ambiguous overlaps, and missing catalog context.
- Scores are explanatory heuristics. Label them as simulated and provide the contributing evidence.

## Evidence Rules

- Cite paths relative to the target Skill.
- Use exact line ranges from `facts.json` when possible.
- Keep excerpts short and relevant.
- Use evidence kind `source` for file facts and `inference` only for a clearly labeled interpretation.
- Do not cite skipped, binary, sensitive, or truncated content as if it had been fully read.
- A missing reference, dependency, or validation step is a finding only when the available evidence supports that claim.

## Resource Selection

Explain both what would be loaded and what would remain unloaded. Prefer progressive disclosure:

- Load a reference when a decision point requires its details.
- Use a script when the task needs its deterministic computation.
- Use an asset when it is copied, transformed, or used as a stable template.
- Do not mark every file as loaded merely because it exists.

## Findings

Use these categories where relevant: `strength`, `risk`, `boundary`, `maintainability`, `efficiency`, and `teaching-value`. Severity is `info`, `low`, `medium`, or `high`.

A useful finding contains a concise claim, why it matters, and evidence. Avoid generic praise such as “well structured” without identifying the structure and its effect.

## Stop Conditions

Stop and report the limitation when:

- `SKILL.md` is missing or unreadable.
- The target is dominated by sensitive or unsupported content.
- The request requires executing the target rather than analyzing it.
- Strict validation cannot connect important conclusions to real files.

