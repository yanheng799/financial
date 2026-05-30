# PRD：行情分析 Agent

## 问题陈述

数据采集 Agent 已实现，能产出日线行情、估值财务、资金流三类原始数据。但这些数据是未经加工的原始值，下游策略决策 Agent（LLM）不能直接使用——设计约束明确禁止让 LLM 碰原始数据计算。系统需要一个纯代码的中间层：从原始数据中计算技术指标、量化基本面和资金面信号，输出 -2~+2 的结构化评分，供 LLM 消费。

## 目标

- 实现一个纯代码的行情分析 Agent，作为 LangGraph StateGraph 的 `market_analyzer` 节点
- 从 `AnalysisState.raw_data` 读取数据采集 Agent 产出的三维原始数据，计算技术指标和三维评分
- 评分输出结构化的 `TechnicalReport`（含分数、原因、指标值），供策略决策 Agent 的 LLM prompt 直接引用
- 评分阈值可配置，调优时不改代码

## 非目标

- LLM 调用（策略决策 Agent 职责）
- `human_review` 节点（后续 PRD 实现）
- Phase 2 指标（KDJ、BOLL、RSI、ATR）
- 情绪面评分维度
- 评分阈值自动调优
- Streamlit 展示
- 技术指标可视化（图表）

## 用户与场景

1. 作为个人投资者，我希望系统自动计算技术指标（MA、MACD、成交量比）并给出技术面评分，以便我无需手动看K线判断趋势方向。
2. 作为个人投资者，我希望系统自动评估基本面（估值位置、盈利能力、成长趋势）并给出基本面评分，以便我无需逐一翻财报数据。
3. 作为个人投资者，我希望系统自动分析资金流向并给出资金面评分，以便我了解主力资金动向。
4. 作为个人投资者，我希望某些股票数据不足时系统仍能给出已有维度的评分，而不是完全拒绝分析。

## 当前状态

- 数据采集 Agent（`src/collector/`）已实现并通过验收，产出 `RawData` 写入 `AnalysisState.raw_data`
- `RawData` 包含三维数据：`daily`（OHLCV 日线）、`fundamental`（daily_basic + fina_indicator + income）、`capital`（moneyflow）
- `AnalysisState.technical_report` 字段已定义（`dict` 类型），尚无生产者
- `pandas-ta` 已列入依赖但未安装，需在开发启动时验证兼容性
- `src/analyzer/` 目录尚未创建

## 方案描述

行情分析 Agent 作为 LangGraph 流水线的 `market_analyzer` 节点运行。数据采集 Agent 完成后，该 Agent 执行以下流程：

1. **读取原始数据**：从 `AnalysisState.raw_data` 获取三维原始数据
2. **计算技术指标**：使用 `pandas-ta` 计算 MA（5/20/60）、MACD（12/26/9）、成交量均量比（20 日）
3. **计算基本面指标**：从 `daily_basic` 计算 PE_TTM 近 1 年分位数，从 `fina_indicator` 读取 `roe_yearly`（年化 ROE）、`tr_yoy`（营收同比）、`netprofit_yoy`（净利润同比）
4. **计算资金面指标**：从 `capital` 数据计算近 5 日主力净流入/流出和大单买卖比率
5. **三维评分**：分别调用 `score_technical()`、`score_fundamental()`、`score_capital()`，每维输出 -2~+2 整数 + reason
6. **组装输出**：将评分和指标值组装为 `TechnicalReport`，写入 `AnalysisState.technical_report`

## 范围

### 范围内

- 三个评分函数 `score_technical/fundamental/capital`
- 技术指标计算：MA（5/20/60）、MACD（12/26/9）、成交量均量比（20 日）
- 基本面指标计算：PE_TTM 近 1 年分位数、年化 ROE（`roe_yearly`）、营收/净利润同比（`tr_yoy`/`netprofit_yoy`）
- 资金面指标计算：近 5 日主力净流入/流出、大单买卖比率
- 阈值配置文件
- LangGraph `market_analyzer` 节点函数 + StateGraph 集成
- Pydantic 输出模型 `TechnicalReport`、`DimensionScore`
- 数据不足时的降级处理

### 范围外

- LLM 调用（策略决策 Agent 职责）
- `human_review` 节点（后续 PRD）
- Phase 2 指标（KDJ、BOLL、RSI、ATR）
- 情绪面维度
- Streamlit 展示
- 评分阈值自动调优

## 功能需求

### FR-1：技术指标计算

1. 系统必须使用 `pandas-ta` 从 `raw_data.daily.data` 计算 MA5、MA20、MA60
2. 系统必须使用 `pandas-ta` 计算 MACD（参数 12/26/9），输出 MACD 柱状图值（`macd_hist`）及前一日柱状图值（`macd_hist_prev`）
3. 系统必须计算成交量均量比 `vol_ratio = 当日 vol / 近 20 日 vol 均值`
4. 系统必须在数据不足时跳过依赖缺失数据的指标（如日线 < 60 天时跳过 MA60 相关规则）

### FR-2：基本面指标计算

5. 系统必须从 `raw_data.fundamental.daily_basic` 提取最新 PE_TTM，计算其在近 1 年数据中的百分位排名
6. 系统必须从 `raw_data.fundamental.fina_indicator` 提取最新季度的 `roe_yearly`（年化净资产收益率）
7. 系统必须从 `raw_data.fundamental.fina_indicator` 提取最新季度的 `tr_yoy`（营业总收入同比）和 `netprofit_yoy`（归母净利润同比）

### FR-3：资金面指标计算

8. 系统必须从 `raw_data.capital.data` 计算近 5 日 `net_mf_amount` 合计值
9. 系统必须从 `raw_data.capital.data` 计算最近 1 日的 `buy_lg_amount / sell_lg_amount` 比率
10. 系统必须在 `capital.insufficient == True` 时跳过资金面评分，返回 `score=0, reason="资金面数据不足"`

### FR-4：三维评分

11. 系统必须实现三个独立评分函数，每个输出 -2~+2 整数和 reason 文本：

**`score_technical(indicators)`**：

| 规则 | 条件 | 得分 | reason |
|---|---|---|---|
| MA 排列 | MA5 > MA20 > MA60 | +1 | "均线多头排列" |
| | MA5 < MA20 < MA60 | -1 | "均线空头排列" |
| MACD 柱 | macd_hist > 0 且 macd_hist > macd_hist_prev | +1 | "MACD柱扩张" |
| | macd_hist < 0 且 macd_hist < macd_hist_prev | -1 | "MACD柱缩减" |
| 成交量修正 | vol_ratio > 1.5 | 不变 | 放量确认信号 |
| | vol_ratio < 0.7 | score × 0.5（取整） | 缩量削弱信号 |

最终 clamp 到 [-2, +2]。

**`score_fundamental(indicators)`**：

| 规则 | 条件 | 得分 | reason |
|---|---|---|---|
| 估值位置 | 最新 PE_TTM < 近 1 年 30% 分位 | +1 | "PE处于近一年低位" |
| | 最新 PE_TTM > 近 1 年 70% 分位 | -1 | "PE处于近一年高位" |
| 盈利能力 | roe_yearly > 15% | +1 | "ROE优秀(>15%)" |
| | roe_yearly < 3% | -1 | "ROE偏低(<3%)" |
| 成长趋势 | tr_yoy > 10% 且 netprofit_yoy > 10% | +1 | "营收净利润双增长" |
| | tr_yoy < 0 且 netprofit_yoy < 0 | -1 | "营收净利润双降" |

最终 clamp 到 [-2, +2]。

**`score_capital(indicators)`**：

| 规则 | 条件 | 得分 | reason |
|---|---|---|---|
| 主力方向 | 近 5 日 net_mf_amount 合计 > 0 | +1 | "近5日主力净流入" |
| | 近 5 日 net_mf_amount 合计 < 0 | -1 | "近5日主力净流出" |
| 大单强弱 | buy_lg_amount / sell_lg_amount > 1.5 | +1 | "大单买入强势" |
| | buy_lg_amount / sell_lg_amount < 0.67 | -1 | "大单卖出强势" |

最终 clamp 到 [-2, +2]。

12. 所有评分阈值必须从配置文件读取，不硬编码在评分函数中
13. Tushare 字段名（如 `roe_yearly`、`tr_yoy`、`netprofit_yoy`）硬编码在函数内，不暴露到配置文件

### FR-5：输出结构

14. 系统必须输出 `TechnicalReport` Pydantic 模型：

```python
class DimensionScore(BaseModel):
    value: int                  # -2 ~ +2
    reason: str                 # 评分原因文本
    data_sufficient: bool       # 维度数据是否充足

class TechnicalReport(BaseModel):
    symbol: str                 # "600519.SH"
    date: str                   # "YYYYMMDD"
    scores: dict[str, DimensionScore]  # technical / fundamental / capital
    indicators: dict            # 所有计算的派生指标值
    generated_at: str           # ISO 8601
```

15. `indicators` 字段必须包含以下键：

| 键名 | 来源维度 | 说明 |
|---|---|---|
| `ma5` / `ma20` / `ma60` | technical | 最新日均线值 |
| `macd_hist` / `macd_hist_prev` | technical | 当日和前一日 MACD 柱状图 |
| `vol_ratio` | technical | 当日成交量 / 20 日均量 |
| `pe_ttm` / `pe_percentile_1y` | fundamental | 最新 PE_TTM 及其近 1 年百分位 |
| `roe_yearly` | fundamental | 最新季年化 ROE |
| `tr_yoy` / `netprofit_yoy` | fundamental | 最新季营收和净利润同比 |
| `net_mf_amount_5d` | capital | 近 5 日主力净流入/流出合计 |
| `lg_buy_sell_ratio` | capital | 最近 1 日大单买卖比率 |

16. `scores` 使用 `dict[str, DimensionScore]` 结构，Phase 2 加情绪面维度只需新增 key

### FR-6：LangGraph 集成

17. 系统必须实现 `market_analyzer_agent(state: AnalysisState) -> dict` 作为 LangGraph 节点函数
18. 系统必须实现 `build_analyzer_graph()` 函数构建包含 `market_analyzer` 节点的 StateGraph
19. 节点必须从 `state["raw_data"]` 读取数据，将 `TechnicalReport.model_dump()` 写入 `state["technical_report"]`

## 业务规则

- **评分由代码计算**：-2~+2 整数，函数实现，不依赖 LLM 主观判断
- **降级不阻塞**：部分规则因数据不足跳过时，仍按已有规则打分；整个维度数据缺失时才标记 `data_sufficient=False` 并归零
- **阈值可配置**：评分阈值从配置文件读取，规则结构硬编码
- **指标值透明传递**：所有计算的派生指标值通过 `indicators` 字段传递给下游，不让 LLM 自行计算
- **成交量修正非独立评分**：vol_ratio 不单独产生 ±1 得分，而是作为修正因子（放量确认、缩量削弱）

## 边界情况与错误状态

| 场景 | 预期行为 |
|---|---|
| 日线 < 60 天（MA60 算不出） | 只算 MA5/MA20，跳过 MA 排列规则，`data_sufficient=True` |
| 日线 < 5 天 | `score_technical=0, reason="日线数据不足，无法计算技术指标", data_sufficient=False` |
| PE_TTM 全部为空 | 估值规则跳过，只按 ROE + 成长打分，`data_sufficient=True` |
| 无财报数据（新股） | `score_fundamental=0, reason="暂无财务数据", data_sufficient=False` |
| 资金面积分不足（`insufficient=True`） | `score_capital=0, reason="资金面数据不足", data_sufficient=False` |
| `raw_data` 中无 daily 数据 | 所有三个维度标记 `data_sufficient=False`，返回错误 |
| `raw_data` 为空 dict | 节点返回结构化错误 |

## 数据与状态

### 输入

从 `AnalysisState.raw_data`（即 `RawData.model_dump()`）读取：

| 数据路径 | 内容 | 消费者 |
|---|---|---|
| `raw_data.daily.data` | OHLCV 日线（list[dict]） | `score_technical()` |
| `raw_data.fundamental.daily_basic` | 日频估值（PE_TTM 等，list[dict]） | `score_fundamental()` |
| `raw_data.fundamental.fina_indicator` | 季频财务指标（roe_yearly、tr_yoy、netprofit_yoy，list[dict]） | `score_fundamental()` |
| `raw_data.capital.data` | 日频资金流（net_mf_amount 等，list[dict]） | `score_capital()` |
| `raw_data.capital.insufficient` | 资金面积分不足标记 | `score_capital()` |

### 输出

写入 `AnalysisState.technical_report`（即 `TechnicalReport.model_dump()`）：

```python
{
    "symbol": "600519.SH",
    "date": "20260530",
    "scores": {
        "technical": {"value": 1, "reason": "均线多头排列；MACD柱扩张", "data_sufficient": True},
        "fundamental": {"value": 1, "reason": "PE处于近一年低位；ROE优秀(>15%)", "data_sufficient": True},
        "capital": {"value": -1, "reason": "近5日主力净流出", "data_sufficient": True}
    },
    "indicators": {
        "ma5": 1850.2, "ma20": 1820.5, "ma60": 1780.0,
        "macd_hist": 0.04, "macd_hist_prev": 0.02,
        "vol_ratio": 1.8,
        "pe_ttm": 30.5, "pe_percentile_1y": 25.0,
        "roe_yearly": 0.31,
        "tr_yoy": 0.12, "netprofit_yoy": 0.15,
        "net_mf_amount_5d": -2.3e8,
        "lg_buy_sell_ratio": 0.6
    },
    "generated_at": "2026-05-30T14:30:00"
}
```

### 配置文件

评分阈值配置（YAML 或 TOML），包含以下参数：

| 参数 | 默认值 | 用途 |
|---|---|---|
| `vol_ratio.confirm` | 1.5 | 放量确认阈值 |
| `vol_ratio.weaken` | 0.7 | 缩量削弱阈值 |
| `pe.low_percentile` | 30 | PE 低位百分位 |
| `pe.high_percentile` | 70 | PE 高位百分位 |
| `roe.high` | 15 | ROE 优秀阈值（%） |
| `roe.low` | 3 | ROE 偏低阈值（%） |
| `yoy.high` | 10 | 同比增长阈值（%） |
| `capital_flow.days` | 5 | 主力方向回看天数 |
| `lg_ratio.strong` | 1.5 | 大单买入强势比率 |
| `lg_ratio.weak` | 0.67 | 大单卖出强势比率 |
| `min_daily_rows` | 5 | 技术面最少日线行数 |

## 实现决策

- **代码位置**：`src/analyzer/` 目录，含 `indicators.py`（指标计算）、`scoring.py`（评分函数）、`schemas.py`（Pydantic 模型）、`node.py`（LangGraph 节点）
- **共享 State**：沿用 `src/state.py` 的 `AnalysisState`，写入 `technical_report` 字段
- **指标库**：`pandas-ta`（MA、MACD）；vol_ratio 手动计算（当日 vol / 20 日均值）
- **配置文件**：`configs/scoring.yaml`（或 `.toml`），评分函数启动时读取
- **日期格式**：沿用项目约定 `YYYYMMDD`
- **scores 结构**：使用 `dict[str, DimensionScore]` 而非三个独立字段，Phase 2 加情绪面只需新增 key
- **成交量修正**：vol_ratio 不独立评分，作为修正因子（缩量时 score × 0.5 后取整）

## 测试决策

### 自动化测试

- **指标计算测试**：mock OHLCV DataFrame，验证 MA/MACD/vol_ratio 计算正确性
- **评分函数测试**：每个评分函数用边界值覆盖所有规则分支（每个条件至少一个正例和一个反例）
- **成交量修正测试**：验证放量保持分数、缩量削弱分数
- **降级测试**：日线不足、PE 为空、无财报、资金面积分不足等场景
- **输出结构测试**：验证 `TechnicalReport` 包含所有必需字段
- **配置读取测试**：验证评分阈值从配置文件读取而非硬编码
- **StateGraph 测试**：mock `raw_data`，验证节点读写 `AnalysisState` 正确

### 手工验收

- 用数据采集 Agent 已产出的真实 Parquet 数据（600519.SH）跑完整评分流程
- 手工抽查指标值与券商 APP 对比

## 验收标准

1. **Given** `raw_data` 包含 600519.SH 完整数据（日线 > 60 天、有财报、有资金流），**When** 通过 StateGraph 执行 `market_analyzer` 节点，**Then** `technical_report.scores` 包含 technical/fundamental/capital 三个 `DimensionScore`，每个 value 在 [-2, +2] 范围内
2. **Given** MA5 > MA20 > MA60 且 MACD 柱扩张且 vol_ratio > 1.5，**When** 执行 `score_technical()`，**Then** value=2，reason 包含"均线多头排列"和"MACD柱扩张"
3. **Given** MA5 < MA20 < MA60 且 MACD 柱缩减，**When** 执行 `score_technical()`，**Then** value=-2，reason 包含"均线空头排列"和"MACD柱缩减"
4. **Given** vol_ratio < 0.7（缩量），**When** 执行 `score_technical()`，**Then** 分数被削弱（取 score × 0.5 的整数部分）
5. **Given** PE_TTM 处于近 1 年 25% 分位且 roe_yearly=20% 且 tr_yoy=15% 且 netprofit_yoy=12%，**When** 执行 `score_fundamental()`，**Then** value=2，reason 包含"PE处于近一年低位"、"ROE优秀"、"营收净利润双增长"
6. **Given** tr_yoy=-5% 且 netprofit_yoy=-8%，**When** 执行 `score_fundamental()`，**Then** value=-1（仅成长趋势规则触发），reason 包含"营收净利润双降"
7. **Given** 近 5 日主力净流入且大单买入强势，**When** 执行 `score_capital()`，**Then** value=2
8. **Given** `capital.insufficient=True`，**When** 执行 `score_capital()`，**Then** value=0，data_sufficient=False，reason="资金面数据不足"
9. **Given** 日线数据仅 30 行（MA60 不可用），**When** 执行 `score_technical()`，**Then** 跳过 MA 排列规则，data_sufficient=True，按 MACD + vol_ratio 评分
10. **Given** 日线数据仅 3 行，**When** 执行 `score_technical()`，**Then** value=0，data_sufficient=False，reason 包含"数据不足"
11. **Given** `technical_report.indicators`，**When** 检查键名，**Then** 包含 `ma5`/`ma20`/`ma60`/`macd_hist`/`macd_hist_prev`/`vol_ratio`/`pe_ttm`/`pe_percentile_1y`/`roe_yearly`/`tr_yoy`/`netprofit_yoy`/`net_mf_amount_5d`/`lg_buy_sell_ratio`
12. **Given** 修改配置文件中 ROE 阈值为 20%，**When** 重新执行评分，**Then** 原本 roe_yearly=16% 的股票不再触发"ROE优秀"

## 开放问题

| 问题 | 负责人 | 不解决的影响 |
|---|---|---|
| 配置文件格式选 YAML 还是 TOML？ | yanhe | 不影响功能，但需在开发前确定 |
| `pandas-ta` 是否与当前 Python 3.11 + pandas 2.x 兼容？ | yanhe | 如不兼容，需降级 pandas 或换用其他指标库 |

## 补充说明

- 系统设计文档：`docs/A股分析Agent系统设计.md`（完整指标体系 + 评分规则蓝图）
- 设计决策记录：`docs/设计决策.md`（决策 #7 三维评分、#8 pandas-ta）
- 编码规则：`docs/agent-harness/coding-rules.md`（评分和 LLM 边界的硬性规则）
- 规格细化：`team-spec/spec/refine/2026-05-30-market-analyzer-agent.md`
- 规格评审：`team-spec/spec/reviews/2026-05-30-market-analyzer-agent.md`
- 数据采集 PRD：`team-spec/prd/2026-05-29-data-collector-agent.md`（输入数据结构定义）
