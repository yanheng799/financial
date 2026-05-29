# 常用命令

## 首次环境搭建

```bash
# 激活虚拟环境
source .venv/bin/activate       # Linux/Mac
.venv\Scripts\activate          # Windows

# 安装项目（运行时依赖）
pip install -e .

# 安装项目（含开发工具）—— 必须执行一次
pip install -e ".[dev]"

# 验证安装成功
python -c "import tushare; print('tushare', tushare.__version__)"
python -c "import langgraph; print('langgraph', langgraph.__version__)"
ruff --version
pytest --version
```

**前置条件**：Python ≥ 3.11，虚拟环境已创建（`.venv/` 已存在）。

## 环境变量

```bash
# 必须配置（Tushare API 认证）
export TUSHARE_TOKEN=your_token_here

# 验证
python -c "import os; print('Token set' if os.getenv('TUSHARE_TOKEN') else 'Token missing')"
```

**安全边界**：不要将 Token 写入代码或提交到 git。

## 日常开发

```bash
# Lint（检查代码问题）
ruff check .

# Lint（自动修复）
ruff check --fix .

# 格式化
ruff format .

# 一键 lint + format
ruff check --fix . && ruff format .
```

**适用场景**：每次提交前执行。耗时 < 5 秒。
**常见失败**：无。ruff 已在 pyproject.toml 配置。

## 测试

```bash
# 运行全部测试
pytest

# 运行单个测试文件
pytest tests/test_collector.py

# 运行单个测试函数
pytest tests/test_collector.py::test_code_parsing -v

# 显示详细输出
pytest -v

# 只跑失败的
pytest --lf
```

**适用场景**：实现每个 issue 后执行。
**前置条件**：`pip install -e ".[dev]"` 已执行，`tests/` 目录存在。
**常见失败**：
- `ModuleNotFoundError: No module named 'src'` → 确认 `pyproject.toml` 中 `pythonpath = ["."]` 生效，或重新 `pip install -e .`
- `TUSHARE_TOKEN not set` → 需要 mock Tushare API，不要依赖真实 Token 跑单元测试

## 运行 Demo 脚本

```bash
# 股票数据 demo（需要 TUSHARE_TOKEN）
python .agents/skills/tushare/scripts/stock_data_demo.py

# 基金数据 demo（需要 TUSHARE_TOKEN）
python .agents/skills/tushare/scripts/fund_data_demo.py
```

**适用场景**：验证 Tushare 连通性，测试 Token 是否有效。
**前置条件**：`TUSHARE_TOKEN` 已配置。

## 待安装的依赖（Issue #1 实现时需补充）

```bash
# pyproject.toml 已声明但尚未安装的包
pip install pandas-ta streamlit
```

后续应将这些加入 `pyproject.toml` 的 `dependencies` 列表。
