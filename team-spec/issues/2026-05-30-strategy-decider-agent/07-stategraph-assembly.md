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
