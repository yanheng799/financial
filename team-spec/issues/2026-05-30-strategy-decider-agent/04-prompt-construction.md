## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

实现 LLM prompt 构造函数，从 `TechnicalReport` 生成带约束的完整 prompt 字符串。

1. **数据格式化**：将 `scores`（`DimensionScore` → `ScoreEntry`）和 `indicators` 格式化为 LLM prompt 摘要文本
2. **冲突计算**：计算最大分差（`max(scores) - min(scores)`）和 `conflict_detected` 判断
3. **prompt 模板**：组装完整 prompt，包含：
   - 三维评分摘要（每维 value/reason/data source）
   - 关键指标摘要（MA/MACD/vol_ratio/PE/ROE/YoY/资金流）
   - 最大分差
   - JSON 输出模板（全部字段，不含 `confidence_level`）
   - 约束规则（不编造、标注数据不足、强制 bearish_factor、仅输出 JSON）
4. **`data_sufficient=False` 处理**：该维度标注"该维度数据不足，仅供参考"

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given mock `TechnicalReport` 含完整三维评分，When 执行 `build_prompt()`，Then 返回字符串含三维评分摘要、全部 13 个 indicators、最大分差、JSON 模板
- [ ] Given prompt 输出，When 检查内容，Then 包含"不得输出 JSON 之外的文字"和"无论综合判断如何，必须输出 bearish_factor"
- [ ] Given prompt 输出，When 检查内容，Then 不包含 `confidence_level` 字段（由代码注入）
- [ ] Given 某维度 `data_sufficient=False`，When 执行 `build_prompt()`，Then prompt 包含"该维度数据不足"标注
- [ ] Given mock `TechnicalReport`，When `prompt` 以 UTF-8 编码，Then `len(prompt.encode("utf-8"))` 在合理范围内（< 3000 tokens）

## Blocked by

- #1（Scaffolding, models, config）

## Notes

- prompt 构造是纯字符串操作，无外部依赖，独立可测
- indicators 截断策略（如果超 token 上限）：保留全部 13 键名，数值截断为 `round(v, 2)`
- `data_sources` 字段从 `TechnicalReport.indicators` 键名推导（如 `ma5` → "Tushare daily"）

## Publish Status

- Status: created
- Updated At: 2026-05-30T05:47:46Z
- GitHub Number: 23
- GitHub URL: https://github.com/yanheng799/financial/issues/23
