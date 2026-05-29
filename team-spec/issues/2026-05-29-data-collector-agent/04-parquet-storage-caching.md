## Parent

PRD：数据采集 Agent (`team-spec/prd/2026-05-29-data-collector-agent.md`)

## What to build

在 #3 完成全部 5 个接口采集的基础上，实现 Parquet 文件落盘和本地缓存策略。

1. **Parquet 写入**：在 `src/collector/storage.py` 中实现存储逻辑，按 PRD 规定的目录结构落盘：
   - `data/daily/{ts_code}.parquet` — daily 接口
   - `data/fundamental/{ts_code}_daily_basic.parquet` — 日频估值
   - `data/fundamental/{ts_code}_fina_indicator.parquet` — 季频质量指标
   - `data/fundamental/{ts_code}_income.parquet` — 季频营收利润
   - `data/capital/{ts_code}.parquet` — 资金流
2. **Parquet 读取**：从本地文件读取数据，反序列化为 `RawData` 对象
3. **本地优先策略**：`fetch_all()` 先检查本地是否已有全部 5 个维度的 Parquet 文件，若有则直接读取返回，不调 Tushare API
4. **手动刷新**：`fetch_all(force_refresh=True)` 时忽略本地缓存，调 API 全量重拉并覆盖文件
5. **完整性保护**：分段拉取失败时不落盘（#3 已保证），确保本地 Parquet 要么完整要么不存在

完成后，整个数据采集 Agent 具备持久化和缓存能力，重复分析同一只股票时不再调 API。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 本地无数据，When 调用 `fetch_all("600519.SH")`，Then 调 Tushare API 拉取数据，`data/` 下生成 5 个 Parquet 文件（含 fundamental 下 3 个子文件）
- [ ] Given 本地已有 `600519.SH` 的全部 Parquet 文件，When 再次调用 `fetch_all("600519.SH")`，Then 直接读取本地文件，无 Tushare API 调用
- [ ] Given 本地已有数据，When 调用 `fetch_all("600519.SH", force_refresh=True)`，Then 调 Tushare API 全量重拉并覆盖本地文件
- [ ] Given 每个 Parquet 文件，When 用 Pandas 读取检查列，Then 包含 `source`、`fetched_at`、`raw_value` 三列
- [ ] Given `capital` 维度因积分不足无数据，When 落盘，Then `data/capital/` 目录下无该股票的 Parquet 文件（空数据不写空文件）
- [ ] 自动化测试：mock 文件系统，验证"有文件→跳过 API""无文件→调 API""force_refresh→覆盖"三条路径

## Blocked by

- #3（全部 5 个接口采集逻辑已完成）

## Notes

- `fundamental` 维度按接口拆分为 3 个子文件（daily_basic/fina_indicator/income），因为日频和季频 schema 不兼容。
- 缓存判断逻辑：检查所有必要的 Parquet 文件是否存在。如果部分存在（如只有 daily 没有 fundamental），视为缓存不完整，按缺失维度调 API 补齐。
- 目录不存在时自动创建（`data/daily/`、`data/fundamental/`、`data/capital/`）。

## Publish Status

- Status: created
- Updated At: 2026-05-29T14:40:34Z
- GitHub Number: 4
- GitHub URL: https://github.com/yanheng799/financial/issues/4
