## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

实现置信度计算函数和 `DimensionScore → ScoreEntry` 映射函数，均为纯代码。

1. **置信度计算**：在 `schemas.py` 中实现 `compute_confidence(scores: dict[str, DimensionScore]) -> str` 函数，按维度一致性规则决定置信度等级。`data_sufficient=False` 的维度不参与计算
2. **ScoreEntry 映射**：在 `schemas.py` 中实现 `to_score_entry(dim_score: DimensionScore) -> ScoreEntry` 函数，`data_sufficient=True → "determined"`，`False → "insufficient"`

### 置信度规则

| 有效维度数 | 置信度 | 条件 |
|---|---|---|
| 3 | 高 | 3 维方向一致（同正/同负/同零） |
| 3 | 中 | 2 维方向一致 |
| 3 | 低 | 3 维各不相同，或任意两维得分差 ≥ 2 |
| 2 | 高 | 2 维方向一致 |
| 2 | 低 | 2 维方向不一致 |
| 1 | 低 | 仅 1 维有效 |
| 0 | N/A | 抛 `ValueError`（不执行 LLM） |

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 技术面 +1、基本面 +1、资金面 -1（2 维方向一致），When 执行 `compute_confidence()`，Then 返回"中"
- [ ] Given 技术面 +1、基本面 +1、资金面 +1（3 维一致），When 执行 `compute_confidence()`，Then 返回"高"
- [ ] Given 技术面 +1、基本面 -1、资金面 0（3 维各不相同），When 执行 `compute_confidence()`，Then 返回"低"
- [ ] Given 技术面 data_sufficient=False，仅剩 2 维方向一致，When 执行 `compute_confidence()`，Then 返回"高"
- [ ] Given 仅 1 维有效，When 执行 `compute_confidence()`，Then 返回"低"
- [ ] Given 0 维有效，When 执行 `compute_confidence()`，Then 抛出 `ValueError`
- [ ] Given `DimensionScore(value=1, reason="...", data_sufficient=True)`，When 执行 `to_score_entry()`，Then 返回 `ScoreEntry(value=1, confidence="determined")`
- [ ] Given `DimensionScore(data_sufficient=False)`，When 执行 `to_score_entry()`，Then confidence="insufficient"

## Blocked by

- #1（Scaffolding, models, config）

## Notes

- 方向判断：`value > 0` = 正、`value < 0` = 负、`value == 0` = 零
- `data_sufficient=False` 的维度从 `scores` 中移除后再统计有效维度数和一致性
- `compute_confidence` 返回 Literal 字符串 "高"/"中"/"低"，兼容 `DecisionReport.confidence_level` 类型

## Publish Status

- Status: created
- Updated At: 2026-05-30T05:47:41Z
- GitHub Number: 21
- GitHub URL: https://github.com/yanheng799/financial/issues/21
