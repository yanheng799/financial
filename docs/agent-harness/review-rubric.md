# 自查与评审清单

每个 issue 实现完成后，提交前按此清单自查。

## 代码质量

- [ ] `ruff check .` 无报错
- [ ] `ruff format --check .` 无报错
- [ ] 无 `# TODO` 或 `# HACK` 注释遗留（除非已在 issue 中说明）
- [ ] import 排序正确（stdlib → third-party → src）

## 测试覆盖

- [ ] issue 中每条 Acceptance criteria 都有对应测试
- [ ] 测试不依赖真实 `TUSHARE_TOKEN`（使用 mock）
- [ ] `pytest -v` 全部通过
- [ ] 边界情况已覆盖（空数据、无效输入、API 失败）

## 数据质量（涉及数据采集时）

- [ ] 每条数据包含 `source`、`fetched_at`、`raw_value` 三字段
- [ ] 数据已按日期降序排序
- [ ] 主键已去重
- [ ] Parquet 文件路径符合 `data/{维度}/{ts_code}_{接口名}.parquet` 规范

## 架构一致性

- [ ] 新代码在正确的模块目录中（`collector/` / `analyzer/` / `strategist/` / `publisher/`）
- [ ] 没有跨模块职责泄漏（collector 不算指标，analyzer 不调 API）
- [ ] Pydantic 模型定义在 `schemas.py` 中，不在业务逻辑文件中
- [ ] State 类型使用 `TypedDict`，数据模型使用 `Pydantic BaseModel`

## 设计决策合规

- [ ] 未违反 `docs/设计决策.md` 中的 11 项决策
- [ ] 未引入 Phase 2 才需要的功能（AKShare、情绪面、自动下单等）
- [ ] `daily_basic` 数据归入 `fundamental` 而非 `daily`

## 文档更新

- [ ] 如果新增了 Pydantic 模型，`docs/agent-harness/architecture-map.md` 已同步
- [ ] 如果发现了新的失败模式，`docs/agent-harness/known-failures.md` 已记录
- [ ] 如果命令有变化，`docs/agent-harness/commands.md` 已更新
