## Parent

PRD：行情分析 Agent (`team-spec/prd/2026-05-30-market-analyzer-agent.md`)

## What to build

创建 `src/analyzer/` 模块骨架，定义 Pydantic 输出模型，创建评分阈值配置文件，验证 `pandas-ta` 兼容性。

1. **模块骨架**：创建 `src/analyzer/` 目录，含 `__init__.py`、`schemas.py`、`indicators.py`、`scoring.py`、`node.py`（空文件或 docstring）
2. **Pydantic 模型**：在 `schemas.py` 中定义 `DimensionScore(value: int, reason: str, data_sufficient: bool)` 和 `TechnicalReport(symbol: str, date: str, scores: dict[str, DimensionScore], indicators: dict, generated_at: str)`
3. **配置文件**：创建 `configs/scoring.yaml`，包含所有评分阈值（vol_ratio.confirm/weaken、pe.low_percentile/high_percentile、roe.high/low、yoy.high、capital_flow.days、lg_ratio.strong/weak、min_daily_rows）
4. **配置读取**：实现配置文件加载函数，评分函数通过该函数获取阈值
5. **pandas-ta 验证**：安装 `pandas-ta`，编写最小验证测试（import + 对 mock DataFrame 计算 MA 和 MACD），确认与 Python 3.11 + pandas 2.x 兼容

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `src/analyzer/` 目录存在，含 `__init__.py`、`schemas.py`、`indicators.py`、`scoring.py`、`node.py`
- [ ] `DimensionScore` 可实例化（value=-2~+2、reason、data_sufficient）
- [ ] `TechnicalReport` 可实例化并 `model_dump()` 返回完整 dict
- [ ] `configs/scoring.yaml` 包含所有阈值参数，可被 Python 代码读取
- [ ] `pandas-ta` 安装成功，验证测试通过（MA 和 MACD 对 mock DataFrame 计算正确）

## Blocked by

None — 可立即开始

## Notes

- `pandas-ta` 兼容性是 P1 风险，必须在本 issue 中验证。如不兼容，需在继续前解决（降级 pandas 或换用其他指标库）
- 配置文件格式选 YAML（与项目惯例一致，TOML 仅用于 pyproject.toml）
- `DimensionScore.value` 范围约束通过 Pydantic field validator 或 `model_config` 实现

## Publish Status

- Status: created
- Updated At: 2026-05-30T04:15:17Z
- GitHub Number: 11
- GitHub URL: https://github.com/yanheng799/financial/issues/11

## Implementation Notes

### 变更文件

- `src/analyzer/__init__.py` — 模块包标记
- `src/analyzer/schemas.py` — `DimensionScore`（含 field_validator 限制 value 在 [-2,+2]）、`TechnicalReport`、`load_scoring_config()` 配置加载函数
- `src/analyzer/indicators.py` — 空文件（issue #02 实现）
- `src/analyzer/scoring.py` — 空文件（issue #02-04 实现）
- `src/analyzer/node.py` — 空文件（issue #05 实现）
- `configs/scoring.yaml` — 全部评分阈值配置（vol_ratio/pe/roe/yoy/capital_flow/lg_ratio/min_daily_rows）
- `tests/test_analyzer_scaffolding.py` — 19 个行为测试
- `pyproject.toml` — 新增 `pandas-ta-classic>=0.6`、`pyyaml>=6.0` 依赖

### 设计决策

- **`pandas-ta` → `pandas-ta-classic`**：`pandas-ta` ≥ 0.4.67b0 要求 Python ≥ 3.12，与项目 Python 3.11 约束冲突。改用 `pandas-ta-classic`（v0.6.20），API 兼容（`import pandas_ta_classic as ta`，`ta.sma()`/`ta.macd()` 接口一致）
- **配置缓存**：`load_scoring_config()` 使用模块级缓存，避免重复读文件

## Acceptance Criteria Coverage

| AC | 测试 | 状态 |
|---|---|---|
| AC#1 src/analyzer/ 目录含 5 个文件 | `TestModuleStructure`（6 tests） | ✅ |
| AC#2 DimensionScore 可实例化，value 范围校验 | `TestDimensionScore`（5 tests） | ✅ |
| AC#3 TechnicalReport model_dump() 返回完整 dict | `TestTechnicalReport`（3 tests） | ✅ |
| AC#4 configs/scoring.yaml 含全部阈值可读取 | `TestScoringConfig`（3 tests） | ✅ |
| AC#5 pandas-ta 安装成功，MA/MACD 计算正确 | `TestPandasTaCompatibility`（2 tests） | ✅ |
