# Harness Debt

阻碍 agent 独立工作的缺口。每条必须含证据、影响和建议处理方式。

---

## DEBT-001：dev 依赖未安装

- **证据**：`.venv/Scripts/pip list` 输出中无 pytest、ruff、pandas-ta、streamlit
- **影响**：agent 无法运行测试、无法 lint、无法验证实现。这是最高优先级阻塞项。
- **建议处理**：执行 `pip install -e ".[dev]"` 安装 pytest + ruff，再 `pip install pandas-ta streamlit` 安装后续所需依赖。同时更新 `pyproject.toml` 的 `dependencies` 列表加入 `pandas-ta` 和 `streamlit`。
- **优先级**：P0 — 阻塞所有 issue 实现
- **建议转入 team-tech-debt-refine**：否（直接安装即可解决）

## DEBT-002：`tests/` 目录不存在

- **证据**：`ls tests/` 返回目录不存在
- **影响**：pytest 配置了 `testpaths = ["tests"]`，但目录不存在。agent 实现 issue #1 时需手动创建。
- **建议处理**：在 issue #1 实现时创建 `tests/` 目录和 `tests/__init__.py`。
- **优先级**：P2 — issue #1 实现时自然解决
- **建议转入 team-tech-debt-refine**：否

## DEBT-003：Tushare 积分覆盖范围未知

- **证据**：`moneyflow` 接口可能需要较高积分。PRD 开放问题中已记录，但尚未验证。
- **影响**：如果积分不足，issue #3 的 `moneyflow` 测试会失败，资金面持续为空，三维评分降为二维。
- **建议处理**：在实现 issue #3 前手动验证 `moneyflow` 接口是否可用（运行 demo 脚本测试）。
- **优先级**：P2 — issue #3 实现前验证
- **建议转入 team-tech-debt-refine**：否（需要人工验证）

## DEBT-004：`data/` 目录和 `.gitignore` 未创建

- **证据**：项目根目录无 `data/` 目录，`.gitignore` 不存在
- **影响**：issue #4（Parquet 存储）需要 `data/` 目录和 `.gitignore` 排除
- **建议处理**：在 issue #1 实现时创建 `.gitignore` 文件并加入 `data/`，创建 `data/daily/`、`data/fundamental/`、`data/capital/` 空目录（或让 storage.py 自动创建）。
- **优先级**：P2 — issue #1 或 #4 实现时自然解决
- **建议转入 team-tech-debt-refine**：否
