## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

将 `DecisionReport` 拆分为 `LLMOutput`（5 个 LLM 推理字段）和 `DecisionReport`（12 个最终字段），7 个确定性字段全部由代码注入。精简 LLM prompt 模板。

### 代码注入字段（7 个，LLM 不输出）
- `symbol`、`date` — 从 `technical_report` 原样取
- `scores` — 代码构建的 `ScoreEntry`
- `confidence_level` — 代码计算
- `conflict_detected` — 代码判断（既有正分又有负分）
- `data_sources` — 代码构建（`data_sufficient=True` 的维度来源）
- `generated_at` — `datetime.now().isoformat()`

### LLM 输出字段（5 个）
- `conflict_detail` — 冲突的自然语言描述
- `overall_judgment` — 综合判断枚举
- `key_driver` — 主驱动因素
- `risk_warning` — 风险提示
- `bearish_factor` — 强制反向因素

### 具体实现

1. **`LLMOutput` 模型**：Pydantic BaseModel，只含 5 个 LLM 推理字段
2. **`detect_conflict(scores)` 函数**：判断任意两维 value 是否既有正又有负（零值不算方向）
3. **`build_data_sources(scores, dim_sources)` 函数**：从 `dim_sources` 构建来源列表
4. **`build_prompt` 重构**：JSON 模板只要求 LLM 输出 5 个字段
5. **`strategy_decider_agent` 重构**：用 `LLMOutput` 校验 LLM 输出 → 合并代码注入字段 → `DecisionReport.model_validate()`
6. **`DecisionReport` 加 `model_config`**：`ConfigDict(extra="ignore")` 显式声明

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `LLMOutput` 模型只含 `conflict_detail`、`overall_judgment`、`key_driver`、`risk_warning`、`bearish_factor` 5 个字段
- [ ] `detect_conflict(scores)` 正确判断：有正有负 → True，全正/全负/含零 → False
- [ ] `build_data_sources(scores, dim_sources)` 只包含 `data_sufficient=True` 的维度来源
- [ ] `build_prompt` 的 JSON 模板只要求 LLM 输出 5 个字段
- [ ] `strategy_decider_agent` 用 `LLMOutput` 校验，合并注入后构建 `DecisionReport`
- [ ] `DecisionReport` 有 `model_config = ConfigDict(extra="ignore")`
- [ ] 端到端 invoke：mock LLM 返回 5 字段 JSON → `state["decision_report"]` 包含完整 12 字段
- [ ] 既有测试全部通过（或已更新）

## Blocked by

- #1（`AnalysisState` 加 `error` 字段，本 issue 不依赖，但建议先做）

## Notes

- prompt 的 JSON 模板中移除 `symbol`、`date`、`scores`、`confidence_level`、`conflict_detected`、`data_sources`、`generated_at` 这 7 个字段
- prompt 上下文信息（评分摘要、指标、symbol、date）仍然提供，只是不要求 LLM 回填
- 零值（value=0）不算方向，不参与冲突判断
- 重试机制不变：应用层 `attempt in range(2)` 校验 `LLMOutput`

## Publish Status

- Status: created
- GitHub Number: 36
- GitHub URL: https://github.com/yanheng799/financial/issues/36
