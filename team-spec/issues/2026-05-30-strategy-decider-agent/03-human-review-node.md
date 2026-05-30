## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

实现 `human_review_agent(state)` 节点函数，作为 Human-in-the-loop 审批节点。

1. **节点函数**：在 `node.py` 中实现 `human_review_agent(state: AnalysisState) -> dict`，从 `configs/llm.yaml` 读取 `auto_approve` 开关
2. **自动模式**：`auto_approve=True` 时直接返回 `{"human_approved": True}`，不中断
3. **中断模式**：`auto_approve=False` 时抛出 `NodeInterrupt({"message": "请确认 technical_report，批准后继续"})`，暂停执行等待 resume

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given `auto_approve=True`，When 执行 `human_review_agent(state)`，Then 返回 `{"human_approved": True}` 不中断
- [ ] Given `auto_approve=False`，When 执行 `human_review_agent(state)`，Then 抛出 `NodeInterrupt`
- [ ] `auto_approve` 值从 `configs/llm.yaml` 读取（mock 配置即可）

## Blocked by

- #1（Scaffolding, models, config）

## Notes

- 本节点不需要 checkpointer 持久化（Phase 2 实现），当前默认 `auto_approve=True`
- `NodeInterrupt` 是 LangGraph 内置异常，抛出后 graph 暂停，resume 时从该节点继续执行
- 不需要条件边——条件边由 issue #7 的 StateGraph 构建实现

## Publish Status

- Status: created
- Updated At: 2026-05-30T05:47:44Z
- GitHub Number: 22
- GitHub URL: https://github.com/yanheng799/financial/issues/22
