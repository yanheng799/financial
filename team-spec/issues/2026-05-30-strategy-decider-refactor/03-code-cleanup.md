## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

三项代码清理，消除重复实现和硬编码：

1. **合并 `_extract_data_sufficient`**：`node.py:_extract_data_sufficient` 与 `schemas.py:_get_data_sufficient` 是同一逻辑两个实现，合并为只保留 `schemas.py` 的版本
2. **维度列表动态化**：`build_prompt` 中硬编码的 `["technical", "fundamental", "capital"]` 改为 `scores.keys()` 动态获取；`dim_sources` 映射外置到 `scoring_config.yaml` 或 `llm.yaml`
3. **重试分工注释**：在 `strategy_decider_agent` 中加注释说明 SDK 层重试（max_retries=2）与应用层重试（attempt range(2)）的分工

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `node.py` 中不再存在 `_extract_data_sufficient`，改为 import `schemas._get_data_sufficient`
- [ ] `build_prompt` 的维度遍历使用 `scores.keys()` 而非硬编码列表
- [ ] `dim_sources` 映射可从配置文件读取
- [ ] `strategy_decider_agent` 中有明确注释说明两层重试分工
- [ ] 既有测试全部通过

## Blocked by

无（可与 #2 并行，但建议 #2 之后做以避免冲突）

## Notes

- `key_indicators` 保持硬编码（精选列表，非全量指标）
- `dim_sources` 配置化后，Phase 2 加 `sentiment` 维度时只需改配置文件

## Implementation Notes

- `node.py`: 删除 `_extract_data_sufficient`，改为从 `schemas` import `_get_data_sufficient`（消除两个实现的分叉风险）
- `tests/test_code_cleanup.py`: 5 个测试验证清理结果

## Acceptance Criteria Coverage

- [x] `node.py` 中不再存在 `_extract_data_sufficient`，改为 import `schemas._get_data_sufficient` → `test_node_no_duplicate_extract_data_sufficient`
- [x] `build_prompt` 使用 `scores.keys()` 而非硬编码列表 → `test_node_build_prompt_uses_dynamic_dims`（已完成于 #36）
- [x] `dim_sources` 映射可从配置文件读取 → `test_dim_sources_externalized`（已完成于 #36）
- [x] `strategy_decider_agent` 中有注释说明两层重试分工 → `test_strategy_decider_has_retry_docs`（已完成于 #36）
- [x] 既有测试全部通过 → 229 passed

## Verification

- `pytest` — 229 passed
- `ruff check` — All checks passed

## Publish Status

- Status: implemented
- GitHub Number: 37
- GitHub URL: https://github.com/yanheng799/financial/issues/37
