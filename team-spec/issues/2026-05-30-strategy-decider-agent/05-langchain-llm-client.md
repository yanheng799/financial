## Parent

PRD：策略决策 Agent (`team-spec/prd/2026-05-30-strategy-decider-agent.md`)

## What to build

实现 LangChain LLM client 封装，处理配置读取、provider 初始化、重试逻辑和错误处理。

1. **配置读取**：从 `configs/llm.yaml` 读取 provider/model/base_url/api_key_env/temperature/max_tokens
2. **LangChain ChatOpenAI 实例**：用 `base_url` 和 `api_key` 创建 `ChatOpenAI` 实例
3. **重试机制**：对网络超时/HTTP 429 自动重试（LangChain 内置 retry）；参数错误（401/403）不重试
4. **结构化输出**：可选——使用 `ChatOpenAI.with_structured_output(DecisionReport)` 让 LLM 直接返回 Pydantic 模型
5. **错误映射**：将 LangChain/httpx 异常映射为结构化错误（`llm_auth`/`llm_parse_error`/`llm_network`）

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] Given `configs/llm.yaml` 有效，When 创建 LLM client，Then `ChatOpenAI` 实例的 `model_name`、`base_url`、`temperature` 与配置一致
- [ ] Given 网络超时（mock HTTP），When 调用 `llm.invoke()`，Then 重试最多 2 次，仍失败抛异常
- [ ] Given HTTP 401，When 调用 `llm.invoke()`，Then 不重试，返回 `error_type: "llm_auth"`
- [ ] Given LLM 返回合法 JSON 但不合 schema，When 使用 `with_structured_output()`，Then 捕获 `OutputParserException`
- [ ] `api_key` 从环境变量读取，不在代码或配置中明文

## Blocked by

- #1（Scaffolding, models, config）

## Notes

- `langchain-openai` 的 `ChatOpenAI` 兼容 DeepSeek/Qwen 的 OpenAI 兼容端点
- 使用 `ChatOpenAI.with_structured_output(method="json_mode")` 或 `function_calling` 均可，推荐 `json_mode`
- 如 `with_structured_output` 验证效果不好，issue #6 可退回到手动 `model_validate`

## Publish Status

- Status: created
- Updated At: 2026-05-30T05:47:48Z
- GitHub Number: 24
- GitHub URL: https://github.com/yanheng799/financial/issues/24
