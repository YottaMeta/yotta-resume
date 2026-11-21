---
name: yotta-resume
description: "元简 — 本地求职者简历诊断、分析、修改与成品导出技能：分析简历结构、经历证据、量化指标、岗位匹配和风险，向用户追问缺失事实，给出逐条合理化修改建议，并把确认后的内容导出为 DOCX/PDF。触发：简历诊断、简历分析、改简历、简历追问、JD匹配、导出Word/PDF。边界：不编造经历，不承诺ATS、面试或Offer结果；不自动投递；不处理复杂设计作品集排版；默认本地处理且不联网。"
version: 0.1.2
license: MIT
metadata:
  zh_name: "元简"
---

# 元简（yotta-resume）

元简分析求职者简历的结构、经历证据和 JD 关键词覆盖，提出可回答的高价值问题，
并按用户确认的事实导出 DOCX、HTML 或 PDF。

## 触发与边界

- Triggers：用户要求诊断简历、改简历、补强经历证据、做 JD 匹配，或把已确认的简历导出为 Word/PDF。
- Do NOT trigger：用户要求代投简历、编造经历或数字、预测面试结果、评估受保护个人属性，或制作复杂设计作品集排版。

## 核心流程

1. 读取简历文件。支持 UTF-8 Markdown、UTF-8 文本、DOCX 和文字层 PDF。
   PDF 解析优先使用本地 PyMuPDF；缺少依赖、加密、损坏或扫描件时明确失败或降级，
   不生成伪完整报告。
2. 运行分析，优先让用户提供目标岗位 JD：

```bash
python scripts/yotta_resume.py audit --resume resume.md --jd jd.txt --format json
```

3. 阅读 `source_manifest`、`parse_warnings`、`issues`、`unknowns` 和 `questions`。
   先确认输入解析质量、规模、个人边界、结果、日期和 JD 缺口，再修改简历。
   用户没有确认的事实不要写进简历。
4. 按用户确认的信息修改 Markdown，再导出成品：

```bash
python scripts/yotta_resume.py export --input revised.md --docx revised.docx --html revised.html --pdf revised.pdf
```

5. 核对输出文件存在且可打开。PDF 依赖本机 Chromium、Chrome 或 Edge；未找到浏览器时命令会明确失败，不会生成伪 PDF。

6. 需要校验随包岗位族、证据账本、题库、来源和双角色权限契约时运行：

```bash
python scripts/yotta_resume.py contracts --format json
```

## 输出契约

- `audit`：JSON 或 Markdown，包含文件来源清单、解析提示、章节识别、要点统计、
  工具发现、未知项、追问、修改建议、JD 匹配、结构准备度和边界声明。
- `export`：DOCX / HTML / PDF。三者来自同一份 Markdown 内容模型，联系方式保留在成品简历中。
- `contracts`：离线校验 `data/` 下的 5 个实际契约与 5 个 JSON Schema，
  失败返回退出码 `6`，不写文件、不联网。
- 分析报告：手机号和邮箱会被打码；不承诺 ATS、面试或 Offer 结果。

## 评分与数字护栏

- `readiness.score` 的展示名称固定为“结构准备度（规则分）”，
  `score_type` 为 `structure_rule_score`，只反映章节、量化证据、文本清洁度和
  可选 JD 关键词覆盖，不是招聘方评分。
- 只能原样引用工具返回的数值；**不得改写为其他数值、主观数字区间或“实际分数”**。
  需要对招聘方视角作判断时，只允许定性标签并列出简历证据。
- 未提供 JD 时 `jd_match.coverage` 必须为 `null`，报告写明不能判断岗位匹配。
- 报告必须区分“工具规则发现”“智能体复核发现”“待用户确认事实”。
  智能体额外发现不得冒充工具输出，且必须引用简历原文或来源页。
- 规则不能判断招聘竞争力、面试通过率或 Offer 结果；必须列入 `unknowns`。

## 渐进披露

- 详细输入格式、CLI 退出码和浏览器要求见 [references/usage.md](references/usage.md)。
- 岗位族、题库、来源与 HR 权限契约见 [references/data-contracts.md](references/data-contracts.md)。

## 自检

```bash
python scripts/test_yotta_resume.py
python scripts/test_contract_validate.py
```
