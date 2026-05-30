# 规格细化：报告推送 Agent

## 需求摘要

报告推送 Agent 是四 Agent 流水线的最后一个节点，纯代码实现。从上游 `decision_report` 组装完整 `AnalysisReport` → Parquet 归档 → Streamlit `app.py` 独立展示。节点负责数据加工和持久化，渲染交给 Streamlit。

## 规范术语

| 术语 | 定义 |
|---|---|
| `report_publisher_agent` | LangGraph 节点，纯代码：组装 `AnalysisReport` + Parquet 落盘。不进 Streamlit |
| `AnalysisReport` | 报告推送 Agent 输出的 Pydantic 模型——上游三维评分的完整汇总 + 原始数据路径引用 |
| `app.py` | Streamlit 独立入口，不在 LangGraph 图中。读 Parquet → 渲染 UI |
| `route_after_decision` | 条件路由：`decision_report` 存在 → `report_publisher`；不存在（拒绝/错误）→ END |
| 原始数据路径引用 | `AnalysisReport.raw_data_paths` 记录上游 Parquet 文件路径，不内嵌原始数据 |
| 文件命名 | `{symbol}_{datetime}.parquet`，永不覆盖，Streamlit 按时间排序展示 |

## 范围

### 范围内

- `report_publisher_agent(state)` 节点函数：组装 `AnalysisReport` + Parquet 归档
- `AnalysisReport` Pydantic 模型（`src/publisher/schemas.py`）
- `route_after_decision(state)` 条件路由
- 条件边集成：`strategy_decider → route_after_decision → report_publisher → END`
- Parquet 存储：`data/reports/{symbol}_{datetime}.parquet`
- 落盘失败 → `error_type: "storage"` 写入 `state["error"]`
- Streamlit `app.py` Phase 1 MVP：输入框 → 进度 → 三维评分表 + 指标数值表 + LLM 研判 + 历史下拉

### 范围外

- HTML/CSS 模板渲染（Jinja）
- 图表、趋势线、多票对比
- 报告导出（PDF/图片）
- 推送通知（手机/邮箱）
- 自定义报告配置

## 流水线结构

```
strategy_decider → route_after_decision
                       ├── decision_report 存在 → report_publisher → END
                       └── decision_report 不存在 → END（跳过，error 已在 state 中）
```

### report_publisher_agent 节点

1. 从 `state` 读取 `symbol`, `technical_report`, `decision_report`
2. 组装 `AnalysisReport`：元信息 + 三维评分 + 12 个指标 + LLM 研判 + 原始数据路径引用
3. `mkdir -p data/reports/`
4. 写入 `data/reports/{symbol}_{datetime}.parquet`
5. 落盘成功 → 返回 `{"report_path": "..."}`
6. 落盘失败 → 返回 `{"error": {"error_type": "storage", "message": "报告存档失败: ..."}}`

### app.py（Streamlit）

独立入口，不在 LangGraph 图中：

1. 输入股票代码 → 调用 LangGraph 流水线（invoke）
2. Spinner 显示执行进度
3. 完成后从 Parquet 读 `AnalysisReport`
4. 三块展示：① 三维评分表 ② 指标数值表 ③ LLM 研判
5. 历史下拉：从 `data/reports/{symbol}_*.parquet` 列出该股票历史分析

## Pydantic 模型

```python
# src/publisher/schemas.py
from pydantic import BaseModel
from src.strategist.schemas import ScoreEntry  # 复用

class AnalysisReport(BaseModel):
    symbol: str
    date: str
    generated_at: str
    scores: dict[str, ScoreEntry]          # 三维评分
    indicators: dict[str, float | None]    # 12 个指标
    overall_judgment: str                  # LLM 研判
    confidence_level: str
    conflict_detected: bool
    conflict_detail: str
    key_driver: str
    risk_warning: str
    bearish_factor: str
    data_sources: list[str]
    raw_data_paths: dict[str, str]         # 原始数据 Parquet 路径引用
```

## 错误处理

| 场景 | 处理 |
|---|---|
| 目录不存在 | `mkdir -p data/reports/` 幂等创建 |
| Parquet 写入失败（磁盘满/权限） | `error_type: "storage"` 写入 `state["error"]`，不阻塞流水线 |
| `decision_report` 不存在（拒绝/错误） | `route_after_decision` 跳过 `report_publisher`，直接 END |
| Streamlit 读 Parquet 失败 | 展示 "暂无分析报告" |

## 边界情况

- 同一只股票同一天多次分析 → 文件名含时间戳，各版本独立保留
- Streamlit 已退出，报告仍存在 → 重新启动后可从历史下拉查看
- `raw_data_paths` 指向的文件被删除 → 报告仍可展示评分和研判，标记"原始数据不可用"

## 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| Streamlit 未安装/未使用过 | P2 | 先安装 `streamlit`，跑通 `streamlit run app.py` 验证环境 |
| 四 Agent 全链路拼接未完成 | P2 | 单独 task：`build_full_pipeline()` 函数，或各 Agent StateGraph 按序 invoke |
| Parquet 文件数量随时间增长 | P3 | Phase 1 单人工具量小；Phase 2 加按日期清理策略 |

## Change Log

- 2026-05-30：初始细化。确认节点/UI 分离、AnalysisReport schema、永不覆盖文件命名、条件路由、Streamlit MVP 范围。
