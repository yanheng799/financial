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

- **证据**：~~`ls tests/` 返回目录不存在~~ 已解决——`tests/` 目录已创建，含 5 个测试文件（72 个测试全部通过）。
- **状态**：**已解决**（2026-05-30）

## DEBT-003：Tushare 积分覆盖范围未知

- **证据**：`moneyflow` 接口可能需要较高积分。PRD 开放问题中已记录，但尚未验证。
- **影响**：如果积分不足，issue #3 的 `moneyflow` 测试会失败，资金面持续为空，三维评分降为二维。
- **建议处理**：在实现 issue #3 前手动验证 `moneyflow` 接口是否可用（运行 demo 脚本测试）。
- **优先级**：P2 — issue #3 实现前验证
- **建议转入 team-tech-debt-refine**：否（需要人工验证）

## DEBT-004：`data/` 目录和 `.gitignore` 未创建

- **证据**：~~项目根目录无 `data/` 目录，`.gitignore` 不存在~~ 已解决——`.gitignore` 已创建并排除 `data/`，`data/` 目录已存在含 Parquet 文件。
- **状态**：**已解决**（2026-05-30）

## DEBT-005：`pandas-ta` 未加入 pyproject.toml 依赖

- **证据**：`pyproject.toml` 的 `dependencies` 列表中无 `pandas-ta`，且 `pip show pandas-ta` 返回未安装
- **影响**：行情分析 Agent 的指标计算依赖 `pandas-ta`，不安装则无法实现 analyzer 模块
- **建议处理**：在 market-analyzer issue #01 实现前，将 `pandas-ta` 加入 `pyproject.toml` 的 `dependencies` 并 `pip install pandas-ta`。安装后需验证与 Python 3.11 + pandas 2.x 的兼容性。
- **优先级**：P1 — 阻塞行情分析 Agent issue #01
- **建议转入 team-tech-debt-refine**：否（直接安装即可解决）
