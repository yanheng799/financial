# 规格评审：行情分析 Agent

**评审对象**：`team-spec/spec/refine/2026-05-30-market-analyzer-agent.md`
**评审日期**：2026-05-30
**Status**：ready

## 结论

P0（YoY 数据路径错误）和 P1（ROE 语义不匹配）已修正：成长趋势改用 `fina_indicator` 的 `tr_yoy`/`netprofit_yoy`，盈利能力改用 `roe_yearly`（年化）。剩余 P2/P3 风险不阻塞 PRD 固化。规格可以进入 `team-spec-to-prd`。

最大风险来自**数据与接口契约**维度。

## 阻塞项

| 等级 | 阻塞项 | 为什么阻塞 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|
| P0 | `revenue_yoy` / `netprofit_yoy` 数据路径错误 | 规格写"数据来源 `raw_data.fundamental.income`"，但 Tushare `income` 接口不返回这两个字段。它们实际在 `fina_indicator` 接口中，字段名为 `tr_yoy`（或 `or_yoy`）和 `netprofit_yoy`。按当前规格实现会导致运行时读不到字段，评分函数全部返回 0 | 修正 `score_fundamental()` 的数据来源为 `raw_data.fundamental.fina_indicator`，字段名改为 `tr_yoy`/`netprofit_yoy`；或改为从 `income` 的 `total_revenue`/`n_income` 手动计算同比 | yanhe | PRD 固化前 |
| P1 | ROE 字段语义不匹配 | 规格写"最新季 ROE > 15%"，但 `fina_indicator.ROE` 是报告期累计值（如 Q1 的 8% 不代表年化 8%）。15% 阈值隐含年化意图，但字段不是年化值 | 确认使用 `roe_yearly`（年化 ROE）还是 `roe`（累计 ROE），并调整阈值。推荐使用 `roe_yearly` + 15% 阈值 | yanhe | PRD 固化前 |

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P0 | YoY 字段数据路径错误 | 运行时读取 `income` 中的 `revenue_yoy` | 字段不存在，成长趋势评分始终为 0 | Tushare `income` 接口文档（doc_id=33）不包含 YoY 字段；`fina_indicator`（doc_id=79）包含 `tr_yoy`、`netprofit_yoy` | 见阻塞项 | yanhe | PRD 固化前 |
| P1 | ROE 累计 vs 年化 | 用累计 `roe` 与 15% 阈值比较 | Q1 报告的 `roe` 通常 3-8%，几乎不可能触发 15%，导致规则失效 | `fina_indicator` 同时返回 `roe`（累计）和 `roe_yearly`（年化） | 见阻塞项 | yanhe | PRD 固化前 |
| P2 | `vol` 单位文档错误 | `schemas.py` 注释"千手"，实际 Tushare 返回"手" | 不影响评分逻辑（vol_ratio 是比值，单位抵消），但误导维护者 | Tushare `daily` 文档（doc_id=27）标注 `vol` 单位为"手" | 修正 `schemas.py` 注释 | 实现时 | 无截止点 |
| P2 | `indicators` 字段无 schema | `TechnicalReport.indicators` 类型为 `dict`，无字段约束 | 下游策略决策 Agent 无法确定可引用哪些指标键名 | refine 规格描述了示例值但未定义完整字段列表 | PRD 中列出 `indicators` 的完整键名列表 | yanhe | PRD 编写时 |
| P2 | `pandas-ta` 兼容性 | `pandas-ta` 与 Python 3.11 + pandas 2.x 可能不兼容 | 阻塞指标计算 | 已在 refine 规格中标记 P1 | PRD 中将版本验证列为先决条件，开发初期首先验证 | yanhe | 开发启动时 |
| P3 | 数据采集 PRD 的 `income` 字段描述也有错误 | 数据采集 PRD FR-2 表格列出 `income` 接口字段包含 `revenue_yoy`、`netprofit_yoy` | 后续开发者参考 PRD 时被误导 | 数据采集 PRD 已关闭，影响只在此处 | 本期不修改已关闭 PRD，在本 PRD 中注明正确来源 | — | — |

## Questions For User

1. **YoY 数据来源选择**：`score_fundamental()` 的成长趋势规则，你希望：
   - (A) 从 `fina_indicator` 读取现成字段 `tr_yoy`（营业总收入同比）和 `netprofit_yoy`（归母净利润同比）
   - (B) 从 `income` 的 `total_revenue` 和 `n_income` 跨季度手动计算同比

   推荐 (A)，字段现成可用，无需手动计算。

2. **ROE 字段选择**：`score_fundamental()` 的盈利能力规则，你希望：
   - (A) 使用 `roe_yearly`（年化 ROE）+ 15%/3% 阈值
   - (B) 使用 `roe`（累计 ROE）+ 调低阈值（如 Q1 用 4%/0.5%，H1 用 8%/1%）
   - (C) 使用 `q_roe`（单季度 ROE）+ 调低阈值（如 5%/0.5%）

   推荐 (A)，年化值与阈值语义一致，跨报告期可比较。

## Required Refinement

需要更新 `team-spec/spec/refine/2026-05-30-market-analyzer-agent.md` 的以下章节：

1. **`score_fundamental()` 评分规则表**：
   - "数据来源"行：`revenue_yoy`/`netprofit_yoy` 的来源从 `income` 改为 `fina_indicator`（或确认手动计算方案）
   - "成长趋势"规则：字段名从 `revenue_yoy`/`netprofit_yoy` 改为 Tushare 实际字段名（如 `tr_yoy`/`netprofit_yoy`）
   - "盈利能力"规则：确认使用 `roe`、`roe_yearly` 还是 `q_roe`，必要时调整阈值

2. **`indicators` 示例**：更新字段名以匹配 Tushare 实际返回值

## 建议改写

### score_fundamental() 修正后版本（待用户确认后应用）

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

## Change Log

- 2026-05-30：初始评审。发现 P0 数据路径错误（YoY 字段来源）和 P1 ROE 语义不匹配。Status: needs refinement。
