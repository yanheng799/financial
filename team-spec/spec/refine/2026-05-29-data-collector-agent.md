# 数据采集 Agent 规格细化

**Slug**: `2026-05-29-data-collector-agent`
**状态**: 已完成评审修正，ready for PRD
**创建日期**: 2026-05-29

---

## 需求描述

实现 LangGraph 流水线的第一个节点——数据采集 Agent。接收股票代码作为输入，调用 Tushare API 拉取日线行情、财务指标、资金流三类数据，经 Pydantic 校验后落盘为 Parquet 文件，并将标准化数据写入 LangGraph State 供下游行情分析 Agent 消费。

---

## 已确认的设计决策

### 1. 输出结构

`AnalysisState.raw_data` 按三维拆分为三个子结构，与下游评分函数一一对应：

```python
from typing import TypedDict
from pydantic import BaseModel

# LangGraph State — TypedDict
class AnalysisState(TypedDict):
    symbol: str                    # 股票代码，如 "600519.SH"
    raw_data: dict                 # 采集 Agent 输出（RawData.model_dump()）
    technical_report: dict         # 行情分析 Agent 输出（后续）
    decision_report: dict          # 策略决策 Agent 输出（后续）
    human_approved: bool           # Human-in-the-loop（后续）

# 数据模型 — Pydantic BaseModel
class RawData(BaseModel):
    daily: DailyQuoteData          # 日线 OHLCV → score_technical()
    fundamental: FundData          # 估值 + 财报 → score_fundamental()
    capital: CapitalFlowData       # 资金流 → score_capital()
```

**类型约定**：
- `AnalysisState` 用 `TypedDict`（LangGraph 约定）
- `RawData` / `DailyQuoteData` / `FundData` / `CapitalFlowData` 用 `Pydantic BaseModel`
- 写入 State 时调用 `raw_data.model_dump()`

### 2. 缓存策略

**本地优先 + 手动刷新**：
- 有本地 Parquet 文件 → 直接读取，不调 API
- 用户点击"刷新数据"按钮 → 调 API 全量重拉并覆盖
- 无本地文件 → 自动调 API 拉取并落盘

### 3. 用户输入

- **仅股票代码**（如 `600519`、`000001`），系统自动补全交易所后缀
- **后缀补全规则**：

| 交易所 | 代码 | 后缀 | 示例 |
|---|---|---|---|
| 上海证券交易所 | SSE | `.SH` | 600000.SH（股票），000001.SH（指数） |
| 深圳证券交易所 | SZSE | `.SZ` | 000001.SZ（股票），399005.SZ（指数） |
| 北京证券交易所 | BSE | `.BJ` | 9xxxxx（股票） |
| 香港证券交易所 | HKEX | `.HK` | 00001.HK（Phase 2） |

补全逻辑：6 开头 → `.SH`，0/3 开头 → `.SZ`，9 开头 → `.BJ`。Phase 1 仅支持 A 股（SH/SZ/BJ），港股留 Phase 2。

- **时间范围系统自动决定**，按维度不同：

| 维度 | 默认时间范围 | 理由 |
|---|---|---|
| 日线行情 | 近 1 年（约 250 个交易日） | 需要足够数据算 MA60、MACD |
| 估值与财务指标 | 近 8 个季度 + 最近年度 | 看财务趋势和 PE 分位 |
| 资金流 | 近 1 个月（约 20 个交易日） | 资金流时效性强 |

### 4. 代码组织

按功能域扁平组织，每个 Agent 一个自包含目录：

```
src/
├── collector/              # 数据采集 Agent
│   ├── __init__.py
│   ├── adapter.py          # Tushare API 调用
│   ├── schemas.py          # Pydantic 模型
│   └── storage.py          # Parquet 读写
├── analyzer/               # 行情分析 Agent（后续）
├── strategist/             # 策略决策 Agent（后续）
├── publisher/              # 报告推送 Agent（后续）
└── state.py                # LangGraph State 定义（共享）
```

### 5. 存储位置

项目根目录 `data/`，按维度分子目录：

```
data/
├── daily/                  # 日线行情 Parquet
│   └── 600519.SH.parquet
├── fundamental/            # 估值 + 财务基本面 Parquet
│   └── 600519.SH.parquet
└── capital/                # 资金流 Parquet
    └── 600519.SH.parquet
```

`data/` 目录加入 `.gitignore`。

---

## Tushare 接口与字段映射

### 日线行情（`daily`）→ raw_data.daily

| Tushare 接口 | 关键字段 | 下游消费者 |
|---|---|---|
| `daily` | `ts_code`, `trade_date`, `open`, `high`, `low`, `close`, `vol`, `amount` | score_technical() — OHLCV 行情 |

### 估值与财务指标（`daily_basic` + `fina_indicator` + `income`）→ raw_data.fundamental

| Tushare 接口 | 关键字段 | 下游消费者 |
|---|---|---|
| `daily_basic` | `ts_code`, `trade_date`, `pe`, `pe_ttm`, `pb`, `turnover_rate` | score_fundamental() — PE/PB 分位 |
| `fina_indicator` | `ts_code`, `ann_date`, `end_date`, `roe`, `grossprofit_margin`, `netprofit_margin`, `current_ratio`, `debt_to_assets` | score_fundamental() — 质量指标 |
| `income` | `ts_code`, `ann_date`, `end_date`, `total_revenue`, `revenue_yoy`, `n_income`, `netprofit_yoy` | score_fundamental() — 营收利润趋势 |

### 资金流（`moneyflow`）→ raw_data.capital

| Tushare 接口 | 关键字段 | 下游消费者 |
|---|---|---|
| `moneyflow` | `ts_code`, `trade_date`, `buy_sm_amount`, `sell_sm_amount`, `buy_lg_amount`, `sell_lg_amount`, `net_mf_amount` | score_capital() |

---

## Pydantic 校验规则

校验放在采集出口，脏数据在进入分析层之前被拦截：

1. **Schema 校验**：字段名和类型必须匹配 Pydantic 模型定义
2. **关键字段存在性**：`ts_code`、`trade_date`（日线）或 `end_date`（财务）不可为空
3. **日期标准化**：统一 `YYYYMMDD` 字符串格式
4. **数值类型规范化**：价格/比率类字段为 `float`，成交量为 `float`（Tushare 返回的 vol 单位是千手）
5. **去重**：按主键（`ts_code` + `trade_date` 或 `ts_code` + `end_date`）去重
6. **排序**：按日期降序（最新数据在前）

每条数据写入时必须携带可追溯性三字段：
- `source`：接口名，如 `"tushare:daily"`
- `fetched_at`：拉取时间，ISO 8601 格式（如 `"2026-05-29T16:30:00+08:00"`）
- `raw_value`：**该行数据首次获取时的完整 JSON 字符串**，用于后续比对数据源是否修正过历史值（如财报修正）

---

## 分段拉取规则

长区间不分段一次性拉取可能导致 Tushare API 超时或数据不全：

| 数据类型 | 分段策略 |
|---|---|
| 日线行情（1 年） | 按半年分段，每次拉 6 个月 |
| 估值指标（1 年） | 按半年分段，每次拉 6 个月（随日线同期拉取） |
| 财务指标（8 季度） | 不分段（数据量小） |
| 资金流（1 个月） | 不分段（数据量小） |

分段拉取后合并、去重、排序。**分段部分失败时不落盘**——确保本地 Parquet 要么完整要么不存在，避免下游读到不完整数据。

---

## 错误处理

| 错误类型 | 处理方式 |
|---|---|
| Token 未配置 | 启动时检查，缺失则报错并给出配置指引 |
| 网络超时 / HTTP 429 | 最多重试 2 次，间隔 3 秒 |
| 参数错误 / 权限不足 | 不重试，直接报错，返回错误详情 |
| 空结果 | 区分原因：非交易日 / 未上市 / 无权限，标注后返回 |
| 分段部分失败 | 不落盘，报错并说明哪些分段失败，要求用户重试 |
| `moneyflow` 积分不足 | 资金面维度标注"数据不足"（confidence: "insufficient"），三维评分自动降为二维，置信度规则同步调整 |

---

## 验收标准

1. 给定股票代码（如 `600519`），能正确拉取日线、估值财务、资金流三类数据
2. 每条数据携带 `source`、`fetched_at`、`raw_value` 三字段
3. Pydantic 校验能拦截缺失关键字段或类型错误的数据
4. 数据正确落盘为 Parquet 文件，文件路径符合 `data/{维度}/{ts_code}.parquet` 规范
5. 重复运行时直接读取本地文件，不调 API
6. 手动刷新后重新拉取并覆盖本地文件
7. Token 缺失时给出清晰的配置指引
8. `moneyflow` 接口返回权限错误时，资金面标注"数据不足"，不阻塞其他维度

---

## 范围外

- AKShare 数据源接入（Phase 2）
- 股票名称模糊搜索（Phase 2）
- 增量更新（Phase 2 考虑）
- 港股数据（Phase 2）
- LLM 调用（采集 Agent 纯代码）
- 技术指标计算（行情分析 Agent 职责）
- Streamlit UI 界面（单独实现）

---

## Change Log

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-05-29 | 初始创建 | 数据采集 Agent 规格细化完成 |
| 2026-05-29 | 评审修正 v2 | 修正 6 项评审问题：P1 daily_basic 归入 fundamental；P2 raw_value 定义为 JSON 字符串；P2 股票代码后缀规则（含北交所 9 开头）；P2 moneyflow 积分降级；P2 State 类型统一（TypedDict + BaseModel）；P3 分段失败不落盘 |

---

## 下一步

推荐使用 `team-spec-review` 确认修正后的规格无残留 P0/P1，然后使用 `team-spec-to-prd` 固化 PRD。
