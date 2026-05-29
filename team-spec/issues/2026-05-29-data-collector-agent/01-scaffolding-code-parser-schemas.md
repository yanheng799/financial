## Parent

PRD：数据采集 Agent (`team-spec/prd/2026-05-29-data-collector-agent.md`)

## What to build

搭建数据采集 Agent 的基础工程骨架，包括：

1. **项目目录结构**：创建 `src/collector/`（adapter.py、schemas.py、storage.py）、`src/state.py`、`data/` 目录、`.gitignore` 更新
2. **共享 State 定义**：在 `src/state.py` 中定义 `AnalysisState`（TypedDict），含 `symbol`、`raw_data`、`technical_report`、`decision_report`、`human_approved` 五个字段
3. **Pydantic 数据模型**：在 `src/collector/schemas.py` 中定义 `RawData`、`DailyQuoteData`、`FundData`、`CapitalFlowData` 四个 BaseModel，其中 `FundData` 包含 `daily_basic`、`fina_indicator`、`income` 三个独立列表字段，`CapitalFlowData` 含 `insufficient` 降级标记
4. **股票代码解析器**：实现代码补全函数，接受裸代码（如 `600519`）或完整代码（如 `600519.SH`），按规则补全交易所后缀（6→.SH、0/3→.SZ、9→.BJ），拒绝无效格式

完成后，可通过 `import` 验证模块加载，通过单元测试验证代码补全逻辑和 schema 校验。

## Type

AFK（可独立执行，无需人工决策）

## Acceptance criteria

- [ ] `src/collector/` 目录存在，含 `__init__.py`、`adapter.py`、`schemas.py`、`storage.py`
- [ ] `src/state.py` 定义 `AnalysisState` TypedDict，可被 LangGraph 使用
- [ ] `RawData` 等 Pydantic 模型可正常实例化和 `.model_dump()`
- [ ] Given 输入 `600519`，When 调用代码补全函数，Then 返回 `600519.SH`
- [ ] Given 输入 `000001`，When 调用代码补全函数，Then 返回 `000001.SZ`
- [ ] Given 输入 `920001`，When 调用代码补全函数，Then 返回 `920001.BJ`
- [ ] Given 输入 `600519.SH`（已带后缀），When 调用代码补全函数，Then 跳过补全，返回 `600519.SH`
- [ ] Given 输入 `1234567`（无法识别的格式），When 调用代码补全函数，Then 返回明确错误
- [ ] `data/` 目录已加入 `.gitignore`

## Blocked by

- None — can start immediately

## Notes

- `src/collector/storage.py` 本 issue 只创建空文件，存储逻辑在 #4 实现
- `src/collector/adapter.py` 本 issue 只创建空文件，API 调用逻辑在 #2 实现
- 后续加 AKShare 时只需新增 `src/collector/akshare_adapter.py`，架构不用改

## Publish Status

- Status: created
- Updated At: 2026-05-29T14:40:29Z
- GitHub Number: 1
- GitHub URL: https://github.com/yanheng799/financial/issues/1
