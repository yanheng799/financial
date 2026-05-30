# 规格评审：报告推送 Agent

**评审对象**：`team-spec/spec/refine/2026-05-30-report-publisher-agent.md`
**评审日期**：2026-05-30
**Status**：ready

## 结论

细化规格范围清晰、边界明确、术语一致，可以进入 PRD 固化。无 P0 阻塞项。两个 P1 风险（`raw_data_paths` 数据源缺失、全链路图不存在）应在 PRD 中明确定义处理方式或在 Phase 1 中降级。

## 阻塞项

无。

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P1 | `raw_data_paths` 的数据来源不存在 | 数据采集 Agent 未将 Parquet 路径写入 state | `report_publisher_agent` 无法填充 `AnalysisReport.raw_data_paths` | `AnalysisState` 只有 `raw_data: dict`（数据内容），没有 `raw_data_paths`。数据采集的路径由 `_get_data_dir()` 内部管理，不对外暴露 | 方案 A：存储时写路径到 `state`（需改 `collector/node.py`）；方案 B：`report_publisher` 用 symbol/date 反推路径（已知目录结构）；方案 C：Phase 1 降级——`raw_data_paths` 标记为空，Streamlit 渲染时省略"原始数据"按钮 | yanhe | PRD 固化时 |
| P1 | 四 Agent 全链路拼接图尚未建设 | `app.py` 需要 `invoke` 全链路但不存在 | Streamlit 无法驱动完整流水线 | 三个 Agent 各有独立的 `build_graph()`（`collector`/`analyzer`/`strategist`），无 `build_full_pipeline()` 一次性 invoke 四个节点 | 方案 A：新建 `build_full_pipeline()` 在最外层串联四个 StateGraph；方案 B：`app.py` 逐图 invoke 并手动传递 state；方案 C：Phase 1 不合并，用 Python 脚本逐级调用 | yanhe | PRD 固化时 |
| P2 | `{symbol}_{datetime}.parquet` 的 `datetime` 格式未指定 | 文件名生成不一致 | Streamlit glob 匹配困难 | 细化文档只说"时间戳"，未指定格式 | 统一使用 `{symbol}_{YYYYMMDDTHHMMSS}.parquet`（ISO 加时分秒），如 `600519.SH_20260530T163000.parquet` | yanhe | 实现时 |
| P2 | `report_publisher_agent` 返回的 `report_path` 字段不在 `AnalysisState` 中 | 节点返回 `{"report_path": "..."}` | LangGraph 静默丢弃该字段 | `AnalysisState` 无 `report_path` 键 | 加 `report_path: str` 到 `AnalysisState`，或把路径只存在 error 时返回 | yanhe | 实现时 |
| P2 | `route_after_decision` 模块归属未定 | strategist 还是 publisher | 循环依赖或职责不清 | 条件边需要检查 `decision_report` 是否存在，判断逻辑已在 strategist 的 `route_after_review` 类似 | 放入 `src/publisher/node.py`，与 `report_publisher_agent` 同一个图；strategist 的图不做条件边，由 publisher 的图处理 | yanhe | 实现时 |
| P3 | `indicators: dict[str, float | None]` 类型不精确 | 13 个指标各有不同语义 | 运行时不会报错，但 IDE 提示不友好 | 当前 dict 足够灵活 | 保持 dict，Phase 2 考虑 `TypedDict` 精确化 | — | — |
| P3 | Streamlit 首次运行需要 `streamlit` package | `pip install streamlit` 未在 pyproject.toml | dev 依赖缺失导致无法启动 | pyproject.toml 现有依赖不包括 streamlit | PRD 中列入安装步骤 | yanhe | 实现时 |

## Questions For User

无。

## Required Refinement

无。所有 P1 都有明确方案选项，可在 PRD 固化时选择，不需要回到 refine。

## 建议改写

### 1. `AnalysisReport.raw_data_paths` 方案（P1）

推荐**方案 B（反推路径）**：数据采集的存储路径是确定的模式 `data/{symbol}/{interface}.parquet`。`report_publisher_agent` 可以根据 `symbol` + 已知目录结构构造路径引用，不需要改收集器。

PRD 应明确：`raw_data_paths` 通过路径反推构建，`symbol` / `date` / 各接口名组合成路径。如果文件不存在，值为 `None`（不阻塞报告生成）。

### 2. 四 Agent 全链路拼接（P1）

推荐**方案 B（逐图 invoke）**：`app.py` 按顺序调用三个 `build_graph().invoke(state)`，state 在调用间自然传递。不需要一个新的全链路图——LangGraph 已经是 StateGraph，只要 state schema 一致，图的边界不限制分步执行。

```python
# app.py 中
state = collector.build_graph().invoke({"symbol": symbol})
state = analyzer.build_analyzer_graph().invoke(state)
state = strategist.build_strategist_graph().invoke(state)
state = publisher.build_publisher_graph().invoke(state)
```

PRD 应明确：Phase 1 用逐图 invoke 串联，不建 `build_full_pipeline()`。Phase 2 考虑统一图 + checkpointer 持久化。

### 3. `report_publisher_agent` 节点的路由归属

推荐 `route_after_decision` 放在 `src/publisher/node.py`，与 `report_publisher_agent` 同一个文件。`build_publisher_graph()` 从 `strategy_decider` 之后开始（不从 `human_review` 开始）。但这也意味着 publisher 图需要知道 `strategy_decider` 节点名——这不现实。

**实际推荐**：扩建 `build_strategist_graph()`，加 `report_publisher` 节点和 `route_after_decision` 边。这样 strategist 图变为 `human_review → strategy_decider → route_after_decision → report_publisher → END`。节点实现放在 `src/publisher/node.py`，但图组装在 `src/strategist/node.py` 中扩展。

或者用方案 B（逐图 invoke）则不需要在图层面耦合——`app.py` 在 `strategist` 图 invoke 后检查 `decision_report` 是否存在，再决定是否调用 `publisher` 图。这是最干净的方案。

## Change Log

- 2026-05-30：初始评审。发现两个 P1（`raw_data_paths` 数据源缺失、全链路拼接未建设）和若干 P2。Status: ready（P1 有明确方案，可在 PRD 固化时选择，无需回到 refine）。
