## Parent

PRD：数据采集 Agent (`team-spec/prd/2026-05-29-data-collector-agent.md`)

## What to build

用 `daily` 接口跑通"Tushare API 调用 → Pydantic 校验 → 附加可追溯性字段"全链路，作为数据采集 Agent 的第一个端到端切片。

具体实现 `src/collector/adapter.py` 中的 `TushareAdapter` 类：

1. **Token 初始化**：从 `TUSHARE_TOKEN` 环境变量读取 Token，初始化 `ts.pro_api()`；Token 缺失时给出配置指引
2. **API 调用**：调用 `pro.daily()` 拉取日线 OHLCV 数据，时间范围默认近 1 年
3. **Pydantic 校验**：将 Tushare 返回的 DataFrame 转为字典列表，用 `DailyQuoteData` 校验（关键字段存在性、类型检查）
4. **可追溯性标注**：对每行数据附加 `source`（`"tushare:daily"`）、`fetched_at`（当前 ISO 8601 时间戳）、`raw_value`（该行完整 JSON 字符串）
5. **去重排序**：按 `ts_code + trade_date` 去重，按 `trade_date` 降序排序
6. **时间范围计算**：实现工具函数，根据"近 N 年/N 季度/N 交易日"计算 start_date/end_date（YYYYMMDD 格式）

完成后，给定一个有效股票代码，能通过 `TushareAdapter` 拿到校验后的日线数据。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given `TUSHARE_TOKEN` 已配置且有效，When 调用 `TushareAdapter.fetch_daily("600519.SH")`，Then 返回 `DailyQuoteData`，包含近 1 年日线数据
- [ ] Given `TUSHARE_TOKEN` 未配置，When 初始化 `TushareAdapter`，Then 抛出明确错误并给出 `export TUSHARE_TOKEN=...` 配置指引
- [ ] Given 返回的任意一行数据，When 检查字段，Then 包含 `source="tushare:daily"`、`fetched_at`（ISO 8601 格式）、`raw_value`（JSON 字符串）
- [ ] Given Tushare 返回含重复 `trade_date` 的数据，When 校验完成，Then 已按 `ts_code + trade_date` 去重
- [ ] Given 校验完成的数据，When 检查排序，Then 按 `trade_date` 降序（最新在前）
- [ ] 自动化测试：mock Tushare API 返回缺失 `close` 字段的数据，Then Pydantic 校验拦截并报错

## Blocked by

- #1（项目骨架、Pydantic 模型、代码解析器）

## Notes

- 本 issue 只实现 `daily` 一个接口。其余 4 个接口在 #3 中加入，模式完全一致。
- 暂不实现分段拉取（#3 加入）、暂不实现 Parquet 落盘（#4 加入）。
- 可用 `.agents/skills/tushare/scripts/stock_data_demo.py` 中的 API 调用模式作为参考。

## Implementation Notes

- 实现日期：2026-05-30
- 修改文件：
  - `src/collector/adapter.py` — `TushareAdapter` 类 + `calc_date_range()` 工具函数
  - `src/collector/schemas.py` — 新增 `DailyQuoteRow` 行级校验模型，`DailyQuoteData.data` 类型从 `list[dict]` 升级为 `list[DailyQuoteRow]`，新增 `ConfigDict(extra="allow")` 保留 Tushare 返回的额外字段
  - `tests/test_adapter_daily.py` — 13 个新测试用例
  - `tests/test_scaffolding.py` — 更新 `test_daily_quote_data_creation` 以适配新的 `DailyQuoteRow` 必填字段
- `DailyQuoteRow` 的 `extra="allow"` 确保额外字段（如 `pre_close`、`change`、`pct_chg`）不会被丢弃
- `calc_date_range()` 按 365 天/年、90 天/季度近似计算，后续如需精确可引入 `dateutil`

## Acceptance Criteria Coverage

- [x] Given `TUSHARE_TOKEN` 已配置且有效，When 调用 `fetch_daily("600519.SH")`，Then 返回 `DailyQuoteData` — `test_returns_daily_quote_data`
- [x] Given `TUSHARE_TOKEN` 未配置，When 初始化 `TushareAdapter`，Then 抛出明确错误 — `test_token_missing_raises_with_guidance`
- [x] Given 返回的任意一行数据，When 检查字段，Then 包含 `source`/`fetched_at`/`raw_value` — `test_traceability_fields_present`
- [x] Given Tushare 返回含重复 `trade_date` 的数据，When 校验完成，Then 已按 `ts_code + trade_date` 去重 — `test_deduplicates_by_ts_code_and_trade_date`
- [x] Given 校验完成的数据，When 检查排序，Then 按 `trade_date` 降序 — `test_sorted_by_trade_date_descending`
- [x] 自动化测试：mock Tushare API 返回缺失 `close` 字段的数据，Then Pydantic 校验拦截并报错 — `test_rejects_missing_close_field`

## Verification

- `pytest tests/` — 33 passed（20 scaffolding + 13 adapter daily）
- `ruff check src/ tests/` — All checks passed
- `ruff format --check src/ tests/` — 8 files already formatted

## Publish Status

- Status: created
- Updated At: 2026-05-29T14:40:31Z
- GitHub Number: 2
- GitHub URL: https://github.com/yanheng799/financial/issues/2
