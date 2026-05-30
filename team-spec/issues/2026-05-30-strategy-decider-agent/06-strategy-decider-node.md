## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

实现 `strategy_decider_agent(state)` 节点函数，串联 prompt 构造 → LLM 调用 → Pydantic 校验 → 重试 → 置信度注入，完整输出 `DecisionReport`。

1. **读取输入**：从 `state["technical_report"]` 提取 scores 和 indicators
2. **调用依赖**：`compute_confidence()` → `to_score_entry()` → `build_prompt()` → LLM invoke → `DecisionReport.model_validate()`
3. **校验失败重试**：Pydantic 校验失败时，用更严格的 prompt（追加"上一次输出格式错误，请严格按 JSON 模板输出"）重试 1 次
4. **置信度注入**：校验通过后，将 `confidence_level` 字段设为 `compute_confidence()` 的返回值（覆盖 LLM 可能输出的任何值）
5. **写入 state**：将 `DecisionReport.model_dump()` 写入 `state["decision_report"]`
6. **错误处理**：`technical_report` 为空、LLM 调用失败、解析失败等场景返回结构化错误

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given mock LLM 返回合法 `DecisionReport` JSON，When 通过 `strategy_decider_agent` 执行，Then `state["decision_report"]` 包含全部 13 字段，`confidence_level` 为代码计算值
- [ ] Given mock LLM 返回非 JSON 字符串，When 执行，Then 重试 1 次后返回 `error_type: "llm_parse_error"`
- [ ] Given mock LLM 返回 JSON 但 `overall_judgment` 不在枚举中，When 执行，Then 重试 1 次后返回 `error_type: "llm_parse_error"`
- [ ] Given `technical_report` 为空 dict，When 执行，Then 返回 `error_type: "input"`
- [ ] Given 所有维度 `data_sufficient=False`，When 执行，Then 不调用 LLM，返回 `error_type: "input"`
- [ ] 代码计算出的 `confidence_level` 覆盖 LLM 返回的任何值

## Blocked by

- #2（Confidence + mapping）
- #4（Prompt construction）
- #5（LangChain LLM client）

## Notes

- 本 issue 是核心 vertical slice，串联 #2/#4/#5 的产出
- mock LLM 使用 `unittest.mock.patch` 或 LangChain 的 `FakeListChatModel` 均可
- 置信度注入在 `model_validate()` 之后、`model_dump()` 之前

## Publish Status

- Status: created
- Updated At: 2026-05-30T05:47:50Z
- GitHub Number: 25
- GitHub URL: https://github.com/yanheng799/financial/issues/25
