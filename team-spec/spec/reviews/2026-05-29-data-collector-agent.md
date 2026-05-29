# 规格评审：数据采集 Agent（第二轮）

**Slug**: `2026-05-29-data-collector-agent`
**评审日期**: 2026-05-29
**Status**: ready

---

## 结论

上一轮 6 项评审问题（1×P1 + 4×P2 + 1×P3）全部已修正到位。无残留 P0/P1 阻塞项。规格可以进入 PRD 固化。最大剩余风险来自**数据存储**维度——`fundamental` 子结构内混合了日频和季频数据，需要在实现时处理。

---

## 上轮修正验证

| 上轮问题 | 修正状态 | 验证 |
|---|---|---|
| P1: `daily_basic` 归属 | ✅ 已移至 `fundamental` 子结构，`daily` 只保留 OHLCV | 接口映射表清晰，下游消费者标注明确 |
| P2: `raw_value` 定义 | ✅ 已定义为"首次获取时的完整 JSON 字符串" | 含使用场景说明（财报修正比对） |
| P2: 股票代码后缀 | ✅ 已按官方映射表补全（SH/SZ/BJ/HK） | 含补全逻辑和 Phase 边界 |
| P2: `moneyflow` 积分降级 | ✅ 已补充降级方案和置信度同步调整 | 错误处理表 + 验收标准 #8 双重覆盖 |
| P2: State 类型统一 | ✅ TypedDict + Pydantic BaseModel + `.model_dump()` | 代码示例清晰 |
| P3: 分段失败不落盘 | ✅ 已补充 | 分段拉取规则 + 错误处理表双重覆盖 |

---

## 阻塞项

无 P0 / P1。

---

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P2 | `fundamental` 子结构内混合频率数据 | `daily_basic` 是日频（~250 行/年），`fina_indicator`/`income` 是季频（~8 行）。存储为单一 `fundamental/600519.SH.parquet` 时，两种频率的 schema 不兼容（列不同、行数差 30 倍） | 实现时必须决定存储方式，否则 Parquet 写入失败或产生大量 null 列 | 规格存储路径为 `data/fundamental/600519.SH.parquet` 单文件，但未说明如何处理混合频率 | 建议在 PRD 中明确：`fundamental` 目录下按接口分子文件（如 `600519.SH_daily_basic.parquet`、`600519.SH_fina_indicator.parquet`、`600519.SH_income.parquet`），Pydantic 模型 `FundData` 包含三个独立的 DataFrame 字段。不阻塞当前规格 | yanhe | PRD 编写时 |
| P3 | `turnover_rate`（换手率）归属 | `turnover_rate` 来自 `daily_basic`，被归入 `fundamental`，但它更偏向技术面的成交量辅助指标 | 无功能影响，但后续 `score_technical()` 如需换手率数据，需从 `fundamental` 子结构中读取 | 下游评分函数尚未实现，无法确认 | 记录即可。如后续发现 `score_technical()` 需要换手率，可在评分函数中从 `raw_data.fundamental.daily_basic` 读取 | yanhe | 实现行情分析 Agent 时 |

---

## 需要补充的问题

无。

---

## Questions For User

不适用（Status: ready）。

---

## Required Refinement

不适用（Status: ready）。

---

## Change Log

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-05-29 | 第二轮评审 | 上轮 6 项全部修正到位，Status: ready。识别 1×P2（混合频率存储）+ 1×P3，均可在 PRD/实现中解决 |

---

## 下一步推荐

规格评审已完成，Status: ready。

下一步请使用 `team-spec-to-prd`，将通过评审的规格固化为 PRD。PRD 编写时注意处理 P2 风险：`fundamental` 目录下按接口分子文件存储混合频率数据。
