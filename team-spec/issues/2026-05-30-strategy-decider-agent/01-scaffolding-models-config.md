## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

创建 `src/strategist/` 模块骨架，定义 Pydantic 输出模型，创建 `configs/llm.yaml`。

1. **模块骨架**：创建 `src/strategist/` 目录，含 `__init__.py`、`schemas.py`、`node.py`
2. **Pydantic 模型**：在 `schemas.py` 中定义 `ScoreEntry`（value/reason/confidence Literal）和 `DecisionReport`（全部 13 字段，含 Literal 约束）
3. **配置文件**：创建 `configs/llm.yaml`（provider/model/base_url/api_key_env/temperature/max_tokens/auto_approve）
4. **配置读取**：实现 `load_llm_config()` 函数
5. **依赖安装**：安装 `openai`、`langchain-openai`，验证可正常 import

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `src/strategist/` 目录存在，含 `__init__.py`、`schemas.py`、`node.py`
- [ ] `ScoreEntry(value=1, reason="...", confidence="determined")` 可实例化
- [ ] `ScoreEntry(confidence="invalid")` 抛出 `ValidationError`
- [ ] `DecisionReport` 可实例化并 `model_dump()` 返回完整 dict（含全部 13 字段）
- [ ] `DecisionReport(overall_judgment="坏")` 抛出 `ValidationError`
- [ ] `configs/llm.yaml` 存在且可被 `load_llm_config()` 读取，返回 dict 含所有键
- [ ] `openai` 和 `langchain-openai` 安装成功

## Blocked by

None — 可立即开始

## Notes

- `openai>=1.0` 和 `langchain-openai` 需加入 `pyproject.toml` 依赖
- `ScoreEntry.confidence` 使用 `Literal["determined", "insufficient", "deferred"]`
- `DecisionReport.overall_judgment` 使用 `Literal["乐观", "中性", "谨慎", "中性偏谨慎", "中性偏乐观"]`

## Publish Status

- Status: created
- Updated At: 2026-05-30T05:50:00Z
- GitHub Number: 27
- GitHub URL: https://github.com/yanheng799/financial/issues/27
