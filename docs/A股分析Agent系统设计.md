# A股分析 Agent 系统设计

## 一、整体架构

四层架构，职责清晰不耦合：

```
数据源层        Tushare（财报/基本面/估值）+ AKShare（行情/舆情/情绪）+ LLM API
     ↓
采集层          数据采集 Agent：定时拉取 · 清洗标准化 · 数据来源+时间戳标注 · 多源交叉校验 · Pydantic 校验
     ↓
分析层          LangGraph 多 Agent 编排：行情分析 → 策略决策 → 报告推送（State 传递 · Checkpoint 持久化 · Human-in-the-loop）
     ↓
展示层          Streamlit 仪表盘：K线图 · 多维分析报告 · PE/PB分位 · 资金流向 · 板块排行
```

### 架构核心原则

- **数据可追溯**：每条数据写入时附带 `source`、`fetched_at`、`raw_value` 三字段，不事后补
- **Pydantic 校验放采集出口**：脏数据在进入分析层前拦截，而非下游处理
- **幻觉防控嵌入第一周**：不是出问题再加，而是建设之初就约束

### 启动路线图

| 阶段 | 时间 | 目标 | 验收标准 |
|------|------|------|----------|
| 数据双源验证 | 第 1 周 | 数据采集 Agent 同时对接 Tushare + AKShare | 连续 5 天无报错，随机抽查 20 个数据点与原始数据源交叉验证 |
| Agent 原型 | 第 2–3 周 | 行情分析 Agent 跑通完整技术分析周期 | 回测一段历史行情，趋势信号和关键风险因子基本准确 |
| 完整流水线 | 第 4 周+ | 四 Agent 全部跑通 + Streamlit 仪表盘 | 完整闭环运行，对比 Agent 与人工分析的盲区差异 |

> 阶段切换原则：每个阶段验收指标全部达标、连续验证期完整通过后，才进入下一阶段。过早扩大规模是个人金融 Agent 项目中最常见的失败模式。

---

## 二、行情分析 Agent：技术指标体系

### 指标优先级

**第一周原型只需三个**，覆盖"趋势 + 确认"核心逻辑：

1. MA 均线系统（趋势方向）
2. MACD（动量确认）
3. 成交量均量比（是否放量）

KDJ、BOLL、ATR 在第二阶段稳定后再加入。

### 完整指标体系

#### 趋势判断

| 指标 | 参数 | 核心信号 |
|------|------|----------|
| 均线系统 | MA5 / MA10 / MA20 / MA60 | 金叉/死叉 · 多空排列 |
| EMA | EMA12 / EMA26 | 趋势方向更灵敏 |
| BOLL 布林带 | 20日 / 2σ | 收口预警突破 · 扩口趋势确认 |

#### 动量分析

| 指标 | 参数 | 核心信号 |
|------|------|----------|
| MACD | 12 / 26 / 9 | 顶底背离 · 柱状图扩缩 |
| KDJ | 9 / 3 / 3 | 超买超卖（80/20阈值） · 死叉钝化 |
| RSI | 6 / 12 / 24 | 70/30 阈值 · 背离 |
| CCI | 14日 | 顺势突破 +100/-100 |

#### 波动率分析

| 指标 | 用途 |
|------|------|
| ATR 真实波幅 | 止损位设置（1.5–2× ATR） |
| 布林带宽度 | 收口后突破预警 |
| HV 历史波动率 | 20日/60日波动率分位 |

#### 成交量分析

| 指标 | 核心信号 |
|------|----------|
| 量价关系 | 放量突破 · 缩量回调 · 量价背离 |
| OBV 能量潮 | 主力资金累积/派发趋势 |
| 成交量均线 | MA5/MA20，放量阈值：1.5倍均量 |

**成交量异常阈值（A股建议）**：

- ≥ 1.5× 20日均量 → 放量
- ≥ 2.5× 20日均量 → 异常放量
- 代码里硬编码判断后作为布尔标签传给 LLM，避免 LLM 自行定义"放量"

#### 形态与支撑阻力

- K线形态：头肩顶/底 · 锤头线/射击之星 · 跳空缺口
- 支撑阻力：历史高低点 · 均线压力位 · 成交密集区

### 幻觉防控：指标数据的传入格式

指标计算必须在代码中完成再传给 LLM，不能让 LLM 自己"估算"指标值：

```
MACD(12,26,9): DIF=0.42, DEA=0.38, 柱状图=+0.04（连续3日扩张）
数据来源: Tushare daily, 2026-05-29 收盘后
```

LLM 的职责是解读信号，不是计算数值。

---

## 三、策略决策 Agent：四维度交叉分析

### 整体流程

```
四维数据输入（技术面 / 基本面 / 资金面 / 情绪面）
     ↓
各维度独立评分（代码计算，-2 到 +2）
     ↓
冲突检测（最大分差 > 2 → 标记冲突维度 · 置信度降级）
     ↓
置信度分级（代码判断，非 LLM 主观）
     ↓
结构化决策报告（含强制反向风险因素）
```

### 单维度评分规则

评分必须在代码里算完再传给 LLM，结果不可复现的分析没有参考价值。

```python
def score_technical(indicators: dict) -> tuple[int, str]:
    score = 0
    reason = []

    # 均线多空排列
    if indicators["ma5"] > indicators["ma20"] > indicators["ma60"]:
        score += 1
        reason.append("均线多头排列")
    elif indicators["ma5"] < indicators["ma20"] < indicators["ma60"]:
        score -= 1
        reason.append("均线空头排列")

    # MACD 柱状图方向
    if indicators["macd_hist"] > 0 and indicators["macd_hist_prev"] < indicators["macd_hist"]:
        score += 1
        reason.append("MACD柱扩张")
    elif indicators["macd_hist"] < 0 and indicators["macd_hist_prev"] > indicators["macd_hist"]:
        score -= 1
        reason.append("MACD柱缩减")

    # 成交量修正
    if indicators["vol_ratio"] > 1.5:
        pass  # 放量，保持原分
    elif indicators["vol_ratio"] < 0.7:
        score = int(score * 0.5)  # 缩量削弱信号强度

    return max(-2, min(2, score)), "；".join(reason)
```

四个维度各写一个打分函数，统一输出 `(-2, -1, 0, +1, +2)` + 文字说明。

### 置信度分级规则（代码判断）

| 等级 | 条件 |
|------|------|
| 高 | 4 个维度方向一致 |
| 中 | 3 个维度方向一致 |
| 低 | 2 个维度以下，或存在强冲突（任意两维分差 ≥ 2） |

置信度由四维评分一致性决定，代码计算，不是 LLM 的主观判断。

**两层置信度叠加**：

- 第一层（数据可信度）：数据是 Tushare 实时拉取还是 LLM 推断，采集时就打标签
- 第二层（结论可信度）：由四维评分一致性决定，代码计算

### Prompt 结构（传给 LLM 的完整格式）

```
技术面评分：+1（均线多头排列；MACD柱扩张）【确定性数据支撑】
基本面评分：+1（PE处于五年30%分位；ROE同比提升）【确定性数据支撑】
资金面评分：-1（近5日主力净流出2.3亿）【确定性数据支撑，来源：Tushare moneyflow，2026-05-29】
情绪面评分：0（舆情中性，无异常信号）【数据不足，仅供参考】

最大分差：|+1 - (-1)| = 2，资金面与技术面/基本面方向相反。

请基于以上评分进行交叉分析，输出：
1. 综合判断（乐观/中性/谨慎）
2. 主要驱动因素（必须指出哪个维度权重最大及原因）
3. 冲突信号说明（技术面+基本面偏多，资金面偏空，需解释如何权衡）
4. 置信度等级（高/中/低）及理由
5. 反向风险因素（强制输出一条最不支持当前结论的理由）

不得编造未提供的数据。情绪面数据不足时标注"该维度数据不足"。
```

### 反向风险因素是硬约束

必须写进 Prompt 强制要求，不是可选项。LLM 在结论乐观时会倾向于略去风险提示，靠自觉不可靠，必须用 Prompt 约束：

> "无论综合判断为何，必须输出一条当前最不支持该判断的反向理由。"

### 结构化输出字段

```json
{
  "symbol": "600519.SH",
  "date": "2026-05-29",
  "scores": {
    "technical": { "value": 1, "reason": "均线多头排列；MACD柱扩张", "confidence": "determined" },
    "fundamental": { "value": 1, "reason": "PE五年30%分位；ROE提升", "confidence": "determined" },
    "capital": { "value": -1, "reason": "近5日主力净流出2.3亿", "confidence": "determined" },
    "sentiment": { "value": 0, "reason": "舆情中性", "confidence": "insufficient" }
  },
  "conflict_detected": true,
  "conflict_detail": "技术面+基本面偏多，资金面偏空",
  "overall_judgment": "中性偏谨慎",
  "confidence_level": "中",
  "key_driver": "资金面净流出信号需重点关注",
  "risk_warning": "若资金持续净流出，技术面多头排列将失去资金面支撑",
  "bearish_factor": "主力连续5日净流出，机构可能在技术形态良好时减仓",
  "data_sources": ["Tushare moneyflow 2026-05-29", "Tushare fina_indicator Q1 2026"],
  "generated_at": "2026-05-29T16:30:00+08:00"
}
```

---

## 四、幻觉防控工程手段汇总

金融场景对幻觉的容忍度极低。Agent 给出错误结论时，还会制造出"已被验证过"的虚假确定感。以下手段在第一周就应嵌入：

| 手段 | 实施位置 | 说明 |
|------|----------|------|
| 数据来源 + 时间戳标注 | 采集 Agent | 每条数据写入时附带，不事后补 |
| 多源交叉校验 | 采集 Agent | Tushare 与 AKShare 同一数据不一致则打异常标记 |
| 指标代码计算 | 分析 Agent | 传给 LLM 的是计算结果，不让 LLM 估算 |
| 推理边界声明 | Prompt | "无法确认的数据请标注'该数据未确认'，不要推测填充" |
| 数据不足标注 | Prompt | "某维度数据不足时标注'该维度数据不足'并说明缺少哪类数据" |
| 置信度代码判断 | 决策 Agent | 置信度由评分一致性代码算出，非 LLM 主观 |
| 强制反向风险因素 | Prompt | 无论结论如何，强制输出一条反向理由 |

---

## 五、LangGraph 编排关键配置

```python
from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver

# State 结构
class AnalysisState(TypedDict):
    symbol: str
    raw_data: dict          # 采集 Agent 输出
    technical_report: dict  # 行情分析 Agent 输出
    decision_report: dict   # 策略决策 Agent 输出
    human_approved: bool    # Human-in-the-loop 节点

# 图结构
builder = StateGraph(AnalysisState)
builder.add_node("data_collector", data_collector_agent)
builder.add_node("market_analyzer", market_analyzer_agent)
builder.add_node("human_review", human_review_node)   # 验证期必须保留
builder.add_node("strategy_decider", strategy_decider_agent)
builder.add_node("report_publisher", report_publisher_agent)

builder.add_edge("data_collector", "market_analyzer")
builder.add_edge("market_analyzer", "human_review")
builder.add_conditional_edges("human_review", route_by_approval)
builder.add_edge("strategy_decider", "report_publisher")

# Checkpoint 持久化（支持中断恢复）
checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)
```

Human-in-the-loop 节点在验证期（至少一个季度）必须保留，不因"Agent 很靠谱"而跳过。

---

## 六、参考资源

| 资源 | 链接 |
|------|------|
| AKShare 文档 | https://akshare.akfamily.xyz/ |
| LangGraph 文档 | https://langchain-ai.github.io/langgraph/ |
| Streamlit 文档 | https://docs.streamlit.io/ |
| Tushare 注册 | https://tushare.pro/register |
