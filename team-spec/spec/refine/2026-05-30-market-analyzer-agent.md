# 规格细化：行情分析 Agent

## 需求摘要

行情分析 Agent 作为 LangGraph `market_analyzer` 节点，从 `AnalysisState.raw_data` 读取数据采集 Agent 产出的三维原始数据（日线、财务、资金流），纯代码计算技术指标和三维评分（技术面、基本面、资金面），输出 `TechnicalReport` 到 `AnalysisState.technical_report`，供下游策略决策 Agent 消费。

## 规范术语

| 术语 | 定义 |
|---|---|
| `market_analyzer` | LangGraph 节点名，行情分析 Agent |
| `score_technical()` | 技术面评分函数：MA 排列 + MACD 柱 + 成交量修正，输出 -2~+2 |
| `score_fundamental()` | 基本面评分函数：PE 位置 + ROE + 成长趋势，输出 -2~+2 |
| `score_capital()` | 资金面评分函数：主力方向 + 大单强弱，输出 -2~+2 |
| `DimensionScore` | 单维度评分结构（value/reason/data_sufficient） |
| `TechnicalReport` | 节点输出 Pydantic 模型（scores + indicators + metadata） |
| 评分阈值 | 评分函数中的数值阈值（如 ROE 15%、PE 30/70 分位），放配置文件 |
| 降级不阻塞 | 部分规则跳过仍可打分，维度数据缺失才归零 |

## 范围

### 范围内

- 三个评分函数 `score_technical/fundamental/capital`
- 技术指标计算：MA（5/20/60）、MACD（12/26/9）、成交量均量比（20 日）
- 基本面指标计算：PE_TTM 近 1 年分位数、最新季年化 ROE（`roe_yearly`）、营收/净利润同比（`tr_yoy`/`netprofit_yoy`，来自 `fina_indicator`）
- 资金面指标计算：近 5 日主力净流入/流出、大单买卖比率
- 阈值配置文件（YAML 或 TOML）
- LangGraph `market_analyzer` 节点函数 + StateGraph 集成
- Pydantic 输出模型 `TechnicalReport`、`DimensionScore`
- 数据不足时的降级处理

### 范围外

- LLM 调用（策略决策 Agent 职责）
- `human_review` 节点（后续 PRD 实现）
- Phase 2 指标（KDJ、BOLL、RSI、ATR）
- 情绪面维度
- Streamlit 展示
- 评分阈值的自动调优

## 评分规则

### score_technical()

数据来源：`raw_data.daily`（OHLCV）

| 规则 | 条件 | 得分 | reason |
|---|---|---|---|
| MA 排列 | MA5 > MA20 > MA60 | +1 | "均线多头排列" |
| | MA5 < MA20 < MA60 | -1 | "均线空头排列" |
| MACD 柱 | macd_hist > 0 且 macd_hist > macd_hist_prev | +1 | "MACD柱扩张" |
| | macd_hist < 0 且 macd_hist < macd_hist_prev | -1 | "MACD柱缩减" |
| 成交量修正 | vol_ratio > 1.5 | 不变 | 放量确认信号 |
| | vol_ratio < 0.7 | score *= 0.5 | 缩量削弱信号 |

最终 clamp 到 [-2, +2]。

### score_fundamental()

数据来源：`raw_data.fundamental`（daily_basic / fina_indicator）

| 规则 | 条件 | 得分 | reason |
|---|---|---|---|
| 估值位置 | 最新 PE_TTM < 近 1 年 30% 分位 | +1 | "PE处于近一年低位" |
| | 最新 PE_TTM > 近 1 年 70% 分位 | -1 | "PE处于近一年高位" |
| 盈利能力 | 最新季 `roe_yearly` > 15% | +1 | "ROE优秀(>15%)" |
| | 最新季 `roe_yearly` < 3% | -1 | "ROE偏低(<3%)" |
| 成长趋势 | `tr_yoy` > 10% 且 `netprofit_yoy` > 10% | +1 | "营收净利润双增长" |
| | `tr_yoy` < 0 且 `netprofit_yoy` < 0 | -1 | "营收净利润双降" |

最终 clamp 到 [-2, +2]。

### score_capital()

数据来源：`raw_data.capital`（moneyflow）

| 规则 | 条件 | 得分 | reason |
|---|---|---|---|
| 主力方向 | 近 5 日 net_mf_amount 合计 > 0 | +1 | "近5日主力净流入" |
| | 近 5 日 net_mf_amount 合计 < 0 | -1 | "近5日主力净流出" |
| 大单强弱 | 最近 1 日 buy_lg_amount / sell_lg_amount > 1.5 | +1 | "大单买入强势" |
| | 最近 1 日 buy_lg_amount / sell_lg_amount < 0.67 | -1 | "大单卖出强势" |

最终 clamp 到 [-2, +2]。若 `capital.insufficient == True`，返回 `score=0, reason="资金面数据不足"`。

## 阈值可配置

评分函数中的数值阈值（如 ROE 15%/3%、PE 30%/70% 分位、大单比率 1.5/0.67、vol_ratio 1.5/0.7）提取到配置文件（YAML 或 TOML），函数运行时读取。规则结构（用哪些字段、几条规则、怎么组合）硬编码在函数内。Tushare 字段名（如 `roe_yearly`、`tr_yoy`、`netprofit_yoy`）硬编码在函数内，不暴露到配置文件。

## 输出结构

```python
class DimensionScore(BaseModel):
    value: int                  # -2 ~ +2
    reason: str                 # "均线多头排列；MACD柱扩张"
    data_sufficient: bool       # 维度数据是否充足

class TechnicalReport(BaseModel):
    symbol: str                 # "600519.SH"
    date: str                   # "20260530"
    scores: dict[str, DimensionScore]  # technical / fundamental / capital
    indicators: dict            # 关键指标值（供 LLM 引用）
    generated_at: str           # ISO 8601
```

`scores` 使用 `dict[str, DimensionScore]` 而非三个独立字段，Phase 2 加情绪面维度只需新增 key。

`indicators` 包含所有计算的派生指标（MA、MACD、vol_ratio、PE 分位数、ROE、YoY、资金流数据），供策略决策 Agent 的 LLM prompt 引用。

## 降级策略

按维度独立降级，不做全有全无的二元判断。

| 场景 | 处理方式 | `data_sufficient` |
|---|---|---|
| 日线 < 60 天（MA60 算不出） | 只算能算的指标，跳过依赖缺失数据的规则 | `True` |
| 日线 < 5 天 | `score=0, reason="日线数据不足，无法计算技术指标"` | `False` |
| PE_TTM 全空 | 估值规则跳过，只按 ROE + 成长打分 | `True` |
| 无财报数据（新股） | `score=0, reason="暂无财务数据"` | `False` |
| 资金面积分不足 | `score=0, reason="资金面数据不足"` | `False` |

核心原则：一个维度内部分规则可跳过（降级但不报错），整个维度数据缺失时才标记 `data_sufficient=False` 并归零。

## 已关闭的开放问题

- `turnover_rate`（换手率）不被 `score_technical()` 使用。技术面评分的成交量指标是 `vol_ratio`（当日成交量 / 20 日均量），直接从 `daily.vol` 字段计算。

## 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| `pandas-ta` 与 Python 3.11 / pandas 2.x 兼容性 | P1 | PRD 中写明版本验证为先决条件 |
| 评分阈值初始值靠经验，可能需要多轮调优 | P2 | 可配置化已覆盖，调优不改代码 |

## Change Log

- 2026-05-30：初始细化。确认三维评分规则、输出 schema、降级策略、阈值可配置方向。
- 2026-05-30：评审后修正——成长趋势字段从 `income` 的 `revenue_yoy`/`netprofit_yoy` 改为 `fina_indicator` 的 `tr_yoy`/`netprofit_yoy`；ROE 字段从累计 `roe` 改为年化 `roe_yearly`。
