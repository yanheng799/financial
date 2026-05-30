## Parent

PRD：行情分析 Agent (`team-spec/prd/2026-05-30-market-analyzer-agent.md`)

## What to build

将三个评分函数集成为 LangGraph `market_analyzer` 节点，实现完整的 `raw_data → TechnicalReport` 端到端链路。

1. **节点函数**：在 `node.py` 中实现 `market_analyzer_agent(state: AnalysisState) -> dict`，从 `state["raw_data"]` 读取数据，调用三个指标计算函数和三个评分函数，组装 `TechnicalReport` 写入 `state["technical_report"]`
2. **StateGraph 构建**：实现 `build_analyzer_graph()` 函数，创建包含 `market_analyzer` 节点的 StateGraph，设置 entry/finish point
3. **indicators 组装**：将三个维度的计算指标合并到 `TechnicalReport.indicators` 字典中，确保包含 PRD 要求的全部 13 个键
4. **错误处理**：`raw_data` 为空或缺失关键字段时返回结构化错误

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given `raw_data` 包含完整三维数据，When 通过 StateGraph 执行 `market_analyzer` 节点，Then `state["technical_report"]` 包含 `scores`（三个 DimensionScore）和 `indicators`（13 个键）
- [ ] Given 通过 StateGraph 执行，When 检查 `technical_report.indicators`，Then 包含 ma5/ma20/ma60/macd_hist/macd_hist_prev/vol_ratio/pe_ttm/pe_percentile_1y/roe_yearly/tr_yoy/netprofit_yoy/net_mf_amount_5d/lg_buy_sell_ratio
- [ ] Given `raw_data` 为空 dict，When 执行节点，Then 返回结构化错误
- [ ] Given 资金面积分不足，When 执行节点，Then technical 和 fundamental 正常评分，capital 的 data_sufficient=False
- [ ] `build_analyzer_graph()` 返回编译后的 StateGraph，可直接 `invoke`
- [ ] PRD 验收标准 #1 通过（StateGraph 执行 + technical_report 包含三维评分）

## Blocked by

- #2（Technical indicators + score_technical）
- #3（Fundamental indicators + score_fundamental）
- #4（Capital indicators + score_capital）

## Notes

- 本 issue 的 StateGraph 只包含 `market_analyzer` 一个节点，不含后续的 `strategy_decider` 等节点
- 节点函数不需要重试机制（无外部 API 调用，纯内存计算）
- `technical_report` 写入 `AnalysisState` 后，后续策略决策 Agent 可直接从 state 读取
- 日线、PE 分位数等计算结果需通过 `indicators` 字段透传给下游 LLM，符合"不让 LLM 碰原始数据计算"的约束
