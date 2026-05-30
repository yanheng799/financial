# A 股分析 Agent 系统

基于 LangGraph 多 Agent 编排的个人量化分析工具。输入股票代码，自动完成数据采集 → 行情分析 → 策略决策 → 报告推送全流程，通过 Streamlit 仪表盘展示。

## 架构

```
数据采集 Agent ──→ 行情分析 Agent ──→ 策略决策 Agent ──→ 报告推送 Agent
 (纯代码)          (纯代码)           (LLM 推理)         (纯代码)
     │                  │                  │                  │
  RawData         TechnicalReport     DecisionReport    AnalysisReport
                                                         Parquet 归档
```

| Agent | 实现 | 输入 | 输出 |
|---|---|---|---|
| 数据采集 | Tushare API + Pydantic | 股票代码 | 日线/财务/资金流数据 (Parquet) |
| 行情分析 | pandas-ta + 评分函数 | 原始数据 | 三维评分 (-2~+2) + 13 指标 |
| 策略决策 | LLM (DeepSeek/Qwen) | 结构化评分 | 综合研判 + 冲突识别 + 风险提示 |
| 报告推送 | Parquet 归档 | 研判报告 | Streamlit 展示 + 历史回溯 |

## 快速开始

### 1. 安装

```bash
git clone https://github.com/yanheng799/financial.git
cd financial

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 安装依赖
pip install -e ".[dev]"
pip install streamlit
```

### 2. 配置

```bash
# Tushare API Token（必需）
export TUSHARE_TOKEN=your_token_here

# LLM API Key（策略决策 Agent 使用）
export DEEPSEEK_API_KEY=your_key_here   # 或 QWEN_API_KEY
```

LLM 配置在 `configs/llm.yaml`，可切换 DeepSeek / Qwen。

### 3. 运行

```bash
streamlit run app.py
```

浏览器打开 `http://localhost:8501`，输入股票代码（如 `600519`）→ 点击"开始分析"。

## 项目结构

```
financial/
├── app.py                       # Streamlit 仪表盘入口
├── configs/
│   └── llm.yaml                 # LLM 配置 (provider/model/key)
├── src/
│   ├── state.py                 # AnalysisState (LangGraph 共享 State)
│   ├── collector/               # 数据采集 Agent
│   │   ├── adapter.py           #   Tushare API 适配器
│   │   ├── schemas.py           #   RawData Pydantic 模型
│   │   ├── storage.py           #   Parquet 读写 + 缓存
│   │   └── node.py              #   LangGraph 节点 + StateGraph
│   ├── analyzer/                # 行情分析 Agent
│   │   ├── schemas.py           #   TechnicalReport / DimensionScore
│   │   ├── indicators.py        #   技术/基本面/资金面指标计算
│   │   ├── scoring.py           #   三维评分函数
│   │   └── node.py              #   LangGraph 节点 + StateGraph
│   ├── strategist/              # 策略决策 Agent (LLM)
│   │   ├── schemas.py           #   LLMOutput / DecisionReport / ScoreEntry
│   │   └── node.py              #   human_review + strategy_decider 节点
│   └── publisher/               # 报告推送 Agent
│       ├── schemas.py           #   AnalysisReport Pydantic 模型
│       └── node.py              #   report_publisher 节点 + StateGraph
├── tests/                       # 测试 (253 项)
├── docs/                        # 设计文档
├── team-spec/                   # 需求规格 / PRD / Issues
│   ├── spec/                    #   细化 + 评审 + 上下文 + 决策
│   ├── prd/                     #   PRD 文档
│   └── issues/                  #   工程 Issue 草稿
└── pyproject.toml               # 项目配置
```

## 核心依赖

| 包 | 用途 |
|---|---|
| [tushare](https://github.com/waditu/tushare) | A 股数据接口 |
| [pandas](https://pandas.pydata.org/) + [pandas-ta](https://github.com/twopirllc/pandas-ta) | 数据处理 + 技术指标 |
| [langgraph](https://github.com/langchain-ai/langgraph) | 多 Agent 编排 + StateGraph |
| [langchain-openai](https://python.langchain.com/) | OpenAI 兼容 LLM 调用 |
| [pydantic](https://docs.pydantic.dev/) | 数据校验 |
| [streamlit](https://streamlit.io/) | 仪表盘 |
| [pyarrow](https://arrow.apache.org/docs/python/) | Parquet 读写 |

## 开发

```bash
# Lint
ruff check .
ruff format .

# 测试
pytest                                    # 全部
pytest tests/test_analyzer_node.py        # 单文件
pytest -k "confidence"                    # 关键字筛选
```

### 设计原则

- **LLM 只在策略决策 Agent 调用一次**，其他 Agent 全部纯代码
- 评分函数输出 -2 ~ +2，代码计算，非 LLM 主观判断
- 每条数据标注 `source` / `fetched_at` / `raw_value`
- 数据存储用 Parquet，不用数据库
- 日期格式统一 `YYYYMMDD`，股票代码格式 `600519.SH`

详见 `docs/` 目录下的设计决策和架构文档。

## License

MIT
