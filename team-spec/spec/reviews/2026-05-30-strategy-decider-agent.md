# 规格评审：策略决策 Agent

**评审对象**：`team-spec/spec/refine/2026-05-30-strategy-decider-agent.md`
**评审日期**：2026-05-30
**Status**：ready

## 结论

P0（LLM prompt 置信度冲突）和 P1（缩减后置信度规则缺失、auto_approve 传递机制未定义）已修正：`confidence_level` 从 prompt 移除改为代码注入；置信度表覆盖 3/2/1/0 全部维度数；`auto_approve` 放入 `configs/llm.yaml`。剩余 P2/P3 风险不阻塞 PRD 固化。规格可以进入 `team-spec-to-prd`。

## 阻塞项

无。

## 风险清单

| 等级 | 风险 | 触发条件 | 影响 | 证据/缺口 | 建议动作 | Owner | 截止点 |
|---|---|---|---|---|---|---|---|
| P2 | LLM 返回 JSON 格式不稳定 | LLM 输出不规范 | Pydantic 校验失败，触发重试 | 温度 0.1 + `Literal` 约束已缓解 | PRD 验收标准覆盖 | yanhe | 实现时 |
| P2 | `bearish_factor` 被 LLM 敷衍 | LLM 输出"无"或泛泛而谈 | 反向风险分析失效 | Prompt 已要求"必须指出一条具体反向因素" | PRD 验收标准明确验证 | yanhe | 实现时 |
| P2 | `indicators` 字段过多导致 token 超限 | 13 个键+描述超 token 上限 | LLM 调用失败 | 细化文档仅提缓解方向未具体定义 | PRD 中定义截断策略（优先保留评分相关键） | yanhe | PRD 编写时 |
| P2 | `NodeInterrupt` 无 checkpointer 时的行为 | `auto_approve=False` 且无 checkpointer | 运行时异常 | `auto_approve=True` 时不会触发，开发时可验证 | 开发启动时验证 | yanhe | 实现时 |
| P3 | LLM mock 测试策略未定义 | 自动化测试依赖 LLM API | 测试不可靠或有外部依赖 | 现有 mock 模式可扩展至 LLM API | PRD 测试决策章节说明 | — | 实现时 |

## Questions For User

1. **`overall_judgment` 允许哪些值？** 当前系统设计文档写"乐观/中性/谨慎"，但 JSON 示例出现了"中性偏谨慎"。是否允许 LLM 自由组合（如"中性偏乐观"），还是严格限制为固定枚举？推荐固定枚举：`"乐观" | "中性" | "谨慎" | "中性偏谨慎" | "中性偏乐观"`。

## Required Refinement

需要更新 `team-spec/spec/refine/2026-05-30-strategy-decider-agent.md` 的以下章节：

1. **LLM Prompt 结构**（第 80-112 行）：从 JSON 模板中移除 `"confidence_level"` 字段，标注该字段由代码注入
2. **置信度计算**（第 114-122 行）：补充缩减维度后的规则（2 维/1 维/0 维时的处理）
3. **输出 Schema**（第 134-155 行）：`confidence_level` 加注释说明"代码填充"；`overall_judgment` 改为 `Literal` 类型
4. **human_review 节点**（第 50-54 行）：明确 `auto_approve` 的传递机制

## 建议改写

### 置信度计算（修正后）

| 有效维度数 | 置信度 | 条件 |
|---|---|---|
| 3 | 高 | 3 维方向一致 |
| 3 | 中 | 2 维方向一致 |
| 3 | 低 | 3 维方向各不相同，或任意两维得分差 ≥ 2 |
| 2 | 高 | 2 维方向一致 |
| 2 | 低 | 2 维方向不一致 |
| 1 | 低 | 唯一有效维度 |
| 0 | N/A | 不执行 LLM，返回错误 |

`data_sufficient=False` 的维度不参与一致性计算。方向：正（>0）、负（<0）、零（=0）。

## Change Log

- 2026-05-30：初始评审。发现 P0（LLM prompt 置信度冲突）和 P1（缩减后置信度规则缺失）。Status: needs refinement。
