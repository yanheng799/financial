## Parent

PRD：行情分析 Agent (`team-spec/prd/2026-05-30-market-analyzer-agent.md`)

## What to build

实现资金面指标计算和 `score_capital()` 评分函数，从资金流数据产出资金面评分。

1. **指标计算**：在 `indicators.py` 中实现 `compute_capital_indicators(capital_data: dict) -> dict`，计算近 N 日（默认 5 日）`net_mf_amount` 合计值、最近 1 日 `buy_lg_amount / sell_lg_amount` 比率
2. **评分函数**：在 `scoring.py` 中实现 `score_capital(indicators: dict, insufficient: bool) -> DimensionScore`，包含两条规则：主力方向（±1）、大单强弱（±1），最终 clamp 到 [-2, +2]
3. **降级处理**：`insufficient=True` 时直接返回 `value=0, reason="资金面数据不足", data_sufficient=False`；数据行数不足回看天数时跳过对应规则
4. **阈值可配置**：回看天数（5）、大单比率阈值（1.5/0.67）从配置文件读取

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 近 5 日净流入且大单买入强势（比率 > 1.5），When 执行 `score_capital()`，Then value=2，reason 包含"近5日主力净流入"和"大单买入强势"
- [ ] Given 近 5 日净流出且大单卖出强势（比率 < 0.67），When 执行 `score_capital()`，Then value=-2，reason 包含"近5日主力净流出"和"大单卖出强势"
- [ ] Given `insufficient=True`，When 执行 `score_capital()`，Then value=0，data_sufficient=False，reason="资金面数据不足"
- [ ] Given 资金流数据仅 2 行（不足 5 日回看），When 执行 `score_capital()`，Then 按实际可用数据计算，data_sufficient=True
- [ ] Given 资金流数据为空（非 insufficient），When 执行 `score_capital()`，Then value=0，data_sufficient=False
- [ ] 所有阈值从配置文件读取，不硬编码

## Blocked by

- #1（Scaffolding, models, config, pandas-ta verification）

## Notes

- `capital.data` 已按 `trade_date` 降序排列（数据采集 Agent 保证），第一条即最近 1 日
- `net_mf_amount` 和 `buy_lg_amount`/`sell_lg_amount` 单位为万元（Tushare 返回值），计算比率时单位抵消
- `insufficient` 标记由数据采集 Agent 设置（`CapitalFlowData.insufficient`），本函数直接读取
