# ming-skill-analyzer

Analyze an Agent Skill and generate a live interactive HTML report with a dynamic flowchart, source browser, and evidence-linked findings. Every conclusion links back to redacted source content and line ranges.

This Skill is for understanding, teaching, comparing, and auditing workflow design. It does not execute or modify the target Skill.

## What it produces

- A three-panel interactive HTML report: file tree, analysis report, and animated SVG flowchart.
- Clickable nodes with AI interpretation, entry conditions, blockers, inputs, outputs, and evidence.
- A live source browser for the target Skill's readable files (served locally via `serve_report.py`).
- Capability catalog, input routing matrix, and findings grouped by strength / risk / boundary.
- Machine-readable `facts.json` and `analysis.json` (schema version 2).

## Installation

Copy the `ming-skill-analyzer` directory into a Skill directory recognized by your Agent host. If it is later published to a repository, give the repository URL to an Agent for installation.

## Configuration

No API key or persistent configuration is required. The scripts use only Python 3.10+ standard-library modules.

## Usage

Example requests:

- “Analyze this Skill and generate an interactive trigger-flow report.”
- “Show why this Skill would or would not trigger for this request.”
- “Create a learning report for this Skill with clickable source evidence.”

Provide the target Skill path, a realistic user request to simulate when possible, and the directory where the analysis artifacts should be written. If the output directory is omitted, the Skill asks for it before scanning.

## Compatibility

The deterministic scripts require Python 3.10 or newer. They are designed to be platform-neutral, but have initially been verified on macOS with Python 3.12. The host must provide file reading and writing capabilities. Viewing the generated report requires a modern browser and a running `serve_report.py` instance for live file preview.

## Privacy, data, permissions, and boundaries

Analysis stays local unless the host itself sends context to a remote model. The scanner does not use the network, execute target code, or install dependencies. It skips likely credential files, redacts common secret patterns, limits embedded text size, and records skipped content in `facts.json`.

The report is a reasoned simulation. It does not expose or reproduce hidden model routing probabilities and is not proof of an actual runtime trace.

## Output

The user chooses an output directory outside the target Skill. Because the output contains source excerpts and AI analysis, no default location is selected silently. A completed run contains `facts.json`, `analysis-template.json`, `analysis.json`, and `report.html`.

Open the report with the live server for full functionality:

```bash
python3 scripts/render_report.py facts.json analysis.json --output report.html --live
python3 scripts/serve_report.py --report report.html --skill-root <target> --open
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

