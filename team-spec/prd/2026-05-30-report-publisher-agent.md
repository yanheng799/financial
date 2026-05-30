# PRD：报告推送 Agent

## 问题陈述

四 Agent 流水线的前三个 Agent（数据采集、行情分析、策略决策）已全部实现，能产出 `raw_data`、`technical_report`、`decision_report`。但这些数据分散在三个 dict 中，没有统一的报告格式，也没有可供用户查看的界面。用户需要一个端到端的输入-分析-展示闭环：输入股票代码 → 看到可读的分析报告。

## 目标

- 实现 `report_publisher_agent` 节点：组装 `AnalysisReport` + Parquet 归档
- 实现 Streamlit `app.py`：输入股票代码 → 驱动全链路 → 展示报告 + 历史回溯
- 完成四 Agent 全链路端到端闭环

## 非目标

- Jinja/HTML 模板渲染
- 图表、趋势线、K 线图
- 多票对比、板块分析
- 报告导出（PDF/图片）、推送通知
- 自定义页面布局

## 用户与场景

1. 作为个人投资者，我希望在浏览器中输入股票代码后点击"分析"，系统自动完成数据采集→行情分析→策略决策→报告展示的全流程，以便我无需分步操作。
2. 作为个人投资者，我希望看到统一格式的分析报告（三维评分表 + 关键指标 + LLM 研判），以便快速理解该股票的当前状态和风险。
3. 作为个人投资者，我希望查看该股票的历史分析记录，以便追踪评分和研判的变化趋势。
4. 作为个人投资者，当上游出错（如 API 不可用、数据不足、用户拒绝审批）时，我希望看到明确的错误提示，而不是空白页面。

## 当前状态

- 数据采集 Agent 已实现（`src/collector/`），`build_graph()` 可独立 invoke
- 行情分析 Agent 已实现（`src/analyzer/`），`build_analyzer_graph()` 可独立 invoke
- 策略决策 Agent 已实现（`src/strategist/`），`build_strategist_graph()` 可独立 invoke
- `AnalysisState` 包含 `symbol`, `raw_data`, `technical_report`, `decision_report`, `human_approved`, `error`
- 三个 Agent 各有独立 StateGraph，无统一全链路图
- Streamlit 未安装，`app.py` 未创建
- `src/publisher/` 目录未创建

## 方案描述

### 全链路执行：逐图 invoke

`app.py` 按顺序调用三个 Agent 的 StateGraph，state 在各调用间自然传递。不需要新建 `build_full_pipeline()` 统一图：

```
app.py 输入 symbol
  → collector.build_graph().invoke({"symbol": symbol})
  → analyzer.build_analyzer_graph().invoke(state)
  → strategist.build_strategist_graph().invoke(state)
  → 检查 state["decision_report"] 是否存在
     ├── 存在 → publisher.build_publisher_graph().invoke(state)
     └── 不存在 → 跳过（error 已在 state 中）
  → 从 Parquet 读 AnalysisReport → Streamlit 渲染
```

### report_publisher_agent 节点

最简单节点图（`build_publisher_graph()`），不设条件边。

1. 读取 `symbol`、`technical_report`、`decision_report`
2. 组装 `AnalysisReport`：上游数据汇总 + `raw_data_paths`（反推路径构建）
3. `mkdir -p data/reports/`
4. 写入 `data/reports/{symbol}_{YYYYMMDDTHHMMSS}.parquet`
5. 返回 `{"report_path": "..."}`
6. 失败 → `{"error": {"error_type": "storage", "message": "..."}}`

### app.py（Streamlit）

独立入口：

1. 输入框 → 输入股票代码
2. 点击"分析" → `st.spinner` 显示进度 → 逐图 invoke 四个 Agent
3. 完成后从 Parquet 读 `AnalysisReport`
4. 三块展示：① 三维评分表（value/reason/置信度标记）② 关键指标数值表 ③ LLM 研判（综合判断 + 风险 + 反向因素）
5. 历史下拉：遍历 `data/reports/{symbol}_*.parquet`，按时间排序
6. 错误处理：`state["error"]` 不为空时展示错误信息

## 范围

### 范围内

- `report_publisher_agent(state)` 节点函数（`src/publisher/node.py`）
- `AnalysisReport` Pydantic 模型（`src/publisher/schemas.py`）
- `build_publisher_graph()` 最简单节点 StateGraph
- Parquet 存储：`data/reports/{symbol}_{YYYYMMDDTHHMMSS}.parquet`
- `raw_data_paths`：通过已知目录结构反推（不内嵌原始数据）
- `app.py`：逐图 invoke → 读取报告 → 三块展示 + 历史下拉
- 落盘失败 → `error_type: "storage"`
- Streamlit spinner 显示执行进度

### 范围外

- HTML/CSS 模板
- 图表/K 线/趋势线
- 多票对比、板块分析
- 报告导出（PDF/图片）、推送通知
- `build_full_pipeline()` 统一图（Phase 2）
- 全链路 checkpointer 持久化（Phase 2）

## 功能需求

### FR-1：report_publisher_agent 节点

1. 系统必须实现 `report_publisher_agent(state: AnalysisState) -> dict` 节点函数
2. 从 `state["technical_report"]` 和 `state["decision_report"]` 组装 `AnalysisReport`
3. 通过已知目录结构反推 `raw_data_paths`（不依赖 state 中存储路径）
4. 写入 `data/reports/{symbol}_{YYYYMMDDTHHMMSS}.parquet`

### FR-2：AnalysisReport 模型

5. 必须定义 `AnalysisReport` Pydantic 模型（`src/publisher/schemas.py`）
6. 复用 `src.strategist.schemas.ScoreEntry`，不重复定义
7. `raw_data_paths: dict[str, str | None]`——路径可不存在时值为 None

### FR-3：build_publisher_graph

8. 系统必须实现 `build_publisher_graph()`——最简单节点 StateGraph
9. 不设条件边，不设 route_after_decision

### FR-4：app.py Streamlit

10. 系统必须提供 `app.py`——Streamlit 入口
11. 输入框接收股票代码，按钮触发分析
12. `st.spinner` 显示执行进度
13. 按序逐图 invoke：collector → analyzer → strategist → publisher
14. 检查 `state["decision_report"]` 存在后才 invoke publisher
15. 三块结果展示：三维评分表、指标数值表、LLM 研判
16. 历史下拉：遍历 `data/reports/{symbol}_*.parquet`

### FR-5：错误处理

17. 目录不存在时 `mkdir -p data/reports/` 幂等创建
18. Parquet 写入失败 → `error_type: "storage"`
19. 上游已有 `error` 时 → Streamlit 展示错误信息，不调用 publisher
20. Parquet 文件不存在时 → Streamlit 展示"暂无分析报告"

## 业务规则

- **报告不可变**：`{symbol}_{datetime}.parquet` 文件名含完整时间戳，写后不修改
- **路径反推**：`raw_data_paths` 通过 symbol + 已知接口名 + 目录结构构造，文件不存在时值为 `None`
- **降级不阻塞**：Parquet 写入失败不阻塞上游流水线（state 中已有全部数据）
- **Streamlit 独立**：app.py 不在 LangGraph 图中，可独立重启

## 边界情况与错误状态

| 场景 | 预期行为 |
|---|---|
| 目录不存在 | `mkdir -p data/reports/` 创建 |
| Parquet 写入失败（磁盘满/权限） | `error_type: "storage"` 写入 `state["error"]` |
| `decision_report` 不存在 | app.py 跳过 publisher 调用，展示 error |
| 同一股票同一天多次分析 | 文件名不同（时间戳差异），各版本独立保留 |
| 历史 Parquet 文件被手动删除 | Streamlit 从 glob 结果中自然消失 |
| `raw_data_paths` 指向的文件不存在 | 报告中标记为 `None` |
| Streamlit 首次启动但无历史报告 | 展示"暂无分析报告，请输入股票代码开始" |
| Streamlit 崩溃 | 报告已落盘，重启后可查看历史 |

## 数据与状态

### Pydantic 模型

```python
# src/publisher/schemas.py
from pydantic import BaseModel
from src.strategist.schemas import ScoreEntry

class AnalysisReport(BaseModel):
    symbol: str
    date: str
    generated_at: str
    scores: dict[str, ScoreEntry]
    indicators: dict[str, float | None]
    overall_judgment: str
    confidence_level: str
    conflict_detected: bool
    conflict_detail: str
    key_driver: str
    risk_warning: str
    bearish_factor: str
    data_sources: list[str]
    raw_data_paths: dict[str, str | None]
```

### 文件命名

`data/reports/{symbol}_{datetime}.parquet`，其中 `datetime` 格式为 `YYYYMMDDTHHMMSS`。示例：`600519.SH_20260530T163000.parquet`。

### raw_data_paths 反推

```python
def _build_raw_data_paths(symbol: str) -> dict[str, str | None]:
    """通过已知目录结构反推原始数据路径"""
    base = Path(f"data/{symbol}")
    files = {
        "daily": base / "daily.parquet",
        "daily_basic": base / "daily_basic.parquet",
        "fina_indicator": base / "fina_indicator.parquet",
        "income": base / "income.parquet",
        "moneyflow": base / "moneyflow.parquet",
    }
    return {k: str(v) if v.exists() else None for k, v in files.items()}
```

## 实现决策

- **全链路拼接**：`app.py` 逐图 invoke，不建统一图。State 在各图间自然传递
- **路由简化**：publisher 是最简单节点图，无条件边。`decision_report` 存在性由 `app.py` 检查
- **路径反推**：`raw_data_paths` 不依赖 state 中的路径（state 只存数据不存路径），通过已知目录结构反推
- **Parquet 落盘时机**：在 report_publisher 节点内写，不在 app.py 中写（保持图的完整性）
- **代码位置**：`src/publisher/schemas.py`（模型）+ `src/publisher/node.py`（节点 + 图构建）
- **Streamlit 安装**：`pip install streamlit`，加入 `pyproject.toml` dev 依赖

## 测试决策

### 自动化测试

- `AnalysisReport` 模型校验：合法/非法构造
- `report_publisher_agent`：mock state → 验证 `AnalysisReport` 内容 + Parquet 文件存在
- `build_publisher_graph`：verify 编译后的图可 invoke
- `_build_raw_data_paths`：文件存在 → 路径字符串；文件不存在 → None
- Parquet 落盘失败：mock `pd.DataFrame.to_parquet` 抛异常 → `error_type: "storage"`

### 手工验收

- `streamlit run app.py` → 输入 `600519` → 点击分析 → 三块结果展示
- 历史下拉列出之前的分析（多次分析同一股票后验证）
- 输入无效代码 → 错误提示（非白页）

## 验收标准

1. **Given** `technical_report` + `decision_report` 完整，**When** `report_publisher_agent(state)`，**Then** `data/reports/{symbol}_{datetime}.parquet` 存在，内容含 `AnalysisReport` 全部字段
2. **Given** Parquet 写入失败，**When** `report_publisher_agent(state)`，**Then** 返回 `error_type: "storage"`
3. **Given** Stocklit 输入 `600519`，**When** 点击"分析"，**Then** 页面展示三维评分 + 指标 + LLM 研判
4. **Given** `decision_report` 不存在，**When** `app.py` 检查，**Then** 跳过 publisher，展示 error
5. **Given** 同一股票分析了 3 次，**When** 打开历史下拉，**Then** 显示 3 条记录，按时间排序
6. **Given** `raw_data_paths` 指向的文件不存在，**When** 反推路径，**Then** 值为 `None`，不阻塞报告生成
7. **Given** `state["human_approved"]=False`，**When** 流水线执行完成，**Then** `state["error"]` 含拒绝信息，publisher 跳过

## 开放问题

| 问题 | 负责人 | 状态 |
|---|---|---|
| Streamlit 未安装 | yanhe | `pip install streamlit`，加入 pyproject.toml |
| 全链路 checkpointer 持久化 | yanhe | Phase 2 |

## 补充说明

- 规格细化：`team-spec/spec/refine/2026-05-30-report-publisher-agent.md`
- 规格评审：`team-spec/spec/reviews/2026-05-30-report-publisher-agent.md`
- 上游 PRD：`team-spec/prd/2026-05-30-strategy-decider-agent.md`（策略决策 v2）
- 系统设计：`docs/A股分析Agent系统设计.md`（全链路 StateGraph 参考架构）
