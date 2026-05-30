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

## Publish Status

- Status: created
- Updated At: 2026-05-30T04:15:21Z
- GitHub Number: 12
- GitHub URL: https://github.com/yanheng799/financial/issues/12

## Implementation Notes

### 变更文件

- `src/analyzer/indicators.py` — `compute_technical_indicators(daily_data)` 函数：用 pandas-ta-classic 计算 SMA5/20/60、MACD(12,26,9) 柱状图、vol_ratio
- `src/analyzer/scoring.py` — `score_technical(indicators, daily_count)` 函数：MA 排列 + MACD 柱 + 成交量修正，阈值从配置读取
- `tests/test_technical_scoring.py` — 13 个行为测试（指标计算 4 + 评分规则 4 + 成交量修正 2 + 降级 2 + 配置 1）

### 设计决策

- `compute_technical_indicators` 输入为 `list[dict]`（`raw_data.daily.data` 格式），内部转 DataFrame 升序计算后提取最新值
- pandas-ta-classic 在数据不足时返回 `None` 而非 NaN Series，`_last_value()` 处理了这种情况
- `score_technical` 接收 `daily_count` 参数用于降级判断，不依赖指标计算结果推断行数
- 成交量修正使用 `int(score * 0.5)` 取整，确保输出仍为整数

## Acceptance Criteria Coverage

| AC | 测试 | 状态 |
|---|---|---|
| AC#1 多头+MACD扩张+放量 → value=2 | `test_full_bullish_with_high_volume` | ✅ |
| AC#2 空头+MACD缩减 → value=-2 | `test_full_bearish` | ✅ |
| AC#3 多头但缩量 → 分数削弱 | `test_low_volume_weakens_score` | ✅ |
| AC#4 日线30行(无MA60) → 跳过MA排列 | `test_no_ma60_skips_ma_arrangement` | ✅ |
| AC#5 日线3行 → value=0, data_sufficient=False | `test_too_few_rows_returns_zero` | ✅ |
| AC#6 vol_ratio 阈值从配置读取 | `test_thresholds_match_config` | ✅ |
