## Parent

PRD：报告推送 Agent (`team-spec/prd/2026-05-30-report-publisher-agent.md`)

## What to build

实现 `report_publisher_agent(state)` 节点函数：从 `technical_report` + `decision_report` 组装 `AnalysisReport` → Parquet 落盘 → 返回结果或 error。

1. 读取 `symbol`、`technical_report`、`decision_report`
2. 组装 `AnalysisReport`（含 `raw_data_paths` 反推）
3. `mkdir -p data/reports/` + 写入 `{symbol}_{YYYYMMDDTHHMMSS}.parquet`
4. 落盘成功返回 `{"report_path": "..."}`
5. 落盘失败返回 `{"error": {"error_type": "storage", "message": "..."}}`

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given mock `technical_report` + `decision_report`（含三维评分 + LLM 研判），When `report_publisher_agent(state)`，Then `data/reports/{symbol}_{datetime}.parquet` 存在
- [ ] Parquet 内容包含 `AnalysisReport` 全部 14 个字段
- [ ] Given Parquet 写入失败（mock `to_parquet` 抛异常），When 执行，Then 返回 `error_type: "storage"`
- [ ] `raw_data_paths` 中不存在的文件值为 `None`
- [ ] 既有测试全部通过

## Blocked by

- #1（`01-scaffolding-analysis-report` — AnalysisReport 模型）

## Notes

- 文件名 `datetime` 格式：`datetime.now().strftime("%Y%m%dT%H%M%S")`
- `indicators` 从 `technical_report.indicators` 原样取
- `scores` 从 `decision_report.scores` 取（已由策略决策 Agent 转为 ScoreEntry）

## Publish Status

- Status: created
- GitHub Number: 45
- GitHub URL: https://github.com/yanheng799/financial/issues/45
