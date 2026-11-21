# 数据契约

元简从 `0.1.2` 起随包提供 5 个机器可读契约及其 JSON Schema：

- `data/security-role-map.json`：6 个安全岗位族与 4 个职级。
- `data/evidence-ledger.json`：简历证据账本，记录责任、动作、规模、结果和边界。
- `data/source-registry.json`：来源层级、日期、刷新周期、失效周期和许可复核状态。
- `data/question-bank.json`：题库清单；`0.1.2` 为空题库，题目由后续批次按契约写入。
- `data/dual-role-contract.json`：求职者和 HR 的数据访问、导出及受保护属性边界。

## 校验

离线校验随包契约：

```bash
python scripts/yotta_resume.py contracts --format json
```

直接运行独立校验器：

```bash
python scripts/contract_validate.py --root data --format json
```

成功返回退出码 `0`；主 CLI 的契约校验失败返回 `6`。独立校验器失败返回非零退出码。

## 安全边界

- 默认策略为 `deny`。
- HR 默认不能读取候选人私有证据账本、原始简历或分析报告。
- 跨角色导出必须提供字段清单并确认，默认只导出投递版简历。
- 年龄、性别、婚育、民族、宗教、籍贯、残障和照片等受保护属性不得进入评分字段。
- 来源许可未确认时只允许事实提炼、链接引用和自主改写，不复制长段原文。
- 社区面经只可作练习提示，不能作为标准答案。
