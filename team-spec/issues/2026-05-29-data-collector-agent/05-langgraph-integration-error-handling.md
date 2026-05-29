## Parent

PRD：数据采集 Agent (`team-spec/prd/2026-05-29-data-collector-agent.md`)

## What to build

将数据采集 Agent 集成为 LangGraph StateGraph 的 `data_collector` 节点，补全全部错误处理，并通过端到端验收。

1. **LangGraph 节点**：实现 `data_collector_agent(state: AnalysisState) -> dict` 函数，作为 StateGraph 节点。从 `state["symbol"]` 读取股票代码，调用 `fetch_all()` 获取数据，将 `RawData.model_dump()` 写入 `state["raw_data"]`
2. **StateGraph 构建**：创建最简 StateGraph，包含 `data_collector` 节点，验证节点输入输出与 `AnalysisState` 的兼容性
3. **Token 预检**：在 `TushareAdapter.__init__()` 中检查 `TUSHARE_TOKEN` 是否存在，缺失时立即报错（而不是等到 API 调用失败）
4. **重试机制**：对网络超时/HTTP 429 最多重试 2 次，间隔 3 秒；参数错误/权限不足不重试
5. **错误信息结构化**：所有错误返回结构化的错误字典（含 `error_type`、`message`、`detail`），便于下游处理和展示

完成后，数据采集 Agent 可作为 LangGraph 节点运行，满足 PRD 全部 8 条验收标准。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given `TUSHARE_TOKEN` 已配置，When 通过 LangGraph StateGraph 执行 `data_collector` 节点（输入 `{"symbol": "600519"}`），Then State 中 `raw_data` 包含 `daily`、`fundamental`、`capital` 三个子结构
- [ ] Given `TUSHARE_TOKEN` 未配置，When 执行 `data_collector` 节点，Then 返回结构化错误，含配置指引
- [ ] Given 输入 `{"symbol": "600519"}`（裸代码），When 节点执行，Then 自动补全为 `600519.SH` 后采集
- [ ] Given 输入不认识的代码，When Tushare 返回空结果，Then 返回"未找到该股票"错误
- [ ] Given Tushare API 超时后重试成功，When 节点执行，Then 正常返回数据（用户无感知）
- [ ] PRD 验收标准 #1-8 全部通过
- [ ] 自动化测试：mock Tushare API 超时场景，验证重试 2 次后报错

## Blocked by

- #4（Parquet 存储和缓存已完成）

## Notes

- 本 issue 的 StateGraph 只包含 `data_collector` 一个节点，不含后续的 `market_analyzer`、`strategy_decider` 等（它们在各自的 PRD 中实现）。
- Human-in-the-loop 节点（`human_review`）不属于数据采集 Agent 的范围，在后续 Agent 的 PRD 中实现。
- 手工验收：用 3 只熟悉股票（600519.SH、000001.SZ、920001.BJ）跑完整流程，抽查 20 个数据点与 Tushare 网页端交叉验证。
