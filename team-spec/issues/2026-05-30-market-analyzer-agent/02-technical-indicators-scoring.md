## Parent

PRD：行情分析 Agent (`team-spec/prd/2026-05-30-market-analyzer-agent.md`)

## What to build

实现技术指标计算和 `score_technical()` 评分函数，从 OHLCV 日线数据产出技术面评分。

1. **指标计算**：在 `indicators.py` 中实现 `compute_technical_indicators(daily_data: list[dict]) -> dict`，使用 `pandas-ta` 计算 MA5/MA20/MA60、MACD(12,26,9) 柱状图（当日和前一日）、vol_ratio（当日 vol / 20 日均值）
2. **评分函数**：在 `scoring.py` 中实现 `score_technical(indicators: dict) -> DimensionScore`，包含三条规则：MA 排列（±1）、MACD 柱方向（±1）、成交量修正（放量不变 / 缩量 × 0.5），最终 clamp 到 [-2, +2]
3. **降级处理**：日线 < 60 天时跳过 MA 排列规则；日线 < 5 天时返回 `value=0, data_sufficient=False`
4. **阈值可配置**：vol_ratio 阈值（1.5/0.7）从配置文件读取

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given MA5 > MA20 > MA60 且 MACD 柱扩张且 vol_ratio > 1.5，When 执行 `score_technical()`，Then value=2，reason 包含"均线多头排列"和"MACD柱扩张"
- [ ] Given MA5 < MA20 < MA60 且 MACD 柱缩减，When 执行 `score_technical()`，Then value=-2，reason 包含"均线空头排列"和"MACD柱缩减"
- [ ] Given 多头排列但 vol_ratio < 0.7，When 执行 `score_technical()`，Then 分数被削弱（取 score × 0.5 的整数部分）
- [ ] Given 日线仅 30 行（MA60 不可用），When 执行 `score_technical()`，Then 跳过 MA 排列规则，data_sufficient=True
- [ ] Given 日线仅 3 行，When 执行 `score_technical()`，Then value=0，data_sufficient=False，reason 包含"数据不足"
- [ ] 所有 vol_ratio 阈值从配置文件读取，不硬编码

## Blocked by

- #1（Scaffolding, models, config, pandas-ta verification）

## Notes

- MA 计算用 `pandas-ta` 的 `ta.sma()`；MACD 用 `ta.macd()`
- vol_ratio 手动计算（当日 vol / 近 20 日 vol 均值），不用 pandas-ta
- 成交量修正的 `score *= 0.5` 后需取整（`int()`），确保输出仍为整数
- 指标计算的输入是 `raw_data.daily.data`（list[dict]），需先转为 DataFrame
