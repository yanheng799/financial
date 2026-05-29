# 验证策略

按变更类型定义最低验证要求。每次提交前必须通过对应验证。

## 最低验证矩阵

| 变更类型 | 最低验证 | 完整验证 |
|---|---|---|
| 新增 Pydantic 模型 / schema | `ruff check .` + 对应测试 | `pytest` |
| 新增 Tushare API 调用 | `ruff check .` + mock 测试 | `pytest` + 手工用真实 Token 跑一次 |
| 修改存储/缓存逻辑 | `ruff check .` + 存储测试 | `pytest` + 检查 `data/` 目录文件结构 |
| 新增 LangGraph 节点 | `ruff check .` + 节点测试 | `pytest` + 端到端跑通 StateGraph |
| 修改配置文件 | 确认 `pip install -e .` 无报错 | `pytest` |
| 修改文档 | 无自动验证 | 人工审读 |

## 验证命令速查

```bash
# 快速检查（< 10 秒）
ruff check . && ruff format --check .

# 标准验证（< 30 秒）
ruff check . && ruff format --check . && pytest -v

# 完整回归（含真实 API，需 TUSHARE_TOKEN）
ruff check . && ruff format --check . && pytest -v && python -m src.collector --verify-e2e
```

## 不可自动验证的检查项

以下需要人工或代码审查时确认：

1. **Parquet 文件结构**：检查 `data/` 下文件路径是否符合 `data/{维度}/{ts_code}_{接口名}.parquet` 规范
2. **可追溯性三字段**：用 Pandas 读取 Parquet，确认每行包含 `source`、`fetched_at`、`raw_value`
3. **数据准确性**：随机抽查数据点与 Tushare 网页端交叉验证
4. **缓存行为**：确认第二次运行不调 API（可通过日志或 mock 计数验证）
5. **降级行为**：`moneyflow` 权限不足时不阻塞其他维度

## Issue 完成验证流程

每个 issue 实现后按以下步骤验证：

1. `ruff check --fix . && ruff format .` — 确保代码风格通过
2. `pytest -v` — 确保全部测试通过
3. 检查 issue 中的每条 Acceptance criteria 是否满足
4. 如果涉及 API 调用，用真实 Token 跑一次手工验证
