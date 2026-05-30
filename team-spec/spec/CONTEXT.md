# 需求上下文

## 产品定位

A 股分析 Agent 系统——单人本地工具。用户输入股票代码，系统产出技术面/基本面/资金面三维评分 + LLM 综合研判报告，通过 Streamlit 仪表盘展示。

## 核心术语

| 术语 | 定义 |
|---|---|
| **分析单元** | 单票全面分析：输入一个股票代码，产出覆盖三个维度的完整分析报告 |
| **三维评分** | 技术面（MA/MACD/成交量比）、基本面（PE/ROE/财务趋势）、资金面（净流入/流出），每维 -2 ~ +2 |
| **数据采集 Agent** | LangGraph 流水线第一个节点，纯代码，调 Tushare API + Pydantic 校验 + Parquet 落盘 |
| **行情分析 Agent** | 第二个节点，纯代码，pandas-ta 算指标 + 三维评分（`score_technical/fundamental/capital`） |
| **DimensionScore** | 单维度评分结构：value（-2~+2）、reason（文本）、data_sufficient（数据是否充足） |
| **TechnicalReport** | 行情分析 Agent 输出：scores（三维 DimensionScore）+ indicators（派生指标值）+ metadata |
| **降级不阻塞** | 部分规则跳过仍可打分，维度数据缺失时才标记 `data_sufficient=False` 并归零 |
| **策略决策 Agent** | 第三、四个节点（`human_review` + `strategy_decider`），唯一使用 LLM 的节点，输入结构化评分，输出 `DecisionReport` |
| **human_review** | Human-in-the-loop 审批节点，`auto_approve` 开关控制是否中断等待用户确认 |
| **DecisionReport** | 策略决策 Agent 最终输出（12 字段：5 LLM 推理 + 7 代码注入），Pydantic 模型 `model_config(extra="ignore")` |
| **LLMOutput** | LLM 只需输出的 5 个推理字段 Pydantic 模型（`conflict_detail`, `overall_judgment`, `key_driver`, `risk_warning`, `bearish_factor`）。确定性字段全部代码注入 |
| **conflict_detected** | 代码判断（`detect_conflict`）：既有正分又有负分 → True。零值不算方向 |
| **bearish_factor** | 强制输出项：无论综合判断如何，LLM 必须输出至少一条反向风险理由 |
| **auto_approve** | 开关：`True` 时 `human_review` 自动通过，`False` 时触发 LangGraph interrupt 等待用户 |
| **LLM provider** | DeepSeek / Qwen，通过 `configs/llm.yaml` 切换，OpenAI 兼容 SDK 调用 |
| **报告推送 Agent** | 第四个节点，纯代码：组装 `AnalysisReport` + Parquet 归档（`{symbol}_{datetime}.parquet` 永不覆盖）。Streamlit `app.py` 独立渲染 UI |
| **AnalysisReport** | 报告推送 Agent 输出的 Pydantic 模型——上游三维评分 + 指标 + LLM 研判 + 原始数据路径引用 |
| **app.py** | Streamlit 独立入口，不在 LangGraph 图中。输入股票代码 → invoke 流水线 → 读 Parquet → 渲染结果 + 历史下拉 |
| **可追溯性三字段** | 每条数据必须携带 `source`（接口名）、`fetched_at`（拉取时间 ISO 8601）、`raw_value`（原始值） |
| **本地优先** | 有本地 Parquet 文件就直接用，用户点"刷新数据"才调 API 重拉 |

## 用户角色

- **个人投资者**：唯一的用户，也是开发者。通过 Streamlit 界面与系统交互。

## 业务规则

1. LLM 只在策略决策 Agent 调用，其他三个 Agent 全部纯代码
2. LLM 输入是代码预处理后的结构化 JSON，不让 LLM 碰原始数据计算
3. 评分由代码计算（-2 ~ +2），不是 LLM 主观判断
4. 置信度由维度一致性决定（高：3 维一致 / 中：2 维一致 / 低：不一致或强冲突），**代码计算，非 LLM 输出**
5. Phase 1 仅覆盖 A 股，仅 Tushare 数据源，仅三维评分（无情绪面）；`scores` 预留 `sentiment` 键标为 `deferred`
6. Stock code format: `600519.SH`, `000001.SZ`
7. 日期格式统一 `YYYYMMDD`

## Phase 范围

### Phase 1（当前）

- 单票全面分析（技术面 + 基本面 + 资金面）
- Tushare 数据采集
- pandas-ta 技术指标计算
- LLM 综合推理（DeepSeek / Qwen 可切换）
- Streamlit 仪表盘

### Phase 2（预留）

- 情绪面分析（加 AKShare 舆情数据）
- 多票对比 / 板块分析
- 定时任务
- 股票名称模糊搜索
