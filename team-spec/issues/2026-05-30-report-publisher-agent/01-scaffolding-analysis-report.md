## Parent

PRD：报告推送 Agent (`team-spec/prd/2026-05-30-report-publisher-agent.md`)

## What to build

创建 `src/publisher/` 模块骨架，定义 `AnalysisReport` Pydantic 模型和 `_build_raw_data_paths()` 路径反推函数。

1. **模块结构**：`src/publisher/__init__.py` + `src/publisher/schemas.py`
2. **`AnalysisReport` 模型**：汇总上游三维评分 + 指标 + LLM 研判 + `raw_data_paths`（复用 `ScoreEntry`）
3. **`_build_raw_data_paths(symbol)`**：通过已知目录结构反推原始数据路径，文件不存在时值为 `None`

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `src/publisher/__init__.py` 和 `src/publisher/schemas.py` 存在
- [ ] `AnalysisReport` 实例化后 `model_dump()` 包含全部 14 个字段
- [ ] `_build_raw_data_paths("600519.SH")` 返回 dict，文件存在时为路径字符串，不存在时为 `None`
- [ ] 既有测试全部通过

## Blocked by

- None - can start immediately

## Notes

- `ScoreEntry` 从 `src.strategist.schemas` import，不重复定义
- `raw_data_paths` 的 dict key 为 `daily`, `daily_basic`, `fina_indicator`, `income`, `moneyflow`
- 参考模型模式：`src/strategist/schemas.py` 的 `DecisionReport`

## Publish Status

- Status: created
- GitHub Number: 44
- GitHub URL: https://github.com/yanheng799/financial/issues/44
