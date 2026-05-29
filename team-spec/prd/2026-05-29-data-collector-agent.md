# PRD：数据采集 Agent

## 问题陈述

A 股分析 Agent 系统目前没有可运行的代码。四 Agent 流水线（数据采集 → 行情分析 → 策略决策 → 报告推送）中，数据采集是第一个节点，也是所有下游 Agent 的数据基础。没有它，后续的分析、评分和报告都无法运行。

用户需要一个可靠的自动化数据获取层：输入股票代码，系统自动从 Tushare 拉取日线行情、估值财务、资金流三类数据，校验后落盘，供下游消费。

## 目标

- 实现一个纯代码的数据采集 Agent，作为 LangGraph StateGraph 的第一个节点
- 输入股票代码后，能自动拉取覆盖三维评分所需的全部原始数据
- 数据经 Pydantic 校验后落盘为 Parquet 文件，具备可追溯性
- 支持本地缓存，避免重复调 API

## 非目标

- AKShare 数据源接入（Phase 2）
- 股票名称模糊搜索（Phase 2）
- 增量更新策略（Phase 2）
- 港股/美股数据（Phase 2）
- 技术指标计算（行情分析 Agent 职责）
- LLM 调用（采集 Agent 纯代码）
- Streamlit UI（单独实现）

## 用户与场景

1. 作为个人投资者，我希望输入一个股票代码（如 `600519`），系统能自动拉取该股票的行情、财务和资金流数据，以便后续进行三维评分分析。
2. 作为个人投资者，我希望数据拉取后自动保存在本地，再次分析同一只股票时不需要重复调 API，以节省 Tushare 积分和等待时间。
3. 作为个人投资者，我希望点击"刷新数据"时系统重新拉取并覆盖本地数据，以便获取最新行情。
4. 作为个人投资者，我希望数据有误时系统能明确告诉我哪个接口失败、什么原因，而不是静默返回不完整数据。

## 当前状态

- 项目 `src/` 目录为空，无任何应用代码
- Tushare 已安装（v1.4.29），Skill 定义和接口文档已就绪
- LangGraph 已安装（v1.2.2），StateGraph 编排模式已在设计文档中定义
- 下游行情分析 Agent、策略决策 Agent、报告推送 Agent 均未实现

## 方案描述

数据采集 Agent 作为 LangGraph 流水线的 `data_collector` 节点运行。用户在 Streamlit 输入股票代码并触发分析后，该 Agent 执行以下流程：

1. **解析输入**：接收裸代码（如 `600519`），自动补全交易所后缀（→ `600519.SH`）
2. **检查缓存**：如果本地 `data/` 目录已有该股票的 Parquet 文件，直接读取返回
3. **调 Tushare API**：按维度分别拉取日线行情、估值财务、资金流数据
4. **Pydantic 校验**：在采集出口拦截脏数据（缺失字段、类型错误、重复行）
5. **附加可追溯性**：每行数据标注 `source`、`fetched_at`、`raw_value`
6. **落盘**：按维度和接口存为 Parquet 文件
7. **写入 State**：将标准化数据通过 `RawData.model_dump()` 写入 `AnalysisState.raw_data`

## 范围

### 范围内

- 股票代码解析与交易所后缀补全（A 股：SH/SZ/BJ）
- Tushare API 调用封装（5 个接口）
- Pydantic 数据模型与校验
- Parquet 文件读写与缓存
- 分段拉取与错误处理
- LangGraph State 节点集成

### 范围外

- Streamlit UI（按钮、输入框、进度条）— 单独实现
- LLM 推理 — 采集 Agent 纯代码
- 技术指标计算 — 行情分析 Agent
- AKShare 数据源 — Phase 2
- 定时任务 — Phase 2

## 功能需求

### FR-1：股票代码解析

1. 系统必须接受裸股票代码（如 `600519`、`000001`、`920001`）
2. 系统必须自动补全交易所后缀：6 开头 → `.SH`，0/3 开头 → `.SZ`，9 开头 → `.BJ`
3. 系统必须拒绝 Phase 1 不支持的代码格式（如港股 5 位纯数字），返回明确错误
4. 系统必须接受已带后缀的完整代码（如 `600519.SH`），跳过补全

### FR-2：Tushare API 调用

5. 系统必须调用以下 5 个 Tushare 接口获取数据：

| 接口 | 频率 | 关键字段 | 维度 |
|---|---|---|---|
| `daily` | 日频 | ts_code, trade_date, open, high, low, close, vol, amount | daily |
| `daily_basic` | 日频 | ts_code, trade_date, pe, pe_ttm, pb, turnover_rate | fundamental |
| `fina_indicator` | 季频 | ts_code, ann_date, end_date, roe, grossprofit_margin, netprofit_margin, debt_to_assets | fundamental |
| `income` | 季频 | ts_code, ann_date, end_date, total_revenue, revenue_yoy, n_income, netprofit_yoy | fundamental |
| `moneyflow` | 日频 | ts_code, trade_date, buy_sm_amount, sell_sm_amount, buy_lg_amount, sell_lg_amount, net_mf_amount | capital |

6. 系统必须按维度自动确定时间范围：日线行情近 1 年、估值指标近 1 年、财务指标近 8 季度、资金流近 1 个月
7. 系统必须对长区间数据分段拉取：日线和估值按半年分段，财务和资金流不分段
8. 系统必须在 Token 未配置时给出配置指引，不静默失败

### FR-3：数据校验

9. 系统必须在采集出口对每批数据做 Pydantic 校验，不合格数据不进入下游
10. 系统必须对每行数据附加三个可追溯性字段：`source`（接口名）、`fetched_at`（ISO 8601 时间戳）、`raw_value`（该行首次获取时的完整 JSON 字符串）
11. 系统必须按主键去重（日线：ts_code + trade_date；财务：ts_code + end_date）
12. 系统必须按日期降序排序（最新数据在前）

### FR-4：数据存储

13. 系统必须将数据存为 Parquet 文件，目录结构为 `data/{维度}/{ts_code}_{接口名}.parquet`
14. 具体文件路径：
    - `data/daily/{ts_code}.parquet` — 仅 `daily` 接口数据
    - `data/fundamental/{ts_code}_daily_basic.parquet` — 日频估值数据
    - `data/fundamental/{ts_code}_fina_indicator.parquet` — 季频质量指标
    - `data/fundamental/{ts_code}_income.parquet` — 季频营收利润
    - `data/capital/{ts_code}.parquet` — 资金流数据
15. `data/` 目录必须加入 `.gitignore`

### FR-5：缓存策略

16. 系统必须在本地已有对应 Parquet 文件时直接读取，不调 Tushare API
17. 系统必须支持手动刷新：触发刷新时全量重拉并覆盖本地文件
18. 系统必须在无本地文件时自动调 API 拉取并落盘

### FR-6：LangGraph 集成

19. 采集 Agent 必须作为 `data_collector` 节点挂载到 LangGraph StateGraph
20. 采集 Agent 必须将数据写入 `AnalysisState.raw_data`，格式为 `RawData.model_dump()`
21. `RawData` 必须包含三个字段：`daily`（日线行情）、`fundamental`（估值+财务）、`capital`（资金流）

## 业务规则

- **可追溯性硬约束**：`source`、`fetched_at`、`raw_value` 三字段在数据写入时附加，不事后补
- **校验在出口拦截**：Pydantic 校验放在采集 Agent 输出边界，脏数据不进入分析层
- **完整性优先**：分段拉取部分失败时不落盘，确保本地 Parquet 要么完整要么不存在
- **降级不阻塞**：`moneyflow` 接口因 Tushare 积分不足返回错误时，资金面维度标注 confidence: "insufficient"，不阻塞其他维度数据采集

## 边界情况与错误状态

| 场景 | 预期行为 |
|---|---|
| 用户输入不认识的代码（如 `1234567`） | 补全后缀后调 Tushare，若 API 返回空结果，返回"未找到该股票"错误 |
| 用户输入港股代码（如 `00001`） | 按 0 开头补全为 `.SZ`，Tushare 返回空结果，返回"Phase 1 仅支持 A 股"提示 |
| Tushare API 网络超时 | 最多重试 2 次，间隔 3 秒；仍失败则报错，不落盘 |
| Tushare `moneyflow` 积分不足 | 资金面标注"数据不足"，日线和财务正常返回 |
| 查询日期为非交易日 | Tushare 返回空结果，系统标注"该日期非交易日"，不视为错误 |
| 股票尚未上市（如查询未来 IPO 代码） | Tushare 返回空结果，系统标注"该股票尚未上市" |
| 日线分段拉取第 1 段成功、第 2 段失败 | 不落盘，返回错误说明第 2 段失败，要求重试 |

## 数据与状态

### Pydantic 模型

```python
from pydantic import BaseModel
from typing import TypedDict

class AnalysisState(TypedDict):
    symbol: str
    raw_data: dict
    technical_report: dict
    decision_report: dict
    human_approved: bool

class RawData(BaseModel):
    daily: DailyQuoteData
    fundamental: FundData
    capital: CapitalFlowData

class DailyQuoteData(BaseModel):
    # daily 接口数据（OHLCV），每行含 source/fetched_at/raw_value
    data: list[dict]

class FundData(BaseModel):
    daily_basic: list[dict]       # 日频估值（PE/PB）
    fina_indicator: list[dict]    # 季频质量指标（ROE 等）
    income: list[dict]            # 季频营收利润

class CapitalFlowData(BaseModel):
    # moneyflow 接口数据，可能为空（积分不足时）
    data: list[dict] | None
    insufficient: bool = False    # 积分不足标记
```

### 存储结构

```
data/
├── daily/
│   └── {ts_code}.parquet
├── fundamental/
│   ├── {ts_code}_daily_basic.parquet
│   ├── {ts_code}_fina_indicator.parquet
│   └── {ts_code}_income.parquet
└── capital/
    └── {ts_code}.parquet
```

每个 Parquet 文件在标准字段之外包含三列：`source`、`fetched_at`、`raw_value`。

## 实现决策

- **代码位置**：`src/collector/` 目录，含 `adapter.py`（Tushare 调用）、`schemas.py`（Pydantic 模型）、`storage.py`（Parquet 读写）
- **共享 State**：`src/state.py` 定义 `AnalysisState`（TypedDict），所有 Agent 共用
- **Adapter 抽象**：`adapter.py` 中 `TushareAdapter` 类封装 API 调用，后续加 AKShare 只需新增 `AkshareAdapter` 实现同一接口
- **日期格式**：Tushare API 传入和返回的日期统一为 `YYYYMMDD` 字符串
- **成交量单位**：Tushare `daily` 的 `vol` 字段单位为千手，需在 Pydantic 校验中标注但不转换
- **fundamental 子文件拆分**：因 `daily_basic`（日频）与 `fina_indicator`/`income`（季频）频率不同，按接口拆分为独立 Parquet 文件，避免混合频率的 schema 冲突

## 测试决策

### 自动化测试

- **API 调用 mock 测试**：mock Tushare API 返回值，验证 Pydantic 校验能拦截脏数据（缺失字段、类型错误）
- **代码补全测试**：覆盖 6xx→SH、0xx→SZ、3xx→SZ、9xx→BJ、完整代码跳过补全、无效代码报错
- **缓存逻辑测试**：本地有文件时跳过 API、无文件时调 API、刷新时覆盖
- **分段拉取测试**：验证分段合并、去重、排序逻辑；部分失败时不落盘
- **降级测试**：`moneyflow` 返回权限错误时，其他维度正常，资金面标记 insufficient

### 手工验收

- 用 3 只熟悉股票（如 600519.SH 茅台、000001.SZ 平安、920001.BJ）跑完整流程
- 手工抽查 20 个数据点与 Tushare 网页端交叉验证

## 验收标准

1. **Given** 本地无数据，**When** 输入 `600519` 触发采集，**Then** 成功拉取 daily/daily_basic/fina_indicator/income/moneyflow 五个接口数据，`data/` 下生成 5 个 Parquet 文件
2. **Given** 本地已有 `600519.SH` 的 Parquet 文件，**When** 再次触发采集，**Then** 直接读取本地文件，无 Tushare API 调用
3. **Given** 用户点击"刷新数据"，**When** 触发采集，**Then** 调 Tushare API 全量重拉，覆盖本地文件
4. **Given** Tushare Token 未配置，**When** 触发采集，**Then** 报错并给出 `export TUSHARE_TOKEN=...` 配置指引
5. **Given** `moneyflow` 接口返回权限错误，**When** 采集完成，**Then** 日线和财务数据正常，资金面 `insufficient=True`
6. **Given** 日线分段拉取第 2 段失败，**When** 采集完成，**Then** daily 目录下无 Parquet 文件，返回错误说明第 2 段失败
7. **Given** 输入 `000001`，**When** 系统解析，**Then** 补全为 `000001.SZ`
8. **Given** 每个 Parquet 文件，**When** 检查列，**Then** 包含 `source`、`fetched_at`、`raw_value` 三列

## 开放问题

| 问题 | 负责人 | 不解决的影响 |
|---|---|---|
| 用户的 Tushare 积分是否覆盖 `moneyflow` 接口？ | yanhe | 如不覆盖，资金面持续为空，三维评分实际只有二维 |
| `daily_basic` 的 `turnover_rate` 是否被 `score_technical()` 使用？ | yanhe（实现行情分析 Agent 时确认） | 如使用，评分函数需从 `raw_data.fundamental.daily_basic` 读取 |

## 补充说明

- Tushare Skill 定义：`.agents/skills/tushare/SKILL.md`
- Tushare 接口目录：`.agents/skills/tushare/references/数据接口.md`
- 系统设计文档：`docs/A股分析Agent系统设计.md`
- 设计决策记录：`docs/设计决策.md`
- 规格细化：`team-spec/spec/refine/2026-05-29-data-collector-agent.md`
- 规格评审：`team-spec/spec/reviews/2026-05-29-data-collector-agent.md`
