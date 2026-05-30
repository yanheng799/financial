## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

给 `AnalysisState` 加 `error: dict | None` 字段，让节点返回的结构化错误能被下游节点和 Streamlit 读取。同时修复 `human_approved=False` 走 END 路径时无提示的问题。

1. **`AnalysisState` 扩展**：加 `error: dict | None` 字段（`TypedDict` 用 `NotRequired` 或默认 `None`）
2. **`route_after_review` 补充**：`human_approved=False` 走 END 时，写 `{"error": {"error_type": "human_review", "message": "用户未批准，跳过策略分析"}}` 到 state

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `AnalysisState` 包含 `error` 字段
- [ ] 三个 Agent 的错误返回（`data_collector`、`market_analyzer`、`strategy_decider`）写入 `state["error"]`
- [ ] Given `human_approved=False`，When `route_after_review` 走 END，Then `state["error"]` 包含 "用户未批准" 提示
- [ ] 既有测试全部通过

## Blocked by

无

## Notes

- `TypedDict` 的可选字段用 `NotRequired[dict]`（Python 3.11+）或直接在运行时赋值
- 这是后续重构的基础——下游节点和 Streamlit 需要读 error 来判断失败原因

## Implementation Notes

- `src/state.py`: `AnalysisState` 加 `error: NotRequired[dict]` 字段
- `src/strategist/node.py`: `human_review_agent` 新增 `auto_approve=False` + `human_approved=False` 分支，返回拒绝 + error
- `tests/test_human_review.py`: 修复 `test_auto_approve_false_calls_interrupt`（state 不含 `human_approved`），新增 `test_auto_approve_false_rejection_returns_error`
- `tests/test_state_error_field.py`: 8 个新测试覆盖全部 AC

## Acceptance Criteria Coverage

- [x] `AnalysisState` 包含 `error` 字段 → `TestAnalysisStateErrorField::test_error_field_exists`
- [x] 三个 Agent 的错误返回写入 `state["error"]` → `TestAgentErrorsReachState` 三个测试
- [x] Given `human_approved=False`，When 走 END，Then `state["error"]` 包含"用户未批准" → `TestHumanReviewEndPathError::test_human_review_rejection_in_graph`
- [x] 既有测试全部通过 → 202 passed

## Verification

- `pytest` — 202 passed
- `ruff check` — All checks passed

## Publish Status

- Status: implemented
- GitHub Number: 35
- GitHub URL: https://github.com/yanheng799/financial/issues/35
