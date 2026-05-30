## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

实现 `build_strategist_graph()` 函数，串联 `human_review` 和 `strategy_decider` 两个节点，构建完整的 StateGraph。

1. **StateGraph 构建**：创建 `StateGraph(AnalysisState)`，添加 `human_review` 和 `strategy_decider` 两个节点
2. **条件边**：`human_review` 后接条件边 `route_after_review(state) → "strategy_decider"` 或 `END`
3. **端到端 invoke**：验证 `{"symbol": "600519.SH", "technical_report": {...}}` 可完整跑通

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `build_strategist_graph()` 返回编译后的 StateGraph
- [ ] Given mock `technical_report` 和 mock LLM，When `graph.invoke(state)`，Then `state["decision_report"]` 包含完整 `DecisionReport`
- [ ] Given `human_approved=False`，When 条件边路由，Then 结果为 `END`
- [ ] Given `human_approved=True`，When 条件边路由，Then 结果为 `"strategy_decider"`
- [ ] PRD 验收标准 #1 通过（端到端 StateGraph 执行）

## Blocked by

- #3（human_review node）
- #6（strategy_decider node）

## Notes

- 条件边 `route_after_review` 逻辑：`return "strategy_decider" if state.get("human_approved") else END`
- 本 issue 的 StateGraph 只包含 `human_review` 和 `strategy_decider` 两个节点，不含上游 `data_collector`/`market_analyzer`（它们已有各自的 StateGraph）
- 后续四 Agent 全链路集成 PRD 会统一组装所有 StateGraph

## Publish Status

- Status: created
- Updated At: 2026-05-30T05:47:53Z
- GitHub Number: 26
- GitHub URL: https://github.com/yanheng799/financial/issues/26

## Implementation Notes

- 在 `src/strategist/node.py` 新增 `route_after_review(state)` 条件路由函数和 `build_strategist_graph()` StateGraph 构建函数
- 图结构：`human_review` → conditional_edges(`route_after_review`) → `strategy_decider` / `END`
- `route_after_review`: `human_approved=True` → `"strategy_decider"`，`False` → `"__end__"`
- 修复 `compute_confidence` / `to_score_entry` / `_get_data_sufficient` 对 dict 输入的兼容性（StateGraph 传递的是 plain dict 而非 DimensionScore 对象）
- 新增 `_get_value`、`_get_reason` 辅助函数，使 schemas.py 的函数同时兼容对象和 dict

## Acceptance Criteria Coverage

- [x] `build_strategist_graph()` 返回编译后的 StateGraph → `TestBuildStrategistGraph::test_returns_compiled_graph`
- [x] Given mock `technical_report` 和 mock LLM，When `graph.invoke(state)`，Then `state["decision_report"]` 包含完整 `DecisionReport` → `TestEndToEndInvoke::test_invoke_produces_decision_report`
- [x] Given `human_approved=False`，When 条件边路由，Then 结果为 `END` → `TestRouteAfterReviewReject::test_rejected_human_review_stops_at_end` + `test_no_llm_called_when_not_approved`
- [x] Given `human_approved=True`，When 条件边路由，Then 结果为 `"strategy_decider"` → `TestRouteAfterReviewApprove::test_approved_routes_to_strategy_decider` + `test_approved_runs_full_pipeline`
- [x] PRD 验收标准 #1 通过（端到端 StateGraph 执行）→ `TestEndToEndInvoke` 全部用例

## Verification

- `pytest` — 193 passed
- `ruff check src/strategist/ tests/test_strategist_graph.py` — All checks passed
