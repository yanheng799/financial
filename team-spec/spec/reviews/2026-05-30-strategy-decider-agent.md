# 规格评审：策略决策 Agent（v2）

**评审对象**：`team-spec/spec/refine/2026-05-30-strategy-decider-agent.md`（第二轮修订）
**评审日期**：2026-05-30
**Status**：ready

## 结论

v2 规格已与实现对齐，无 P0 阻塞项。LLMOutput/DecisionReport 分离、7 字段代码注入、error 字段的引入消除了 v1 评审中 P0（置信度冲突）和多项 P1（auto_approve 传递、置信度缩维规则缺失）的残留风险。LLM 格式不稳定风险从 P1 降为 P2（5 字段 vs 原 12 字段，确定性字段不受 LLM 幻觉影响）。v2 可以进入 PRD 刷新或直接跳过 PRD 固化（因为 v1 PRD 已存在且变更已有 issue 覆盖）。

## 阻塞项

无。

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P2 | LLM API 401/403 错误类型与规格不一致 | LLM key 无效或过期，API 返回 401/403 | `error_type` 为 `"llm_call"` 而非 `"config"` | 规格写 `error_type: "config"`，代码在 `except Exception` 中返回 `error_type: "llm_call"` | 统一到 `error_type: "config"`（语义更精确），或规格改为 `error_type: "llm_call"` 并注释说明 | yanhe | PRD 刷新时 |
| P2 | `auto_approve` 拒绝后 Streamlit 如何消费 `error` 字段未定义 | Streamlit 读取 `state["decision_report"]` 但发现为空 | 用户看到空白或无提示的失败 | Streamlit UI 不在 Phase 1 范围（`auto_approve=True` 绕过）。`error` 字段已存在供下游消费 | Streamlit 实现时检查 `error` 字段并展示 | yanhe | Streamlit 开发时 |
| P2 | `indicators` 截断策略未实现 | Phase 2 加情绪面指标后 key_indicators 增长 | prompt token 超 model 限制 | 当前 12 个精选指标约 500-800 token，安全边际充足 | Phase 2 新增指标时评估是否需要截断 | yanhe | Phase 2 |
| P3 | `LLMOutput` 和 `DecisionReport` 共享 `overall_judgment` 枚举导致重复定义 | 两个类维护相同的 Literal | 增删枚举值时需同步修改两处 | 当前代码中两处枚举值相同 | 可用常量提取：`OVERALL_JUDGMENT_VALUES = Literal["乐观", "中性", ...]` | yanhe | 下次重构 |
| P3 | `scores` 维度顺序回填时不保证与输入一致 | `scores` 是 dict，Python 3.7+ 保证插入顺序 | LLM 输出回填的 scores 键顺序与输入一致 | Python 3.11 dict order-preserving | 现有行为已正确，无需修改 | — | — |

## Questions For User

无（v2 已与实现对齐，无需回到 refine）。

## 建议改写

### 1. `error_type` 分类统一（P2）

当前规格表和代码存在轻微不一致。建议在 PRD 中明确三层错误分类：

| 错误层 | `error_type` | 触发条件 | 重试 |
|---|---|---|---|
| 配置 | `"config"` | API key 缺失、配置文件缺失、LLM 401/403 | 不重试 |
| 网络 | `"llm_call"` | 超时、HTTP 5xx、429 耗尽 | SDK 层已重试 |
| 解析 | `"llm_parse_error"` | 非 JSON、LLMOutput schema 失败 | 应用层重试 1 次 |
| 输入 | `"input"` | technical_report 为空、scores 全 insufficient | 不重试 |
| 审批 | `"human_review"` | 用户拒绝 | 不重试 |

### 2. 范围章节补充

v2 新增的以下项应在"范围内"章节显式列出：
- `LLMOutput` 模型（5 字段）+ `DecisionReport` 模型（12 字段）分离
- `detect_conflict()` / `build_data_sources()` 代码函数
- `AnalysisState.error` 字段
- `DIM_SOURCES` 外置 + 维度动态遍历
- `request_timeout` 配置

## Change Log

- 2026-05-30（v1）：初始评审。发现 P0（LLM prompt 置信度冲突）和 P1（缩维规则缺失）。Status: needs refinement。
- 2026-05-30（v2）：第二次评审。v1 P0/P1 已全部解决（#35–#38 实现）。v2 规格完全对齐实现。Status: ready。
