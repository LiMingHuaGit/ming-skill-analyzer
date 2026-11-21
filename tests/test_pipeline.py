from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.skill = self.base / "demo-skill"
        (self.skill / "references").mkdir(parents=True)
        (self.skill / "scripts").mkdir()
        (self.skill / "SKILL.md").write_text(
            """---
name: demo-skill
description: Analyze CSV files when the user requests a data-quality report.
---
# Demo
Read [the rubric](references/rubric.md) when scoring data.
Run `python3 scripts/check.py` and verify the result.
""",
            encoding="utf-8",
        )
        (self.skill / "references" / "rubric.md").write_text("# Rubric\nCheck missing values.\n", encoding="utf-8")
        (self.skill / "scripts" / "check.py").write_text("print('ok')\n", encoding="utf-8")
        self.output = self.base / "output"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_script(self, script: str, *args: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_scan_validate_and_render(self) -> None:
        scan = self.run_script(
            "scan_skill.py", self.skill, "--output-dir", self.output,
            "--prompt", "Check this CSV for quality problems",
        )
        self.assertEqual(scan.returncode, 0, scan.stderr)
        facts = json.loads((self.output / "facts.json").read_text(encoding="utf-8"))
        self.assertEqual(facts["target"]["name"], "demo-skill")
        self.assertTrue(any(signal["kind"] == "file-reference" for signal in facts["signals"]))

        analysis_path = self.output / "analysis.json"
        analysis = json.loads((self.output / "analysis-template.json").read_text(encoding="utf-8"))
        analysis["scenario"]["invocation_mode"] = "automatic"
        analysis["scenario"]["context_summary"] = "CSV analysis request"
        analysis["schema_version"] = 2
        analysis["capabilities"] = []
        analysis["input_classes"] = []
        analysis["lanes"] = []
        analysis["edges"] = []
        analysis["overview"].update({"summary": "The Skill matches the request.", "routing_score": 88, "routing_label": "matched"})
        for node in analysis["nodes"]:
            node["status"] = "matched" if node["id"] == "match" else "succeeded"
            node["summary"] = f"Completed {node['title']}"
            node["analysis"] = "Evidence-backed test analysis."
        evidence = [{
            "file": "SKILL.md", "line_start": 2, "line_end": 3,
            "excerpt": "name and description", "kind": "source",
        }]
        analysis["nodes"][2]["evidence"] = evidence
        analysis["findings"] = [{
            "category": "strength", "severity": "info", "title": "Clear trigger",
            "analysis": "The description names the task and output.", "evidence": evidence,
        }]
        analysis_path.write_text(json.dumps(analysis), encoding="utf-8")

        validate = self.run_script("validate_analysis.py", self.output / "facts.json", analysis_path, "--strict")
        self.assertEqual(validate.returncode, 0, validate.stderr)
        result = json.loads(validate.stdout)
        self.assertIn("evidence_coverage", result)
        self.assertIn("inference_ratio", result)
        self.assertIn("unsupported_claims", result)

        report = self.output / "report.html"
        render = self.run_script("render_report.py", self.output / "facts.json", analysis_path, "--output", report)
        self.assertEqual(render.returncode, 0, render.stderr)
        html = report.read_text(encoding="utf-8")
        self.assertIn("动态流程图", html)
        self.assertIn("demo-skill", html)

    def test_refuses_to_overwrite_scan_outputs(self) -> None:
        first = self.run_script("scan_skill.py", self.skill, "--output-dir", self.output)
        second = self.run_script("scan_skill.py", self.skill, "--output-dir", self.output)
        self.assertEqual(first.returncode, 0)
        self.assertNotEqual(second.returncode, 0)

    def test_rejects_output_inside_target_skill(self) -> None:
        result = self.run_script(
            "scan_skill.py", self.skill, "--output-dir", self.skill / "analysis-output",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside the target Skill", result.stderr)

    def test_css_at_rules_not_detected_as_skill_reference(self) -> None:
        """@media, @keyframes etc. must not be flagged as skill references."""
        (self.skill / "references" / "style.css").write_text(
            "@media (max-width: 768px) { body { font-size: 14px; } }\n"
            "@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }\n",
            encoding="utf-8",
        )
        scan = self.run_script("scan_skill.py", self.skill, "--output-dir", self.output)
        self.assertEqual(scan.returncode, 0, scan.stderr)
        facts = json.loads((self.output / "facts.json").read_text(encoding="utf-8"))
        skill_signals = [s for s in facts["signals"] if s["kind"] == "other-skill"]
        css_false_positives = [s for s in skill_signals if s["value"].lstrip("@$") in ("media", "keyframes")]
        self.assertEqual(css_false_positives, [], f"CSS at-rules detected as skills: {css_false_positives}")

    def test_email_not_detected_as_skill_reference(self) -> None:
        """Email addresses like @user.com must not be flagged as skill references."""
        (self.skill / "references" / "contact.md").write_text(
            "Contact @admin.example for support.\n",
            encoding="utf-8",
        )
        scan = self.run_script("scan_skill.py", self.skill, "--output-dir", self.output)
        self.assertEqual(scan.returncode, 0, scan.stderr)
        facts = json.loads((self.output / "facts.json").read_text(encoding="utf-8"))
        email_signals = [s for s in facts["signals"] if "admin.example" in s.get("value", "")]
        self.assertEqual(email_signals, [])

    def test_skill_signal_has_confidence_and_detection_rule(self) -> None:
        """Skill signals must include confidence and detection_rule fields."""
        scan = self.run_script("scan_skill.py", self.skill, "--output-dir", self.output)
        self.assertEqual(scan.returncode, 0, scan.stderr)
        facts = json.loads((self.output / "facts.json").read_text(encoding="utf-8"))
        for signal in facts["signals"]:
            self.assertIn("confidence", signal, f"Missing confidence in signal: {signal}")
            self.assertIn("detection_rule", signal, f"Missing detection_rule in signal: {signal}")

    def test_validate_outputs_quality_metrics(self) -> None:
        """validate_analysis.py must output evidence_coverage, inference_ratio, unsupported_claims."""
        self.run_script("scan_skill.py", self.skill, "--output-dir", self.output)
        analysis_path = self.output / "analysis.json"
        analysis = json.loads((self.output / "analysis-template.json").read_text(encoding="utf-8"))
        analysis["scenario"]["invocation_mode"] = "automatic"
        analysis["scenario"]["context_summary"] = "test"
        analysis["overview"].update({"summary": "test", "routing_score": 50, "routing_label": "matched"})
        for node in analysis["nodes"]:
            node["status"] = "succeeded"
            node["summary"] = "done"
            node["analysis"] = "test"
        analysis["findings"] = [{
            "category": "strength", "severity": "info", "title": "T",
            "analysis": "test",
            "evidence": [{"file": "SKILL.md", "line_start": 1, "line_end": 2, "excerpt": "x", "kind": "source"}],
        }]
        analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
        result = self.run_script("validate_analysis.py", self.output / "facts.json", analysis_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertIn("evidence_coverage", out)
        self.assertIn("inference_ratio", out)
        self.assertIn("unsupported_claims", out)
        self.assertIsInstance(out["evidence_coverage"], float)

    def test_inference_ratio_calculated_correctly(self) -> None:
        """Inference evidence should be counted separately from source evidence."""
        self.run_script("scan_skill.py", self.skill, "--output-dir", self.output)
        analysis_path = self.output / "analysis.json"
        analysis = json.loads((self.output / "analysis-template.json").read_text(encoding="utf-8"))
        analysis["scenario"]["invocation_mode"] = "automatic"
        analysis["scenario"]["context_summary"] = "test"
        analysis["overview"].update({"summary": "test", "routing_score": 50, "routing_label": "matched"})
        mixed_evidence = [
            {"file": "SKILL.md", "line_start": 1, "line_end": 1, "excerpt": "x", "kind": "source"},
            {"file": "SKILL.md", "line_start": 2, "line_end": 2, "excerpt": "y", "kind": "inference"},
        ]
        for node in analysis["nodes"]:
            node["status"] = "succeeded"
            node["summary"] = "done"
            node["analysis"] = "test"
            node["evidence"] = mixed_evidence
        analysis["findings"] = []
        analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
        result = self.run_script("validate_analysis.py", self.output / "facts.json", analysis_path)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        # 9 nodes × 2 evidence each = 18 total; 9 inference → ratio = 0.5
        self.assertAlmostEqual(out["inference_ratio"], 0.5, places=2)

    def test_code_block_skill_reference_not_detected(self) -> None:
        """@skill references inside fenced code blocks must not be treated as live skill refs."""
        (self.skill / "references" / "example.md").write_text(
            "Some text.\n"
            "```\n"
            "@some-skill-name --option\n"
            "```\n"
            "End of doc.\n",
            encoding="utf-8",
        )
        scan = self.run_script("scan_skill.py", self.skill, "--output-dir", self.output)
        self.assertEqual(scan.returncode, 0, scan.stderr)
        facts = json.loads((self.output / "facts.json").read_text(encoding="utf-8"))
        in_code = [
            s for s in facts["signals"]
            if s.get("kind") == "other-skill" and "some-skill-name" in s.get("value", "")
        ]
        self.assertEqual(in_code, [], f"Code-block skill ref leaked into signals: {in_code}")


if __name__ == "__main__":
    unittest.main()
