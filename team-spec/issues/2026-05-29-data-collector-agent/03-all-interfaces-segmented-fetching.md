## Parent

PRD：数据采集 Agent (`team-spec/prd/2026-05-29-data-collector-agent.md`)

## What to build

在 #2 跑通的 `daily` 接口基础上，扩展到全部 5 个 Tushare 接口，并加入分段拉取和降级处理。

1. **新增 4 个接口**：在 `TushareAdapter` 中实现 `fetch_daily_basic()`（日频估值）、`fetch_fina_indicator()`（季频质量指标）、`fetch_income()`（季频营收利润）、`fetch_moneyflow()`（日频资金流），每个接口复用 #2 建立的校验+可追溯性流程
2. **各接口时间范围**：daily_basic 近 1 年、fina_indicator 近 8 季度、income 近 8 季度、moneyflow 近 1 个月
3. **分段拉取**：对 `daily` 和 `daily_basic`（时间跨度 1 年）按半年分段拉取，每次 6 个月，分段后合并、去重、排序。分段部分失败时不返回数据，报错说明哪段失败
4. **moneyflow 降级**：`moneyflow` 接口返回权限/积分不足错误时，不阻塞其他维度，`CapitalFlowData.insufficient` 设为 `True`，`data` 设为 `None`
5. **组合采集**：实现 `fetch_all()` 方法，一次调用拉取全部 5 个接口，返回 `RawData` 对象

完成后，给定股票代码，能一次性拿到覆盖三维评分所需的全部原始数据。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given 有效股票代码，When 调用 `fetch_all("600519.SH")`，Then 返回 `RawData`，其中 `daily`、`fundamental.daily_basic`、`fundamental.fina_indicator`、`fundamental.income` 四项均有数据
- [ ] Given `moneyflow` 接口返回权限错误，When 调用 `fetch_all()`，Then `daily`/`fundamental` 正常返回，`capital.insufficient=True`，`capital.data=None`
- [ ] Given 日线分段拉取第 2 段失败，When 调用 `fetch_daily()`，Then 返回错误说明第 2 段失败，不返回部分数据
- [ ] Given `fina_indicator` 返回 8 个季度数据，When 校验完成，Then 按 `end_date` 降序排列，无重复
- [ ] 自动化测试：mock 4 个新接口的返回值，验证各接口数据正确映射到 `RawData` 对应字段

## Blocked by

- #2（daily 接口端到端链路已跑通）

## Notes

- `daily_basic` 和 `daily` 同为日频且时间范围一致（近 1 年），分段策略一致（按半年分段），实现时可共享分段拉取逻辑。
- `fina_indicator` 和 `income` 是季频接口，数据量小（~8 行），不需要分段。
- Tushare `vol` 字段单位为千手，在 Pydantic schema 中标注但不转换值。

## Publish Status

- Status: created
- Updated At: 2026-05-29T14:40:32Z
- GitHub Number: 3
- GitHub URL: https://github.com/yanheng799/financial/issues/3
