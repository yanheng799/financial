# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A 股分析 Agent 系统——基于 LangGraph 多 Agent 编排的单人本地工具。输入股票代码，产出技术面/基本面/资金面三维评分 + LLM 综合研判报告，通过 Streamlit 仪表盘展示。

**当前状态**：数据采集 Agent 已实现（`src/collector/`），行情分析 Agent 待实现（`src/analyzer/`）。

## Commands

```bash
# 安装（运行时）
pip install -e .

# 安装（含开发工具）
pip install -e ".[dev]"

# Lint
ruff check .
ruff format .

# 测试
pytest                    # 全部
pytest tests/test_foo.py  # 单文件

# 环境变量
export TUSHARE_TOKEN=your_token   # Tushare API 认证
```

## Architecture

四 Agent 流水线，LangGraph StateGraph 编排：

```
数据采集 Agent (纯代码) → 行情分析 Agent (纯代码) → 策略决策 Agent (LLM) → 报告推送 Agent (纯代码)
```

**关键约束**：
- **LLM 只在策略决策 Agent 调用一次**，其他三个 Agent 全部纯代码
- LLM 输入是代码预处理后的结构化 JSON（评分/标签/异常），**不让 LLM 碰原始数据计算**
- 评分函数输出 -2 ~ +2 整数，代码计算，非 LLM 主观判断
- 每条数据必须标注 `source`、`fetched_at`、`raw_value`
- 数据存储用 Parquet 文件，不用数据库

**Phase 1 范围**：单票全面分析，三维评分（技术面/基本面/资金面），仅 Tushare 数据源，Streamlit 交互驱动。

**Phase 2 预留**：情绪面维度（加 AKShare 舆情数据）、多票对比、板块分析。

## Tech Stack

| 组件 | 选型 | 用途 |
|---|---|---|
| 数据源 | Tushare | 日线/财报/资金流（Phase 1 唯一数据源） |
| Agent 编排 | LangGraph (≥1.2.2) | StateGraph + Checkpoint |
| 技术指标 | pandas-ta | MA/MACD/成交量比（待安装） |
| 数据校验 | Pydantic (≥2.0) | 数据采集出口校验 |
| 数据存储 | Parquet | Pandas 原生读写 |
| LLM | DeepSeek / Qwen | OpenAI 兼容协议，配置文件切换 |
| 交互界面 | Streamlit | 分析仪表盘（待安装） |

## Key References

- `docs/设计决策.md` — 11 项设计决策及理由（必须遵守）
- `docs/A股分析Agent系统设计.md` — 四 Agent 架构、评分规则、置信度分级、LangGraph State 定义、输出 JSON schema
- `docs/炒股Agent需求要点.md` — 技术栈确认、Phase 范围、启动路线图
- `.agents/skills/tushare/SKILL.md` — Tushare 接口映射、10 类意图识别、9 种工作流模板
- `.agents/skills/tushare/references/数据接口.md` — 237 个 Tushare API 接口目录

## Agent Harness

详细工作环境文档：`docs/agent-harness/`

| 文档 | 用途 |
|---|---|
| `commands.md` | 安装、测试、lint 命令（含前置条件） |
| `verification.md` | 变更后如何验证（按变更类型） |
| `architecture-map.md` | 模块边界、代码入口、数据流 |
| `coding-rules.md` | 项目特有编码约束和禁止事项 |
| `review-rubric.md` | issue 完成前自查清单 |
| `harness-debt.md` | 阻塞 agent 工作的缺口（含 P0：dev 依赖未安装） |

## Coding Conventions

- Python 3.11，行宽 120，Ruff 规则集 `E/W/F/I/UP/B/SIM`（忽略 E501）
- `src` 为 first-party package（isort `known-first-party = ["src"]`）
- 测试放在 `tests/`，pytest pythonpath 设为项目根
- 日期格式统一 `YYYYMMDD`
- 股票代码内部格式：`600519.SH`、`000001.SZ`、`920001.BJ`

### Design Principles

- **开闭原则（Open-Closed Principle）**：对扩展开放，对修改关闭。通过抽象基类、Protocol 或策略模式扩展功能（如新增数据源 Adapter、新增评分维度），不修改已有模块的内部实现
- **合理使用设计模式**：优先选择自然匹配场景的模式——Adapter（多数据源适配）、Strategy（评分策略切换）、Template Method（分段拉取流程）。不为用模式而用模式
- **禁止遗留临时代码**：提交时不得包含 `# TODO`、`# HACK`、`# FIXME`、`# XXX` 注释。功能必须完整实现或拆到独立 issue，不留占位符
