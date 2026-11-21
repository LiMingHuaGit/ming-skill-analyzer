# ming-skill-analyzer

> 分析任意 Agent Skill，生成带动态流程图的三栏交互式 HTML 报告。MIT 开源，Python 3.10+ 标准库，零外部依赖。

[English](README.md) · **中文**

---

## 是什么

**ming-skill-analyzer** 是一个面向 Agent Skill 作者和使用 Claude Code / Codex 的开发者的分析工具。它把对一个 Skill 的「理解」变成可交互、可探索、有证据溯源的 HTML 报告——而不是仅仅阅读 SKILL.md 文件。

**亮点**：工具本身也用自己分析了自己（自指分析），通过了 100% 证据覆盖率的严格验证，落地页上展示的流程图和能力说明都直接来自那份分析报告。

---

## 能做什么

分析过程分为五个独立步骤：

| 步骤 | 能力 | 说明 |
|------|------|------|
| 1 | **确定性只读扫描** | 读取 Skill 目录，脱敏，提取引用信号（带置信度 + 识别规则，过滤 CSS 和代码块误报） |
| 2 | **语义分析** | 以 `facts.json` 为唯一事实权威，输出能力族、输入类、节点图、边和设计结论 |
| 3 | **严格质量验证** | 检查证据摘录真实性，输出三项质量指标：`evidence_coverage` ≥ 90%、`inference_ratio`、`unsupported_claims` = 0 |
| 4 | **实时报告渲染** | 生成三栏 HTML（文件树 + 解析报告 + 动态 SVG 流程图），支持深浅色主题 |
| 5 | **本地安全服务** | 只绑定 `127.0.0.1`，提供文件 API 供浏览器按需读取当前 Skill 文件，拒绝路径越界 |

---

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/LiMingHuaGit/ming-skill-analyzer

# 2. 扫描（替换为你的 Skill 路径）
python3 scripts/scan_skill.py ./my-skill \
  --output-dir ./my-analysis \
  --prompt "分析触发边界"

# 3. 完成 analysis.json 后验证
python3 scripts/validate_analysis.py \
  my-analysis/facts.json my-analysis/analysis.json --strict

# 4. 渲染实时报告
python3 scripts/render_report.py \
  my-analysis/facts.json my-analysis/analysis.json \
  --output my-analysis/report.html --live

# 5. 本地浏览
python3 scripts/serve_report.py \
  --report my-analysis/report.html \
  --skill-root ./my-skill --open
```

**系统要求**：Python 3.10+，标准库，无需 pip install。支持 macOS / Linux / Windows。

---

## 报告长什么样

生成的 HTML 报告包含三个标签页：

- **文件树**：可展开折叠的 Skill 文件目录，点击任意文件实时预览内容，支持行级搜索
- **解析报告**：路由分数、场景分析、能力目录、输入路由矩阵、设计结论（强项 / 风险 / 边界）、证据索引
- **动态流程图**：SVG 有向图，支持泳道布局、播放动画、能力筛选、缩放全屏，左侧流程树显示所有执行路径

每条结论都追溯到 `facts.json` 的具体文件行号。

---

## 质量验证指标

运行 `validate_analysis.py --strict` 会输出三项可量化的质量门：

```json
{
  "evidence_coverage": 1.0,     // ≥ 0.9 才能通过
  "inference_ratio": 0.0,       // 越低越好
  "unsupported_claims": 0        // 必须为 0
}
```

---

## 目录结构

```
ming-skill-analyzer/
├── scripts/
│   ├── scan_skill.py          # 确定性扫描器
│   ├── validate_analysis.py   # 质量验证器（支持 --strict）
│   ├── render_report.py       # HTML 渲染器（支持 --live / --lang zh|en）
│   └── serve_report.py        # 本地只读服务器（127.0.0.1）
├── references/
│   ├── analysis-guidance.md   # 语义分析指南（含 v2 字段说明）
│   └── analysis-schema.md     # analysis.json Schema v2 文档
├── tests/
│   └── test_pipeline.py       # 9 个回归测试
└── docs/                      # 落地页（GitHub Pages / Cloudflare Worker）
```

---

## 安装为 Claude Code / Codex Skill

如果你使用 Claude Code 或 Codex，可以把本目录复制到 Skill 宿主目录，例如 `~/.codex/skills/ming-skill-analyzer/`，然后让 Agent 直接调用：

```
分析这个 Skill：~/my-project/skills/my-tool/
```

Agent 会自动遵循 SKILL.md 中的 11 步工作流，输出语言跟随你的输入语言（中文或英文）。

---

## 测试

```bash
python3 -m unittest discover -s tests -v
```

9 个测试覆盖：CSS 误报过滤、代码块误报过滤、邮件地址过滤、signal 字段完整性、质量指标输出、推断比例计算、全流程渲染等。

---

## 许可证

[MIT](LICENSE) · 由 [李明华（Minghua Li）](https://liminghua.fyi/) 开发
