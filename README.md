# Financial

A 股金融数据研究工具，基于 [Tushare](https://tushare.pro) 提供行情、财务、资金流、板块、宏观等数据的获取与分析能力。

## 功能概览

- **行情 / 趋势** — 个股、指数、ETF 日线/周线/月线走势与区间统计
- **财务 / 估值** — 营收、利润、ROE、毛利率、PE/PB 等质量与估值指标
- **资金流 / 情绪** — 北向资金、主力资金、龙虎榜、板块资金流向
- **板块 / 主题** — 申万/同花顺/东方财富板块成分与轮动分析
- **公告 / 新闻** — 公司公告、研报、重大新闻梳理
- **宏观数据** — CPI、PPI、PMI、社融、利率、美股/港股跨市场数据
- **数据导出** — CSV / Parquet 格式输出，支持回测数据准备

## 环境要求

- Python ≥ 3.11
- [Tushare Token](https://tushare.pro/register)（用于数据接口认证）

## 快速开始

### 1. 安装

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装项目
pip install -e .

# 开发模式（含 linter 和测试工具）
pip install -e ".[dev]"
```

### 2. 配置 Token

```bash
export TUSHARE_TOKEN=your_token_here
```

### 3. 运行示例

```bash
# 股票数据示例
python .agents/skills/tushare/scripts/stock_data_demo.py

# 基金数据示例
python .agents/skills/tushare/scripts/fund_data_demo.py
```

## 项目结构

```
financial/
├── src/                        # 项目源码
│   └── __init__.py
├── .agents/skills/tushare/     # Tushare 技能定义与参考文档
│   ├── SKILL.md                # 技能说明（意图识别、接口映射、工作流模板）
│   ├── references/             # 数据接口文档
│   └── scripts/                # 数据获取示例脚本
│       ├── stock_data_demo.py
│       └── fund_data_demo.py
├── pyproject.toml              # 项目配置与依赖
└── skills-lock.json            # 技能版本锁定
```

## 核心依赖

| 包 | 用途 |
|---|---|
| [tushare](https://github.com/waditu/tushare) | A 股数据接口 |
| [pandas](https://pandas.pydata.org/) | 数据处理与分析 |
| [langgraph](https://github.com/langchain-ai/langgraph) | AI 工作流编排 |
| [pydantic](https://docs.pydantic.dev/) | 数据模型校验 |
| [httpx](https://www.python-httpx.org/) | HTTP 客户端 |

## 开发

### Lint

```bash
ruff check .
ruff format .
```

### 测试

```bash
pytest
```

## License

MIT
