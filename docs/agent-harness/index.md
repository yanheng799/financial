# Agent Harness 总入口

**最后更新**: 2026-05-30
**更新原因**: 数据采集 Agent 已实现；为行情分析 Agent 做准备（更新架构地图、commands、debt）

## Agent 执行任务前必须阅读

1. `CLAUDE.md` — 项目入口（必读）
2. 本文件 — harness 文档地图
3. `docs/agent-harness/commands.md` — 所有可执行命令
4. `docs/agent-harness/verification.md` — 变更后如何验证

## 按任务类型选择文档

| 任务类型 | 额外必读 |
|---|---|
| 实现新 Agent 模块 | `docs/agent-harness/architecture-map.md` + 对应 PRD |
| 修改已有模块 | `docs/agent-harness/coding-rules.md` + `docs/agent-harness/review-rubric.md` |
| 修复 bug | `docs/agent-harness/known-failures.md` |
| 环境搭建/依赖问题 | `docs/agent-harness/commands.md` + `docs/agent-harness/harness-debt.md` |

## 文档地图

```
docs/agent-harness/
├── index.md              ← 本文件
├── commands.md           # 安装、测试、lint、运行命令
├── verification.md       # 变更类型 → 验证策略
├── architecture-map.md   # 模块边界、代码入口、数据流
├── coding-rules.md       # 项目特有编码约束
├── review-rubric.md      # 实现完成前自查清单
├── known-failures.md     # 已知失败模式
└── harness-debt.md       # 阻碍 agent 独立工作的缺口
```

## 外部文档索引

| 文档 | 路径 | 用途 |
|---|---|---|
| 设计决策 | `docs/设计决策.md` | 11 项必须遵守的决策 |
| 系统设计 | `docs/A股分析Agent系统设计.md` | 四 Agent 架构、评分规则、State schema |
| 需求要点 | `docs/炒股Agent需求要点.md` | 技术栈、Phase 范围、启动路线图 |
| Tushare Skill | `.agents/skills/tushare/SKILL.md` | 接口映射、工作流模板 |
| Tushare 接口目录 | `.agents/skills/tushare/references/数据接口.md` | 237 个 API 接口 |
| PRD / Issues | `team-spec/prd/`、`team-spec/issues/` | 工程任务定义 |
