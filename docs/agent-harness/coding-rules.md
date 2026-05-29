# 编码规则

项目特有的编码约束。通用 Python 规范不重复，只写与惯例不同或容易出错的部分。

## 代码风格

- **行宽 120**，Ruff 规则集 `E/W/F/I/UP/B/SIM`，忽略 E501
- **first-party 包**：`src`（isort `known-first-party = ["src"]`）
- **import 排序**：stdlib → third-party → first-party（`src`），由 ruff isort 自动处理

## 设计原则

- **开闭原则（Open-Closed Principle）**：通过抽象和接口扩展功能，不修改已有模块内部实现。例如：
  - 新增数据源 → 实现 `DataSourceAdapter` 接口（如 `TushareAdapter`、`AkshareAdapter`），不改动已有 Adapter
  - 新增评分维度 → 新增 `score_xxx()` 函数并注册，不修改评分调度器
  - 新增 LLM provider → 通过配置文件切换，不改动调用代码
- **合理使用设计模式**：自然匹配场景时使用，不为用模式而用模式。项目中的典型场景：
  - **Adapter**：多数据源适配（`TushareAdapter` → `AkshareAdapter`）
  - **Strategy**：评分策略（三维独立评分函数）
  - **Template Method**：分段拉取流程（定义骨架，子类填充接口参数）
- **禁止遗留临时代码**：提交时不得包含 `# TODO`、`# HACK`、`# FIXME`、`# XXX`。未完成的功能必须拆到独立 issue，不留占位符或桩代码

## 数据相关硬规则

1. **可追溯性三字段**：每条从 Tushare 获取的数据必须附加 `source`（如 `"tushare:daily"`）、`fetched_at`（ISO 8601）、`raw_value`（该行完整 JSON 字符串）。不事后补。
2. **Pydantic 校验在采集出口**：脏数据在 `collector/schemas.py` 中拦截，不进入 `analyzer/` 等下游模块。
3. **日期格式统一 `YYYYMMDD`**：字符串形式，不做 datetime 对象转换。
4. **股票代码内部格式**：始终带交易所后缀（`600519.SH`、`000001.SZ`、`920001.BJ`）。裸代码只在用户输入时出现，进入系统前必须补全。
5. **成交量单位**：Tushare `vol` 字段单位为千手，保持原值不转换，在 schema 注释中标注。

## LLM 相关硬规则

6. **LLM 只在 `strategist/` 调用**：其他三个 Agent 目录中不得出现 LLM API 调用。
7. **LLM 只看结构化输入**：传给 LLM 的数据必须是代码计算后的评分/标签/结论，不是原始 OHLCV 数字。
8. **评分由代码计算**：`-2 ~ +2` 整数，在 `analyzer/` 中用函数实现，不依赖 LLM 主观判断。
9. **置信度由维度一致性决定**：代码逻辑，不是 LLM 输出。

## 存储相关硬规则

10. **Parquet 不数据库**：落盘用 Parquet 文件，不引入 SQLite/MySQL/DuckDB。
11. **完整性优先**：分段拉取部分失败时不落盘，确保本地文件要么完整要么不存在。
12. **`data/` 目录不入 git**：已在 `.gitignore` 中排除。

## 测试相关规则

13. **单元测试不依赖真实 Token**：mock Tushare API 返回值，测试可在无 `TUSHARE_TOKEN` 环境下运行。
14. **测试放在 `tests/` 目录**：与 `src/` 平级，pytest `pythonpath = ["."]`。

## 禁止事项

- 禁止在代码中硬编码 Token
- 禁止让 LLM 计算技术指标数值
- 禁止在 `collector/` 中调用 LLM
- 禁止将 `data/` 目录提交到 git
- 禁止在 Phase 1 实现自动下单功能
