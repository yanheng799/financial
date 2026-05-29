# 架构地图

Agent 执行任务时需要理解的模块边界、数据流和代码入口。

## 整体数据流

```
用户输入股票代码
       ↓
Streamlit（UI 层，Phase 1 末实现）
       ↓
LangGraph StateGraph
       ↓
data_collector ──→ market_analyzer ──→ human_review ──→ strategy_decider ──→ report_publisher
  (纯代码)          (纯代码)          (验证期必须)      (LLM 介入)         (纯代码)
       ↓                 ↓                   ↓                ↓                 ↓
  raw_data        technical_report     human_approved   decision_report    最终报告 JSON
```

## 代码入口

```
src/
├── state.py                 # AnalysisState（TypedDict）—— 所有 Agent 共享的 State 定义
│
├── collector/               # 数据采集 Agent（当前要实现的）
│   ├── __init__.py          # 导出 data_collector_agent 函数
│   ├── adapter.py           # TushareAdapter —— Tushare API 调用封装
│   │                        #   关键方法：fetch_daily(), fetch_daily_basic(),
│   │                        #              fetch_fina_indicator(), fetch_income(),
│   │                        #              fetch_moneyflow(), fetch_all()
│   ├── schemas.py           # Pydantic 数据模型
│   │                        #   RawData, DailyQuoteData, FundData, CapitalFlowData
│   └── storage.py           # Parquet 读写 + 缓存逻辑
│
├── analyzer/                # 行情分析 Agent（后续）—— pandas-ta 算指标 + 三维评分
├── strategist/              # 策略决策 Agent（后续）—— 唯一调用 LLM 的节点
└── publisher/               # 报告推送 Agent（后续）—— JSON → Streamlit 渲染
```

## 关键模块边界

| 模块 | 职责边界 | 不负责 |
|---|---|---|
| `collector/adapter.py` | 调 Tushare API、返回原始数据 | 不算指标、不评分 |
| `collector/schemas.py` | 数据结构定义和校验 | 不做业务逻辑 |
| `collector/storage.py` | Parquet 读写和缓存判断 | 不知道数据含义 |
| `state.py` | State 类型定义 | 不含任何逻辑 |
| `analyzer/`（后续） | 算技术指标 + 评分 | 不调 API、不调 LLM |
| `strategist/`（后续） | LLM 综合推理 | 不算指标、不下单 |

## Agent 最容易误判的点

1. **`daily_basic` 归 fundamental 不归 daily**：PE/PB 虽然是日频数据，但它是基本面评分的输入，存在 `fundamental` 子结构中
2. **评分是代码算不是 LLM 算**：所有评分函数在 `analyzer/` 中用纯代码实现，LLM 只在 `strategist/` 中做综合推理
3. **fundamental 按接口拆子文件**：`daily_basic`（日频）、`fina_indicator`（季频）、`income`（季频）分别存为独立 Parquet，不混在一个文件里
4. **moneyflow 可能不可用**：Tushare 积分不足时该接口返回错误，采集 Agent 应降级处理而非报错退出

## 数据文件结构

```
data/                          # .gitignore 排除
├── daily/
│   └── {ts_code}.parquet     # daily 接口（OHLCV）
├── fundamental/
│   ├── {ts_code}_daily_basic.parquet      # 日频估值（PE/PB）
│   ├── {ts_code}_fina_indicator.parquet   # 季频质量（ROE 等）
│   └── {ts_code}_income.parquet           # 季频营收利润
└── capital/
    └── {ts_code}.parquet     # moneyflow 接口（资金流）
```
