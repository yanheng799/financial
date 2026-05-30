## Parent

PRD：报告推送 Agent (`team-spec/prd/2026-05-30-report-publisher-agent.md`)

## What to build

实现 `app.py` —— Streamlit 独立入口，驱动四 Agent 全链路执行并展示分析报告。

1. **输入**：股票代码输入框 + "开始分析"按钮
2. **执行**：`st.spinner` 显示进度 → 逐图 invoke collector → analyzer → strategist → 检查 `decision_report` → publisher
3. **展示**：三维评分表（`st.dataframe`）+ 指标数值表 + LLM 研判（`st.markdown`）
4. **历史**：下拉菜单列出 `data/reports/{symbol}_*.parquet`，选择后展示历史报告
5. **错误**：`state["error"]` 不为空时展示错误信息

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `streamlit run app.py` 可正常启动
- [ ] 输入 `600519` 点击分析 → 页面展示三维评分表 + 指标表 + LLM 研判
- [ ] 历史下拉列出该股票的所有历史分析，选择后切换展示
- [ ] 上游出错时（如无效代码），页面展示 error 信息而非崩溃
- [ ] `human_approved=False` 时，页面展示拒绝提示

## Blocked by

- #3（`03-publisher-graph` — `build_publisher_graph()` 可 invoke）
- Streamlit 已安装（`pip install streamlit`）

## Notes

- `app.py` 不在 LangGraph 图中，独立入口
- 逐图 invoke 模式：每次 `invoke` 返回更新后的 state 作为下一个图的输入
- `streamlit` 加入 `pyproject.toml` dev 依赖
- 不需要 CSS/Jinja，用 `st.dataframe` + `st.markdown` 即可
- 参考 Streamlit 模式：单页应用，无路由

## Publish Status

- Status: created
- GitHub Number: 47
- GitHub URL: https://github.com/yanheng799/financial/issues/47
