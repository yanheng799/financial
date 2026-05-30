## Parent

PRD：行情分析 Agent (`team-spec/prd/2026-05-30-market-analyzer-agent.md`)

## What to build

实现基本面指标计算和 `score_fundamental()` 评分函数，从估值和财务数据产出基本面评分。

1. **指标计算**：在 `indicators.py` 中实现 `compute_fundamental_indicators(fundamental_data: dict) -> dict`，从 `daily_basic` 计算最新 PE_TTM 的近 1 年百分位排名，从 `fina_indicator` 提取最新季 `roe_yearly`、`tr_yoy`、`netprofit_yoy`
2. **评分函数**：在 `scoring.py` 中实现 `score_fundamental(indicators: dict) -> DimensionScore`，包含三条规则：估值位置（PE 分位数 ±1）、盈利能力（ROE 年化 ±1）、成长趋势（YoY 双向 ±1），最终 clamp 到 [-2, +2]
3. **降级处理**：PE_TTM 全空时跳过估值规则；无财报数据时返回 `value=0, data_sufficient=False`
4. **阈值可配置**：PE 分位数阈值（30/70）、ROE 阈值（15%/3%）、YoY 阈值（10%）从配置文件读取

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given PE_TTM 处于近 1 年 25% 分位且 roe_yearly=20% 且 tr_yoy=15% 且 netprofit_yoy=12%，When 执行 `score_fundamental()`，Then value=2，reason 包含"PE处于近一年低位"、"ROE优秀"、"营收净利润双增长"
- [ ] Given PE_TTM 处于近 1 年 80% 分位，When 执行 `score_fundamental()`，Then 估值规则得分=-1，reason 包含"PE处于近一年高位"
- [ ] Given tr_yoy=-5% 且 netprofit_yoy=-8%，When 执行 `score_fundamental()`，Then value=-1（仅成长趋势规则触发），reason 包含"营收净利润双降"
- [ ] Given PE_TTM 全部为空，When 执行 `score_fundamental()`，Then 估值规则跳过，data_sufficient=True，按 ROE + 成长打分
- [ ] Given 无财报数据（fina_indicator 为空），When 执行 `score_fundamental()`，Then value=0，data_sufficient=False，reason 包含"暂无财务数据"
- [ ] 所有阈值从配置文件读取，不硬编码

## Blocked by

- #1（Scaffolding, models, config, pandas-ta verification）

## Notes

- PE_TTM 分位数计算：取 `daily_basic` 中最近 1 年的 `pe_ttm` 值，计算最新值在其中的百分位排名
- `roe_yearly`、`tr_yoy`、`netprofit_yoy` 字段来自 `fina_indicator` 接口（非 `income` 接口），取最新季度记录
- `fina_indicator` 按 `end_date` 降序排列，第一条即最新季
- 基本面数据在 `FundData` 中以 `list[dict]` 存储，字段名取决于 Tushare 返回值
