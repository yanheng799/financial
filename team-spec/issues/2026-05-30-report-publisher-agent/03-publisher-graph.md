## Parent

PRD：报告推送 Agent (`team-spec/prd/2026-05-30-report-publisher-agent.md`)

## What to build

实现 `build_publisher_graph()` —— 最简单节点 StateGraph，包含 `report_publisher_agent` 节点，可独立 invoke 验证端到端行为。

1. `StateGraph(AnalysisState)`，add_node `"report_publisher"`
2. set_entry_point + set_finish_point → compile
3. Mock 上游 state（含 `technical_report` + `decision_report`）→ invoke → 验证 Parquet 生成 + report_path 返回

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `build_publisher_graph()` 返回编译后的 StateGraph
- [ ] Given mock `technical_report` + `decision_report`，When `graph.invoke(state)`，Then 返回 state 含 `report_path`，`data/reports/` 下有 parquet 文件
- [ ] Given `decision_report` 为空，When `graph.invoke(state)`，Then 不报错（publisher 图本身无条件边，空报告由 app.py 处理）

## Blocked by

- #2（`02-publisher-agent-node` — report_publisher_agent 节点函数）

## Notes

- 不设条件边——`decision_report` 存在性由 `app.py` 在调用前检查
- 参考模式：`src/analyzer/node.py` 的 `build_analyzer_graph()`

## Publish Status

- Status: created
- GitHub Number: 46
- GitHub URL: https://github.com/yanheng799/financial/issues/46
