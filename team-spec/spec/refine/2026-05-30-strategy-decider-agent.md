# 规格细化：策略决策 Agent

## 需求摘要

策略决策 Agent 作为 LangGraph 流水线的 `human_review` + `strategy_decider` 两个节点，是四 Agent 中唯一调用 LLM 的环节。从 `AnalysisState.technical_report` 读取行情分析 Agent 产出的结构化评分和指标，构造包含上下文约束的 LLM prompt，让 LLM 进行交叉推理（综合判断、冲突识别、风险提示），输出结构化 JSON 写入 `AnalysisState.decision_report`。

## 规范术语

| 术语 | 定义 |
|---|---|
| `strategy_decider` | LangGraph 节点名，策略决策 Agent（LLM 推理） |
| `human_review` | LangGraph 节点名，Human-in-the-loop 审批（条件边），`auto_approve` 开关控制是否中断 |
| `DecisionReport` | 策略决策 Agent 输出 Pydantic 模型（JSON schema 中定义的所有字段） |
| `auto_approve` | `human_review` 节点的配置开关。`True` 时自动跳过审批直接进入 `strategy_decider`；`False` 时触发 LangGraph interrupt 等待用户确认 |
| LLM provider | DeepSeek 或 Qwen，通过 `configs/llm.yaml` 切换，均使用 OpenAI 兼容 SDK |
| 置信度 | 由维度一致性决定（3 维一致=高，2 维一致=中，否则=低），**代码计算，非 LLM 主观判断** |
| `bearish_factor` | 强制输出项：无论综合判断为何，必须输出一条最不支持该结论的反向理由 |

## 范围

### 范围内

- `human_review` 节点函数：检查 `human_approved` 字段，`auto_approve=True` 时自动通过，`False` 时使用 LangGraph `NodeInterrupt` 暂停
- `strategy_decider` 节点函数：构造 LLM prompt → 调用 LLM → Pydantic 校验输出 → 写入 `decision_report`
- 置信度计算函数（代码计算，非 LLM）
- `configs/llm.yaml` 配置文件（provider/model/endpoint/api_key_env）
- Pydantic 输出模型 `DecisionReport`
- LLM 输出校验失败时重试 1 次
- LLM 调用失败时重试（网络/429 重试 2 次，参数错误不重试）
- StateGraph 构建：`market_analyzer → human_review → strategy_decider`
- 结构化错误返回

### 范围外

- Streamlit UI（`human_review` 的实际交互界面届时由 Streamlit 实现）
- LLM 的提示词优化/tuning
- 情绪面评分维度（Phase 2，输出 schema 预留字段）
- `human_review` 的 checkpointer 持久化策略（Phase 2）
- 多 LLM provider 的自动 fallback

## 流水线结构

```
market_analyzer → human_review → strategy_decider
                    │                  │
              human_approved     decision_report
              (auto_approve 开关)
```

### human_review 节点

- 读取 `state["human_approved"]`
- `auto_approve=True`：直接返回 `{"human_approved": True}`，不中断
- `auto_approve=False`：抛出 `NodeInterrupt("请确认是否继续")`，等用户在 Streamlit 中点击批准后 resume

### strategy_decider 节点

1. 从 `state["technical_report"]` 读取评分和指标
2. 计算置信度（代码：维度一致性规则）
3. 构造 LLM prompt（含约束规则和结构化输出指令）
4. 调用 `openai.OpenAI` 兼容的 LLM
5. Pydantic 校验 LLM 输出 → 失败则重试 1 次
6. 写入 `state["decision_report"]`

## LLM 配置

`configs/llm.yaml`：

```yaml
provider: deepseek       # deepseek | qwen
model: deepseek-chat     # 模型名
base_url: https://api.deepseek.com/v1
api_key_env: DEEPSEEK_API_KEY   # 从哪个环境变量读取 key
temperature: 0.1         # 低温度减少随机性
max_tokens: 4000
auto_approve: true       # human_review 是否自动通过（无 Streamlit 时设为 true）
```

切换 Qwen：改 `provider: qwen`、`model: qwen-turbo`、`base_url`、`api_key_env` 四项即可。
`auto_approve` 控制 `human_review` 节点的中断行为，节点从配置文件读取该值。

## LLM Prompt 结构

```
技术面评分：{value}（{reason}）【确定性数据支撑】
基本面评分：{value}（{reason}）【确定性数据支撑】
资金面评分：{value}（{reason}）【确定性数据支撑，来源：Tushare moneyflow】

{indicators 关键指标摘要}

最大分差：|{max} - {min}| = {diff}

请基于以上评分进行交叉分析，严格按照以下 JSON 格式输出：
{
  "symbol": "...",
  "date": "...",
  "scores": { ... 回填传入的评分 },
  "conflict_detected": true/false,
  "conflict_detail": "技术面+基本面偏多，资金面偏空",
  "overall_judgment": "乐观/中性/谨慎/中性偏谨慎/中性偏乐观",
  "key_driver": "哪个维度权重最大及原因",
  "risk_warning": "如果判断偏乐观，必须列出风险因素",
  "bearish_factor": "强制输出一条最不支持当前判断的反向理由",
  "data_sources": ["数据来源列表"],
  "generated_at": "ISO 8601"
}

注意：不要输出 confidence_level，该字段由代码计算后注入。

规则：
1. 仅基于提供的数据进行分析，不要编造未提供的信息
2. 数据不足时标注"该维度数据不足"并说明缺少哪类数据
3. 无论综合判断如何，必须输出 bearish_factor
4. 不得输出 JSON 之外的文字
```

## 置信度计算（代码实现，非 LLM）

`data_sufficient=False` 的维度不参与一致性计算。方向定义：正（>0）、负（<0）、零（=0）。

| 有效维度数 | 置信度 | 条件 |
|---|---|---|
| 3 | 高 | 3 维方向一致 |
| 3 | 中 | 2 维方向一致 |
| 3 | 低 | 3 维方向各不相同，或任意两维得分差 ≥ 2 |
| 2 | 高 | 2 维方向一致 |
| 2 | 低 | 2 维方向不一致 |
| 1 | 低 | 唯一有效维度（标注"单维度，评估受限"） |
| 0 | N/A | 所有维度均数据不足，不执行 LLM，返回错误 |

## 错误处理

| 场景 | 处理 |
|---|---|
| LLM 网络超时/HTTP 429 | 重试 2 次，间隔 3 秒 |
| LLM 401/403 | 不重试，返回结构化错误 `error_type: "llm_auth"` |
| LLM 返回非 JSON | 重试 1 次（更严格的 prompt），仍失败返回 `error_type: "llm_parse_error"` |
| LLM 返回 JSON 但不合 schema | 同上 |
| `technical_report` 为空 | 返回结构化错误 `error_type: "input"` |

## 输出 Schema（Pydantic 模型）

```python
from typing import Literal

class ScoreEntry(BaseModel):
    value: int
    reason: str
    confidence: Literal["determined", "insufficient", "deferred"]
    # data_sufficient=True → "determined", False → "insufficient", Phase 2 sentiment → "deferred"

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

`scores` 中 Phase 1 含 `technical`/`fundamental`/`capital` 三个键，Phase 2 加 `sentiment`。

## 已关闭的开放问题

- `human_review` 和 `strategy_decider` 同属一个 PRD
- LLM provider 通过 `configs/llm.yaml` 切换
- LLM 输出校验失败重试 1 次
- 情绪面字段标 `"deferred"`，Phase 2 激活
- `human_review` 含 `auto_approve` 开关，默认 `True`
- LLM 调用失败复用数据采集 Agent 重试模式

## 风险

| 风险 | 等级 | 缓解 |
|---|---|---|
| LLM 返回 JSON 格式不稳定 | P1 | Pydantic 校验 + 重试 1 次 + `Literal` 类型约束 + 低温度 |
| `bearish_factor` 被 LLM 敷衍（如写"无"） | P2 | Prompt 明确要求"必须指出一条具体反向因素"，PRD 验收标准覆盖 |
| `indicators` 字段过多导致 token 超限 | P2 | PRD 中定义截断策略（优先保留评分相关键，次要指标可截断） |
| LangGraph `NodeInterrupt` 在无 checkpointer 时的行为 | P2 | 开发时先验证，`auto_approve=True` 时不会触发 interrupt |

## Change Log

- 2026-05-30：初始细化。确认 human_review+strategy_decider 双节点、LLM 配置、校验策略、重试机制、置信度计算规则。
- 2026-05-30：评审后修正——移除 LLM prompt 中的 `confidence_level`（改为代码注入）；补充缩减后置信度规则（2/1/0 维边界）；`overall_judgment` 改为 `Literal` 枚举；`auto_approve` 放入 `configs/llm.yaml`。
