# PRD：策略决策 Agent（v2）

## 问题陈述

数据采集 Agent 和行情分析 Agent 已实现，能产出原始数据（`RawData`）和三维结构化评分（`TechnicalReport`）。但这些评分是独立的数字——技术面 +1、基本面 +1、资金面 -1——用户无法直接从中得出投资结论。系统需要一个 LLM 驱动的推理层：接收纯代码计算的评分和指标，进行交叉分析（哪两个维度冲突？哪个维度权重更大？），输出包含综合判断、风险提示和强制反向因素的研判报告。

## 目标

- 实现策略决策 Agent（`human_review` + `strategy_decider` 两个 LangGraph 节点），作为四 Agent 流水线的第三个环节
- LLM 只输出 5 个推理字段，其余 7 个确定性字段全部由代码注入
- 置信度与冲突检测由代码计算，不依赖 LLM 主观判断
- 预留 `human_review` 人工审批节点，`auto_approve` 开关控制是否中断；拒绝时返回结构化错误
- 结构化错误通过 `AnalysisState.error` 字段传递给下游

## 非目标

- Streamlit UI（`human_review` 的审批交互界面单独实现）
- LLM 提示词优化/tuning
- 情绪面评分维度（Phase 2，output schema 预留字段）
- `human_review` 的 checkpointer 持久化策略
- 多 LLM provider 的自动 fallback
- 模型输出质量评估/RLHF

## 用户与场景

1. 作为个人投资者，我希望系统对三个维度的评分进行交叉分析，给出综合判断（乐观/中性/谨慎），以便我无需自己权衡矛盾信号。
2. 作为个人投资者，我希望系统强制输出一条反向风险因素（bearish factor），即使当前总体看多，也要提醒我可能的风险，以便我避免确认偏误。
3. 作为个人投资者，我希望看到各维度数据来源和置信度标注，以便我知道哪些结论有数据支撑、哪些是推测。
4. 作为个人投资者，我希望在验证期间，能先看到三维评分和指标，确认后再进入 LLM 综合推理，以便发现评分逻辑异常时及时中断。
5. 作为个人投资者，当我不批准分析时，系统应给出明确的拒绝提示（通过 `error` 字段），以便我知道为什么没有生成研判报告。

## 当前状态

- 数据采集 Agent 已实现（`src/collector/`）
- 行情分析 Agent 已实现（`src/analyzer/`）
- 策略决策 Agent 已完全实现（`src/strategist/`），含 #21–#27、#35–#38 全部 issue
- `AnalysisState` 包含 `symbol`, `raw_data`, `technical_report`, `decision_report`, `human_approved`, `error` 六个字段
- 测试覆盖 229 项，全部通过

## 方案描述

策略决策 Agent 作为 LangGraph 流水线的两个连续节点运行：

```
market_analyzer → human_review → strategy_decider
                    │                  │
              human_approved     decision_report
              (auto_approve 开关)   (12 字段：5 LLM + 7 代码注入)
              │
              └── human_approved=False → END + error
```

### human_review 节点

- 读取 `configs/llm.yaml` 的 `auto_approve` 开关
- `auto_approve=True`：直接返回 `{"human_approved": True}`，不中断
- `auto_approve=False` 且 `state["human_approved"]` 已为 `False`：返回 `{"human_approved": False, "error": {"error_type": "human_review", "message": "用户未批准，跳过策略分析"}}` → 条件边路由到 `END`
- `auto_approve=False` 且未审批：调用 `interrupt("请确认 technical_report，批准后继续")`，等待用户在 Streamlit 批准后 resume

### strategy_decider 节点

1. 从 `state["technical_report"]` 读取评分、指标、symbol、date
2. 代码计算 7 个确定性字段：`confidence_level`（`compute_confidence`）、`conflict_detected`（`detect_conflict`，零值不算方向）、`data_sources`（`build_data_sources`，只含 sufficient 维度）、`generated_at`（`datetime.now().isoformat()`）、`symbol`、`date`、`scores`（`to_score_entry` 映射）
3. 构造 LLM prompt：上下文（评分摘要 + 关键指标 + 最大分差）+ JSON 模板（只要求 5 个推理字段）+ 约束规则
4. 调用 LangChain ChatOpenAI（SDK 层 `max_retries=2` 处理网络/429，`request_timeout=300` 秒）
5. Pydantic `LLMOutput`（5 字段）校验 → 失败则应用层重试 1 次
6. 合并 LLM 5 字段 + 代码 7 字段 → `DecisionReport.model_validate()` → 写入 `state["decision_report"]`

**重试分工**：SDK 层处理网络/超时/429（最多 3 次调用），应用层处理 JSON 解析/校验失败（最多 2 次调用），两类互不交叉。

## 范围

### 范围内

- `human_review` 节点函数（含 `auto_approve` 开关 + 拒绝分支）
- `strategy_decider` 节点函数（LLM prompt 构造 + LLM 调用 + `LLMOutput` 校验 + 7 字段代码注入 + `DecisionReport` 组装）
- Pydantic 模型 `LLMOutput`（5 字段）+ `DecisionReport`（12 字段）
- `compute_confidence()` / `detect_conflict()` / `build_data_sources()` 代码函数
- `AnalysisState.error` 字段（`NotRequired[dict]`）
- `configs/llm.yaml` 配置文件（含 `request_timeout`）
- `DIM_SOURCES` 外置 + 维度动态遍历
- 结构化错误返回（`config` / `llm_call` / `llm_parse_error` / `input` / `human_review`）
- StateGraph 构建函数 `build_strategist_graph()`

### 范围外

- Streamlit UI
- LLM 提示词优化/tuning
- 情绪面评分（Phase 2，字段预留 `"deferred"`）
- `human_review` 的 checkpointer 持久化
- 多 LLM provider 自动 fallback

## 功能需求

### FR-1：LLM 配置

1. 系统必须从 `configs/llm.yaml` 读取配置（provider、model、base_url、api_key_env、temperature、max_tokens、request_timeout、auto_approve）
2. 系统必须支持 DeepSeek 和 Qwen 切换，只改配置文件
3. `api_key` 只能从配置文件指定的环境变量读取，不得写入配置文件或代码
4. `request_timeout` 默认 300 秒，传入 `ChatOpenAI(request_timeout=...)`

### FR-2：human_review 节点

5. 系统必须实现 `human_review_agent(state: AnalysisState) -> dict` 节点函数
6. 当 `auto_approve=True` 时，自动设置 `human_approved=True` 并返回
7. 当 `auto_approve=False` 且 `state["human_approved"]` 为 `False` 时，返回拒绝 error（`error_type: "human_review"`）
8. 当 `auto_approve=False` 且 `human_approved` 未设置时，调用 `interrupt()` 暂停执行

### FR-3：置信度与冲突检测（代码）

9. 系统必须实现 `compute_confidence(scores) -> Literal["高", "中", "低"]` 函数

| 有效维度数 | 置信度 | 条件 |
|---|---|---|
| 3 | 高 | 3 维方向一致（同正/同负/同零） |
| 3 | 中 | 2 维方向一致 |
| 3 | 低 | 3 维各不相同，或任意两维得分差 ≥ 2 |
| 2 | 高 | 2 维方向一致 |
| 2 | 低 | 2 维方向不一致 |
| 1 | 低 | 仅 1 维有效 |
| 0 | N/A | 不执行 LLM，返回错误 |

10. 系统必须实现 `detect_conflict(scores) -> bool` 函数：既有正分又有负分 → True。零值不算方向。`data_sufficient=False` 的维度不参与
11. `conflict_detected` 字段必须由代码注入，非 LLM 输出

### FR-4：strategy_decider 节点

12. 系统必须实现 `strategy_decider_agent(state: AnalysisState) -> dict` 节点函数
13. 系统必须从 `state["technical_report"]` 读取 `scores`、`indicators`、`symbol`、`date`
14. LLM prompt 只要求 LLM 输出 5 个推理字段：`conflict_detail`、`overall_judgment`、`key_driver`、`risk_warning`、`bearish_factor`
15. 7 个确定性字段必须由代码注入：`symbol`、`date`、`scores`（`to_score_entry` 映射）、`confidence_level`、`conflict_detected`、`data_sources`、`generated_at`
16. 系统必须用 Pydantic `LLMOutput`（5 字段）校验 LLM 输出，而非 `DecisionReport`（12 字段）
17. 校验失败时应用层重试 1 次（更严格的 prompt），仍失败返回 `error_type: "llm_parse_error"`
18. 合并 LLM 5 字段 + 代码 7 字段 → `DecisionReport.model_validate()` → 写入 `state["decision_report"]`

### FR-5：重试与错误处理

19. 网络超时/HTTP 429：SDK 层 `max_retries=2` 自动重试（最多 3 次调用）
20. 单次请求超时：`request_timeout=300` 秒后 SDK 异常 → `error_type: "llm_call"`
21. API key 缺失/配置文件缺失/401/403：不重试，返回 `error_type: "config"`
22. 非 JSON 或 `LLMOutput` schema 失败：应用层重试 1 次，仍失败返回 `error_type: "llm_parse_error"`
23. `technical_report` 为空/所有维度 insufficient：返回 `error_type: "input"`
24. `human_approved=False`：返回 `error_type: "human_review"`，条件边路由到 END
25. 所有错误写入 `state["error"]`，供下游节点和 Streamlit 读取

### FR-6：StateGraph 集成

26. 系统必须实现 `build_strategist_graph()` 函数，构建 `human_review` 和 `strategy_decider` 两个节点的 StateGraph
27. 条件边 `route_after_review(state)`：`human_approved=True` → `"strategy_decider"`，`False` → `"__end__"`

## 业务规则

- **LLM 不碰原始数据**：传给 LLM 的只能是评分/标签/指标值，不能是原始 OHLCV
- **确定性字段代码注入**：`symbol`、`date`、`scores`、`confidence_level`、`conflict_detected`、`data_sources`、`generated_at` 全部由代码计算/注入，LLM 不输出
- **冲突检测（零值不算方向）**：零值（=0）代表"中性"，不参与冲突判断。冲突定义 = 既有正分又有负分
- **强制反向因素**：LLM 必须输出 `bearish_factor`，prompt 规则强调"无论如何必须输出"
- **数据不足标注**：`data_sufficient=False` 的维度在 prompt 中标注"该维度数据不足"并在置信度/冲突计算中被过滤
- **`auto_approve` 为过渡开关**：Phase 1 无 Streamlit 时设为 `true`，UI 就绪后改为 `false`
- **Layer separation**：SDK 层重试（网络/429）vs 应用层重试（JSON/schema）互不交叉

## 边界情况与错误状态

| 场景 | 预期行为 |
|---|---|
| 所有维度 `data_sufficient=False` | 不执行 LLM，返回 `error_type: "input"` |
| LLM 返回的 JSON 多了额外字段 | `LLMOutput` + `DecisionReport` `extra="ignore"` 忽略，校验通过 |
| LLM 返回的 `overall_judgment` 不在枚举中 | `LLMOutput` Literal 校验失败 → 应用层重试 1 次 |
| `configs/llm.yaml` 不存在 | 返回 `error_type: "config"` |
| LLM API key 环境变量未设置 | `create_llm_client` 抛出 `ValueError` → `error_type: "config"` |
| LLM 请求超时（超过 300 秒） | SDK 抛出异常 → `error_type: "llm_call"` |
| `human_approved=False` + `auto_approve=False` | `human_review` 返回 `error_type: "human_review"`，条件边路由到 END |
| `indicators` 字段过多导致 prompt 超 token | Phase 1 12 个精选指标约 500-800 token，安全；Phase 2 新增时评估截断 |

## 数据与状态

### 输入

从 `AnalysisState.technical_report` 读取 — 维度从 `scores.keys()` 动态遍历，不硬编码。

### 输出

写入 `AnalysisState.decision_report`（12 字段：5 LLM 推理 + 7 代码注入）。

### 错误

写入 `AnalysisState.error`（`NotRequired[dict]`）：`{"error_type": "...", "message": "...", "detail": "..."}`。

### 配置文件

`configs/llm.yaml`：

```yaml
provider: deepseek
model: deepseek-chat
base_url: https://api.deepseek.com/v1
api_key_env: DEEPSEEK_API_KEY
temperature: 0.1
max_tokens: 4000
request_timeout: 300
auto_approve: true
```

### Pydantic 模型

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict

class ScoreEntry(BaseModel):
    value: int
    reason: str
    confidence: Literal["determined", "insufficient", "deferred"]

class LLMOutput(BaseModel):
    """LLM 只需输出此 5 个推理字段"""
    model_config = ConfigDict(extra="ignore")
    conflict_detail: str
    overall_judgment: Literal["乐观", "中性", "谨慎", "中性偏谨慎", "中性偏乐观"]
    key_driver: str
    risk_warning: str
    bearish_factor: str

class DecisionReport(BaseModel):
    """策略决策 Agent 最终输出（12 字段：5 LLM + 7 代码注入）"""
    model_config = ConfigDict(extra="ignore")
    symbol: str            # 代码注入
    date: str              # 代码注入
    scores: dict[str, ScoreEntry]              # 代码注入
    conflict_detected: bool                     # 代码注入（detect_conflict）
    conflict_detail: str                        # LLM 输出
    overall_judgment: Literal["乐观", "中性", "谨慎", "中性偏谨慎", "中性偏乐观"]  # LLM 输出
    confidence_level: Literal["高", "中", "低"]  # 代码注入
    key_driver: str                             # LLM 输出
    risk_warning: str                           # LLM 输出
    bearish_factor: str                         # LLM 输出
    data_sources: list[str]                     # 代码注入（build_data_sources）
    generated_at: str                           # 代码注入（datetime.now().isoformat()）
```

## 实现决策

- **代码位置**：`src/strategist/` — `schemas.py`（所有 Pydantic 模型 + 置信度/冲突/数据源函数 + LLM client + config）、`node.py`（human_review / strategy_decider 节点 + StateGraph 构建 + prompt 构造）
- **LLM SDK**：LangChain `ChatOpenAI`，`configs/llm.yaml` 指定 provider/model/base_url
- **Schema 分离**：`LLMOutput`（5 字段）校验 LLM 输出 → 与 7 个代码注入字段合并 → `DecisionReport`（12 字段）
- **冲突检测**：`detect_conflict()` 代码判断 "既有正又有负"，零值不算方向，`insufficient` 维度被过滤
- **数据源**：`build_data_sources()` 只包含 `data_sufficient=True` 的维度，从 `DIM_SOURCES` 映射取
- **生成时间**：`datetime.now().isoformat()`，代码注入
- **维度遍历**：`scores.keys()` 动态获取，不硬编码 `["technical", "fundamental", "capital"]`
- **重试分工**：SDK 层 `max_retries=2` 处理网络/429；应用层 `for attempt in range(2)` 处理 JSON/schema
- **超时**：`request_timeout=300` 从配置文件读取
- **配置缓存**：`_LLM_CONFIG_CACHE` 全局缓存，改配置需重启
- **错误传递**：`AnalysisState.error`（`NotRequired[dict]`），下游节点和 Streamlit 可读

## 测试决策

### 自动化测试（229 项全部通过）

- 置信度计算：覆盖 3/2/1/0 维全部组合
- 冲突检测：覆盖正/负/零值/insufficient 全部边缘
- 数据源构建：覆盖 sufficient 筛选
- LLMOutput 校验：mock 5 字段 JSON，验证 schema
- Prompt 构造：验证 5 字段模板，排除代码注入字段
- strategy_decider：LLMOutput 校验 → 合并 → DecisionReport 端到端
- human_review：auto_approve、拒绝 error、interrupt
- StateGraph：mock LLM 端到端 invoke
- LLM timeout config

### 手工验收

- 用行情分析 Agent 产出的真实 `TechnicalReport`（600519.SH）跑完整 LLM 流程
- 检查 LLM 输出的 `bearish_factor` 是否具体（不含"无"等敷衍回答）
- 检查 `overall_judgment` 是否与三维评分方向一致

## 验收标准

1. **Given** `auto_approve=True` + `technical_report` 含三维完整评分，**When** StateGraph 执行 `human_review → strategy_decider`，**Then** `decision_report` 含 12 字段，7 个确定性字段为代码注入
2. **Given** tech=+1, fund=+1, cap=-1，**When** 计算置信度，**Then** `confidence_level="低"`（max-min=2 ≥ 2）
3. **Given** tech=+1, fund=+1, cap=-1，**When** 检测冲突，**Then** `conflict_detected=True`（既有正又有负）
4. **Given** tech=+1, fund=0, cap=+1，**When** 检测冲突，**Then** `conflict_detected=False`（零值不算方向）
5. **Given** 三个维度 `data_sufficient=False`，**When** `strategy_decider`，**Then** 不调用 LLM，返回 `error_type: "input"`
6. **Given** LLM 返回非 JSON，**When** `strategy_decider`，**Then** 应用层重试 1 次，仍失败返回 `error_type: "llm_parse_error"`
7. **Given** LLM `overall_judgment` 不在枚举中，**When** `LLMOutput` 校验，**Then** 失败触发重试
8. **Given** `configs/llm.yaml` 缺失 / API key 未设，**When** `strategy_decider`，**Then** 返回 `error_type: "config"`
9. **Given** `auto_approve=False` + `human_approved=False`，**When** `human_review`，**Then** 返回 `error_type: "human_review"`，条件边路由到 END
10. **Given** LLM 返回 5 字段 JSON + 额外字段，**When** `LLMOutput` 校验，**Then** `extra="ignore"` 忽略，校验通过
11. **Given** `DimensionScore(data_sufficient=True)`，**When** `to_score_entry`，**Then** `confidence="determined"`
12. **Given** `DimensionScore(data_sufficient=False)`，**When** `to_score_entry`，**Then** `confidence="insufficient"`

## 开放问题

| 问题 | 负责人 | 状态 |
|---|---|---|
| DeepSeek/Qwen API key 未获取 | yanhe | 手工验收需要有效 key |
| `indicators` 截断策略的具体阈值 | yanhe | Phase 2 新增指标时评估 |
| Streamlit 消费 `error` 字段的具体 UI | yanhe | Streamlit 开发时实现 |

## 补充说明

- 系统设计文档：`docs/A股分析Agent系统设计.md`
- 设计决策：`docs/设计决策.md`
- 编码规则：`docs/agent-harness/coding-rules.md`
- 规格细化（v2）：`team-spec/spec/refine/2026-05-30-strategy-decider-agent.md`
- 规格评审（v2）：`team-spec/spec/reviews/2026-05-30-strategy-decider-agent.md`
- 重构 issues：`team-spec/issues/2026-05-30-strategy-decider-refactor/` (#35–#38)
