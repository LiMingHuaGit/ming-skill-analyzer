#!/usr/bin/env python3
"""Read-only Agent Skill scanner that emits facts and an analysis template."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FACTS_SCHEMA_VERSION = 1   # facts.json output format version
ANALYSIS_SCHEMA_VERSION = 2  # analysis.json format version (required by render_report.py)
MAX_FILE_BYTES = 250_000
MAX_TOTAL_TEXT = 2_000_000
SKIP_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
SENSITIVE_NAMES = {
    ".env", "credentials.json", "secrets.json", "id_rsa", "id_ed25519",
    "service-account.json", "service_account.json", "auth.json",
}
TEXT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".jsx", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".sh",
    ".bash", ".zsh", ".fish", ".swift", ".java", ".kt", ".go", ".rs", ".rb",
    ".php", ".html", ".css", ".scss", ".sql", ".xml", ".csv", ".svg",
}
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\b\s*[:=]\s*['\"]?([^\s'\"]{8,})"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{16,})\b"),
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"),
]
COMMON_CLIS = {
    "python", "python3", "node", "npm", "pnpm", "npx", "git", "curl", "wget",
    "bash", "zsh", "sh", "swift", "xcodebuild", "java", "mvn", "gradle", "docker",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path, help="Target Skill directory")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--prompt", default="", help="User request to simulate")
    return parser.parse_args()


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    result: dict[str, str] = {}
    index = 1
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            break
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            key, value = match.groups()
            value = value.strip()
            if value in {"|", ">"}:
                block: list[str] = []
                index += 1
                while index < len(lines) and (lines[index].startswith(" ") or not lines[index].strip()):
                    block.append(lines[index].strip())
                    index += 1
                result[key] = " ".join(part for part in block if part).strip()
                continue
            result[key] = value.strip("\"'")
        index += 1
    return result


def redact(text: str) -> tuple[str, int]:
    redactions = 0
    for pattern in SECRET_PATTERNS:
        def replacement(match: re.Match[str]) -> str:
            if match.lastindex and match.lastindex >= 2:
                return f"{match.group(1)}: [REDACTED]"
            return "[REDACTED]"
        text, count = pattern.subn(replacement, text)
        redactions += count
    return text, redactions


def is_sensitive(path: Path) -> bool:
    name = path.name.lower()
    return name in SENSITIVE_NAMES or name.endswith((".pem", ".key", ".p12", ".pfx"))


def decode_text(data: bytes, path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_EXTENSIONS and path.name.lower() != "skill.md":
        return None
    for encoding in ("utf-8", "utf-8-sig", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def classify(relative: str, path: Path) -> str:
    if path.name.lower() == "skill.md":
        return "skill-manifest"
    first = relative.lower().split("/", 1)[0]
    if first in {"scripts", "references", "assets", "templates", "examples", "tests", "evals"}:
        return first
    if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".mp3", ".wav", ".pdf"}:
        return "media"
    return "file"


def _in_code_block(lines: list[str], line_index: int) -> bool:
    """Return True if the line is inside a fenced code block."""
    fence_count = 0
    for i, line in enumerate(lines):
        if i >= line_index:
            break
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence_count += 1
    return fence_count % 2 == 1


def extract_signals(relative: str, text: str) -> list[dict]:
    signals: list[dict] = []
    seen: set[tuple[str, str, int]] = set()
    is_css = relative.endswith((".css", ".scss", ".sass"))
    lines = text.splitlines()

    # CSS at-rules to ignore (not skill references)
    CSS_AT_RULES = re.compile(r"@(media|keyframes|font-face|import|charset|supports|layer|property|namespace)\b", re.I)

    patterns = [
        ("file-reference", re.compile(r"(?<![A-Za-z0-9_-])((?:scripts|references|assets|templates|examples)/[^\s)`'\"<>]+)")),
        ("markdown-link", re.compile(r"\[[^\]]+\]\(([^)#][^)]+)\)")),
        ("mcp", re.compile(r"\b(mcp__[A-Za-z0-9_.-]+|MCP\s+(?:server|tool|resource))\b", re.I)),
        ("other-skill", re.compile(r"(?<!\w)([$@][A-Za-z0-9][A-Za-z0-9_-]{2,})")),
        ("api", re.compile(r"https?://[^\s)`'\"<>]+")),
        ("cli", re.compile(r"`(?:/[^`\s]+/)?([A-Za-z0-9_.-]+)(?:\s+[^`]*)?`")),
    ]
    for line_number, line in enumerate(lines, start=1):
        in_code = _in_code_block(lines, line_number - 1)
        for kind, pattern in patterns:
            for match in pattern.finditer(line):
                value = match.group(1) if match.lastindex else match.group(0)
                if kind == "cli" and value not in COMMON_CLIS:
                    continue
                # Skip CSS at-rules and email addresses for other-skill
                if kind == "other-skill":
                    if is_css or in_code:
                        continue
                    if CSS_AT_RULES.match(value.lstrip("$@")):
                        continue
                    # Skip email-like patterns (contains @domain.tld)
                    if re.match(r"@[A-Za-z0-9_-]+\.[A-Za-z]{2,}", value):
                        continue
                    detection_rule = "markdown-skill-link" if value.startswith("$") else "at-mention"
                    confidence = "high" if value.startswith("$") else "medium"
                else:
                    detection_rule = kind
                    confidence = "high"
                value = value.rstrip(".,:;")
                key = (kind, value, line_number)
                if key in seen:
                    continue
                seen.add(key)
                signal: dict = {
                    "kind": kind,
                    "value": value,
                    "file": relative,
                    "line": line_number,
                    "excerpt": line.strip()[:240],
                    "confidence": confidence,
                    "detection_rule": detection_rule,
                }
                signals.append(signal)
    return signals


def build_template(name: str, description: str, prompt: str) -> dict:
    titles = [
        ("discover", "discovery", "Discover Skill"),
        ("request", "context", "Current Request"),
        ("match", "routing", "Match Skill"),
        ("load", "instructions", "Load SKILL.md"),
        ("resources", "resources", "Select Resources"),
        ("plan", "planning", "Plan Next Action"),
        ("tools", "tools", "Simulate Tools"),
        ("verify", "verification", "Verify Result"),
        ("reply", "feedback", "Reply & Feedback"),
    ]
    nodes = []
    for index, (node_id, node_type, title) in enumerate(titles):
        nodes.append({
            "id": node_id,
            "type": node_type,
            "title": title,
            "status": "pending",
            "summary": "",
            "analysis": "",
            "inputs": [],
            "outputs": [],
            "resources": [],
            "next": [titles[index + 1][0]] if index + 1 < len(titles) else [],
            "evidence": [],
        })
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "scenario": {"prompt": prompt, "invocation_mode": "unknown", "context_summary": ""},
        "overview": {
            "summary": f"Analysis of {name or 'the target Skill'}.",
            "routing_score": 0,
            "routing_label": "unknown",
            "strengths": [],
            "risks": [],
        },
        "nodes": nodes,
        "findings": [],
        "target_metadata": {"name": name, "description": description},
    }


def main() -> int:
    args = parse_args()
    target = args.target.expanduser().resolve()
    skill_md = target / "SKILL.md"
    if not target.is_dir() or not skill_md.is_file():
        print("error: target must be a directory containing SKILL.md", file=sys.stderr)
        return 2
    output = args.output_dir.expanduser().resolve()
    if output == target or output.is_relative_to(target):
        print("error: output directory must be outside the target Skill", file=sys.stderr)
        return 3
    output.mkdir(parents=True, exist_ok=True)
    facts_path = output / "facts.json"
    template_path = output / "analysis-template.json"
    if facts_path.exists() or template_path.exists():
        print("error: output already contains analyzer files; choose a new directory", file=sys.stderr)
        return 4

    files: list[dict] = []
    signals: list[dict] = []
    warnings: list[str] = []
    total_text = 0
    for path in sorted(target.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(target).parts):
            continue
        relative = path.relative_to(target).as_posix()
        size = path.stat().st_size
        record = {
            "path": relative, "category": classify(relative, path), "size": size, "sha256": "",
            "text": None, "line_count": None, "truncated": False, "sensitive": False,
            "redactions": 0, "skip_reason": None,
        }
        if is_sensitive(path):
            record["sensitive"] = True
            record["skip_reason"] = "credential-like file"
            warnings.append(f"Skipped sensitive file: {relative}")
            files.append(record)
            continue
        if size > MAX_FILE_BYTES:
            record["skip_reason"] = f"file exceeds {MAX_FILE_BYTES} bytes"
            warnings.append(f"Skipped oversized file: {relative}")
            files.append(record)
            continue
        data = path.read_bytes()
        record["sha256"] = hashlib.sha256(data).hexdigest()
        decoded = decode_text(data, path)
        if decoded is None:
            record["skip_reason"] = "binary or unsupported text format"
            files.append(record)
            continue
        remaining = MAX_TOTAL_TEXT - total_text
        if remaining <= 0:
            record["skip_reason"] = "total embedded text limit reached"
            warnings.append(f"Text omitted after total limit: {relative}")
            files.append(record)
            continue
        if len(decoded) > remaining:
            decoded = decoded[:remaining]
            record["truncated"] = True
            warnings.append(f"Truncated text at total limit: {relative}")
        decoded, redaction_count = redact(decoded)
        record["text"] = decoded
        record["line_count"] = len(decoded.splitlines())
        record["redactions"] = redaction_count
        total_text += len(decoded)
        signals.extend(extract_signals(relative, decoded))
        files.append(record)

    skill_text = next((item["text"] for item in files if item["path"] == "SKILL.md"), None)
    if not skill_text:
        print("error: SKILL.md could not be read safely", file=sys.stderr)
        return 5
    metadata = parse_frontmatter(skill_text)
    facts = {
        "schema_version": FACTS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": {
            "name": metadata.get("name", target.name),
            "description": metadata.get("description", ""),
            "skill_md": "SKILL.md",
            "file_count": len(files),
            "embedded_text_chars": total_text,
        },
        "frontmatter": metadata,
        "files": files,
        "signals": signals,
        "warnings": warnings,
        "limits": {"max_file_bytes": MAX_FILE_BYTES, "max_total_text_chars": MAX_TOTAL_TEXT},
    }
    template = build_template(facts["target"]["name"], facts["target"]["description"], args.prompt)
    facts_path.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")
    template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": "ok", "facts": str(facts_path), "analysis_template": str(template_path),
        "files": len(files), "signals": len(signals), "warnings": len(warnings),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
