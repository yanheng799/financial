# PRD：策略决策 Agent

## 问题陈述

数据采集 Agent 和行情分析 Agent 已实现，能产出原始数据（`RawData`）和三维结构化评分（`TechnicalReport`）。但这些评分是独立的数字——技术面 +1、基本面 +1、资金面 -1——用户无法直接从中得出投资结论。系统需要一个 LLM 驱动的推理层：接收纯代码计算的评分和指标，进行交叉分析（哪两个维度冲突？哪个维度权重更大？），输出包含综合判断、风险提示和强制反向因素的研判报告。

## 目标

- 实现策略决策 Agent（`human_review` + `strategy_decider` 两个 LangGraph 节点），作为四 Agent 流水线的第三个环节
- 从 `AnalysisState.technical_report` 读取结构化评分和指标，构造带约束的 LLM prompt
- LLM 输出经 Pydantic 校验的结构化 `DecisionReport`，写入 `AnalysisState.decision_report`
- 置信度由代码计算（维度一致性规则），不依赖 LLM 主观判断
- 预留 `human_review` 人工审批节点，`auto_approve` 开关控制当前是否中断

## 非目标

- Streamlit UI（`human_review` 的审批交互界面单独实现）
- LLM 提示词优化/tuning
- 情绪面评分维度（Phase 2，但 output schema 预留 `sentiment` 字段）
- `human_review` 的 checkpointer 持久化策略
- 多 LLM provider 的自动 fallback
- 模型输出质量评估/RLHF

## 用户与场景

1. 作为个人投资者，我希望系统对三个维度的评分进行交叉分析，给出综合判断（乐观/中性/谨慎），以便我无需自己权衡矛盾信号。
2. 作为个人投资者，我希望系统强制输出一条反向风险因素（bearish factor），即使当前总体看多，也要提醒我可能的风险，以便我避免确认偏误。
3. 作为个人投资者，我希望看到各维度数据来源和置信度标注，以便我知道哪些结论有数据支撑、哪些是推测。
4. 作为个人投资者，我希望在验证期间，能先看到三维评分和指标，确认后再进入 LLM 综合推理，以便发现评分逻辑异常时及时中断。

## 当前状态

- 数据采集 Agent 已实现（`src/collector/`），产出 `RawData` 写入 `AnalysisState.raw_data`
- 行情分析 Agent 已实现（`src/analyzer/`），产出 `TechnicalReport` 写入 `AnalysisState.technical_report`
- `TechnicalReport` 包含三维 `DimensionScore` 和 13 个指标的 `indicators` 字典
- `AnalysisState.decision_report` 和 `human_approved` 字段已定义但无生产者
- `src/strategist/` 目录尚未创建
- LLM 库（`openai` Python SDK）未安装，DeepSeek/Qwen API key 未配置

## 方案描述

策略决策 Agent 作为 LangGraph 流水线的两个连续节点运行：

```
market_analyzer → human_review → strategy_decider
                    │                  │
              human_approved     decision_report
              (auto_approve 开关)
```

### human_review 节点

- 读取 `state["human_approved"]`
- 从 `configs/llm.yaml` 读取 `auto_approve` 开关
- `auto_approve=True`：直接设置 `{"human_approved": True}`，不中断
- `auto_approve=False`：抛出 `NodeInterrupt("请确认 technical_report，批准后继续")`，等待用户在 Streamlit 点击批准后 resume

### strategy_decider 节点

1. 从 `state["technical_report"]` 提取三个维度的评分和全部指标
2. 计算置信度（代码根据维度一致性决定）
3. 将 `DimensionScore` 映射为 `ScoreEntry`（`data_sufficient=True → "determined"`, `False → "insufficient"`）
4. 构造带约束的 LLM prompt（含评分摘要、指标数据、输出格式指令）
5. 调用 `openai.OpenAI` 兼容的 LLM（DeepSeek 或 Qwen，由 `configs/llm.yaml` 指定）
6. Pydantic 校验 LLM 输出 → 失败则用更严格的 prompt 重试 1 次
7. 代码注入 `confidence_level` 到校验后的结果
8. 组装完整 `DecisionReport`，写入 `state["decision_report"]`

## 范围

### 范围内

- `human_review` 节点函数（含 `auto_approve` 开关）
- `strategy_decider` 节点函数（LLM prompt 构造 + LLM 调用 + 校验 + 注入置信度）
- 置信度计算函数（代码实现，3/2/1/0 维规则）
- `configs/llm.yaml` 配置文件
- Pydantic 模型 `ScoreEntry`、`DecisionReport`
- `DimensionScore` → `ScoreEntry` 映射
- LLM 输出校验失败重试 1 次
- LLM 调用失败重试（网络/429 重试 2 次，参数错误不重试）
- StateGraph 构建函数：`market_analyzer → human_review → strategy_decider`
- 结构化错误返回

### 范围外

- Streamlit UI
- LLM 提示词优化/tuning
- 情绪面评分（Phase 2，字段预留 `"deferred"`）
- `human_review` 的 checkpointer 持久化
- 多 LLM provider 自动 fallback

## 功能需求

### FR-1：LLM 配置

1. 系统必须从 `configs/llm.yaml` 读取 LLM 配置（provider、model、base_url、api_key_env、temperature、max_tokens、auto_approve）
2. 系统必须支持 DeepSeek 和 Qwen 两个 provider，切换只改配置文件
3. `api_key` 只能从配置文件指定的环境变量读取，不得写入配置文件或代码

### FR-2：human_review 节点

4. 系统必须实现 `human_review_agent(state: AnalysisState) -> dict` 节点函数
5. 当 `auto_approve=True` 时，自动设置 `human_approved=True` 并返回
6. 当 `auto_approve=False` 时，抛出 LangGraph `NodeInterrupt` 暂停执行

### FR-3：置信度计算（代码）

7. 系统必须实现 `compute_confidence(scores: dict[str, DimensionScore]) -> str` 函数
8. 规则如下（`data_sufficient=False` 的维度不参与）：

| 有效维度数 | 置信度 | 条件 |
|---|---|---|
| 3 | 高 | 3 维方向一致（同正/同负/同零） |
| 3 | 中 | 2 维方向一致 |
| 3 | 低 | 3 维各不相同，或任意两维得分差 ≥ 2 |
| 2 | 高 | 2 维方向一致 |
| 2 | 低 | 2 维方向不一致 |
| 1 | 低 | 仅 1 维有效 |
| 0 | N/A | 不执行 LLM，返回错误 |

### FR-4：strategy_decider 节点

9. 系统必须实现 `strategy_decider_agent(state: AnalysisState) -> dict` 节点函数
10. 系统必须从 `state["technical_report"]` 读取 `scores` 和 `indicators`
11. 系统必须将 `DimensionScore` 转换为 `ScoreEntry`（`data_sufficient=True → "determined"`, `False → "insufficient"`）
12. 系统必须构造 LLM prompt，包含：
    - 三维评分摘要（每维：value、reason、data sources）
    - 关键指标摘要（indicators 中的关键值）
    - 最大分差
    - JSON 输出格式模板
    - 约束规则（不编造数据、强制输出 bearish_factor、仅输出 JSON）
13. 系统必须调用 LLM 并读取 JSON 响应
14. 系统必须用 Pydantic `DecisionReport` 校验 LLM 输出
15. 校验失败时必须以更严格的 prompt 重试 1 次
16. 系统必须在校验通过后注入 `confidence_level`（代码计算的置信度）
17. 系统必须将 `DecisionReport.model_dump()` 写入 `state["decision_report"]`

### FR-5：重试与错误处理

18. 网络超时/HTTP 429：重试 2 次，间隔 3 秒
19. 401/403：不重试，返回 `error_type: "llm_auth"`
20. 非 JSON 或不合 schema：重试 1 次，仍失败返回 `error_type: "llm_parse_error"`
21. `technical_report` 为空：返回 `error_type: "input"`

### FR-6：StateGraph 集成

22. 系统必须实现 `build_strategist_graph()` 函数，构建包含 `human_review` 和 `strategy_decider` 两个节点的 StateGraph
23. 图结构：`human_review` → (条件边: `human_approved`?) → `strategy_decider`

## 业务规则

- **LLM 不碰原始数据**：传给 LLM 的只能是 `TechnicalReport` 中的评分/标签/指标值，不能是原始 OHLCV
- **置信度代码计算**：不与 LLM 输出的任何字段冲突，在 Pydantic 校验后注入
- **强制反向因素**：LLM 必须输出 `bearish_factor`，prompt 规则强调"无论如何必须输出"
- **数据不足标注**：`data_sufficient=False` 的维度在 prompt 中标注"该维度数据不足"
- **`auto_approve` 为过渡开关**：Phase 1 无 Streamlit 时设为 `true`，UI 就绪后改为 `false`

## 边界情况与错误状态

| 场景 | 预期行为 |
|---|---|
| 所有维度 `data_sufficient=False` | 不执行 LLM，返回 `error_type: "input"`, reason 含"所有维度数据不足" |
| LLM 返回的 JSON 多了额外字段 | Pydantic `model_validate` 忽略额外字段（`extra="ignore"`），校验通过 |
| LLM 返回的 `overall_judgment` 不在枚举中 | Pydantic `Literal` 校验失败 → 重试 1 次 |
| `configs/llm.yaml` 不存在 | 返回 `error_type: "config"`, 含配置指引 |
| LLM API key 环境变量未设置 | `openai.OpenAI` 初始化失败 → `error_type: "config"` |
| `indicators` 字段过多导致 prompt 超 max_tokens | 截断策略：保留全部 13 键名，数值截断为 `round(v, 2)`；仍超限则删除 `data_sources` 中冗余项 |

## 数据与状态

### 输入

从 `AnalysisState.technical_report`（即 `TechnicalReport.model_dump()`）读取：

```python
{
    "scores": {
        "technical":  {"value": 1, "reason": "...", "data_sufficient": true},
        "fundamental": {"value": 0, "reason": "...", "data_sufficient": false},
        "capital":     {"value": -1, "reason": "...", "data_sufficient": true}
    },
    "indicators": { "ma5": 1850.2, ..., "lg_buy_sell_ratio": 0.6 }
}
```

### 输出

写入 `AnalysisState.decision_report`（即 `DecisionReport.model_dump()`）：

```python
{
    "symbol": "600519.SH",
    "date": "20260530",
    "scores": {
        "technical":  {"value": 1, "reason": "...", "confidence": "determined"},
        "fundamental": {"value": 0, "reason": "...", "confidence": "insufficient"},
        "capital":     {"value": -1, "reason": "...", "confidence": "determined"}
    },
    "conflict_detected": true,
    "conflict_detail": "技术面+基本面偏多，资金面偏空",
    "overall_judgment": "中性偏谨慎",
    "confidence_level": "中",  # 代码注入
    "key_driver": "资金面净流出信号弱化了技术面多头排列的积极信号",
    "risk_warning": "若主力持续净流出，技术面多头排列将失去资金面支撑",
    "bearish_factor": "近5日主力净流出明显，大单卖出比率偏高",
    "data_sources": ["Tushare daily 2026-05-30", "Tushare fina_indicator Q1 2026", "Tushare moneyflow 2026-05-30"],
    "generated_at": "2026-05-30T16:30:00"
}
```

### 配置文件

`configs/llm.yaml`：

```yaml
provider: deepseek
model: deepseek-chat
base_url: https://api.deepseek.com/v1
api_key_env: DEEPSEEK_API_KEY
temperature: 0.1
max_tokens: 4000
auto_approve: true
```

### Pydantic 模型

```python
from typing import Literal
from pydantic import BaseModel

class ScoreEntry(BaseModel):
    value: int
    reason: str
    confidence: Literal["determined", "insufficient", "deferred"]

class DecisionReport(BaseModel):
    symbol: str
    date: str
    scores: dict[str, ScoreEntry]
    conflict_detected: bool
    conflict_detail: str
    overall_judgment: Literal["乐观", "中性", "谨慎", "中性偏谨慎", "中性偏乐观"]
    confidence_level: Literal["高", "中", "低"]  # 代码注入，非 LLM 输出
    key_driver: str
    risk_warning: str
    bearish_factor: str
    data_sources: list[str]
    generated_at: str
```

## 实现决策

- **代码位置**：`src/strategist/` 目录，含 `schemas.py`（Pydantic 模型 + 置信度计算）、`node.py`（human_review/strategy_decider 节点 + StateGraph 构建）
- **LLM SDK**：`openai.OpenAI` 兼容协议，通过 `base_url` 参数切换 DeepSeek/Qwen
- **置信度注入时机**：Pydantic `model_validate()` 之后、`model_dump()` 之前，通过直接修改 `DecisionReport.confidence_level` 字段
- **DimensionScore → ScoreEntry 转换**：在 prompt 构造阶段完成，转换逻辑：`data_sufficient=True → confidence="determined"`, `False → "insufficient"`
- **StateGraph 条件边**：`human_review` 后接条件边 `route_after_review(state) → "strategy_decider" if state["human_approved"] else END`
- **`auto_approve` 来源**：从 `configs/llm.yaml` 读取，不在 state 中保存

## 测试决策

### 自动化测试

- **置信度计算测试**：mock `DimensionScore` 字典，覆盖 3/2/1/0 维各种组合
- **DimensionScore → ScoreEntry 映射测试**：验证 `data_sufficient` 到 `confidence` 的正确转换
- **prompt 构造测试**：给定固定 `TechnicalReport`，验证生成的 prompt 包含所有必需字段和约束规则
- **LLM 输出校验测试**：mock LLM 返回各种不规范 JSON，验证 Pydantic 校验和重试逻辑
- **重试机制测试**：mock `openai.OpenAI` 超时/429/401/403/非 JSON 等场景，验证重试和错误处理
- **StateGraph 测试**：mock LLM，验证两个节点的完整 StateGraph 可 invoke
- **`human_review` 节点测试**：验证 `auto_approve=True` 自动通过、`auto_approve=False` 抛出 NodeInterrupt
- **错误处理测试**：空 `technical_report`、配置缺失、API key 缺失

### 手工验收

- 用行情分析 Agent 产出的真实 `TechnicalReport`（600519.SH）跑完整 LLM 流程
- 检查 LLM 输出的 `bearish_factor` 是否具体（不含"无"等敷衍回答）
- 检查 `overall_judgment` 是否与三维评分方向一致（不一致时 `conflict_detected=True`）

## 验收标准

1. **Given** `auto_approve=True` 且 `technical_report` 包含三维完整评分，**When** 通过 StateGraph 执行 `human_review → strategy_decider`，**Then** `state["decision_report"]` 包含 `DecisionReport` 全部字段，`confidence_level` 由代码注入
2. **Given** 技术面 +1、基本面 +1、资金面 -1（技术面和基本面方向一致），**When** 计算置信度，**Then** `confidence_level="中"`
3. **Given** 三个维度均为 `data_sufficient=False`，**When** 执行 `strategy_decider`，**Then** 不调用 LLM，返回 `error_type: "input"`
4. **Given** LLM 返回非 JSON，**When** 执行 `strategy_decider`，**Then** 重试 1 次，仍失败返回 `error_type: "llm_parse_error"`
5. **Given** LLM 返回合法 JSON 但 `overall_judgment` 不在枚举中，**When** Pydantic 校验，**Then** 失败触发重试
6. **Given** `configs/llm.yaml` 缺失或 API key 环境变量未设置，**When** 执行 `strategy_decider`，**Then** 返回 `error_type: "config"`
7. **Given** `auto_approve=False`，**When** 执行 `human_review`，**Then** 抛出 `NodeInterrupt`
8. **Given** `DimensionScore(data_sufficient=True)`，**When** 映射为 `ScoreEntry`，**Then** `confidence="determined"`
9. **Given** `DimensionScore(data_sufficient=False)`，**When** 映射为 `ScoreEntry`，**Then** `confidence="insufficient"`

## 开放问题

| 问题 | 负责人 | 不解决的影响 |
|---|---|---|
| `openai` Python SDK 未安装 | yanhe | 安装后 LLM 调用才能编译运行 |
| DeepSeek/Qwen API key 未获取 | yanhe | 手工验收需要有效 key |
| `indicators` 截断策略的具体阈值 | yanhe | 当真实数据超 token 上限时才暴露 |

## 补充说明

- 系统设计文档：`docs/A股分析Agent系统设计.md`（LLM prompt 模板 + JSON schema）
- 设计决策：`docs/设计决策.md`（决策 #3 LLM 调用点、#4 输入边界、#9 LLM 选型）
- 编码规则：`docs/agent-harness/coding-rules.md`（LLM 相关硬规则 #6-9）
- 行情分析 PRD：`team-spec/prd/2026-05-30-market-analyzer-agent.md`（输入数据结构 `TechnicalReport`）
- 规格细化：`team-spec/spec/refine/2026-05-30-strategy-decider-agent.md`
- 规格评审：`team-spec/spec/reviews/2026-05-30-strategy-decider-agent.md`
