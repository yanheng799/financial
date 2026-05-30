"""Issue #1 测试：项目骨架 + State 定义 + Pydantic 模型 + 代码解析器"""

from pathlib import Path

import pytest

# ── 行为 1：项目目录结构和 State 定义 ──────────────────────


class TestProjectStructure:
    """src/collector/ 目录存在，含所需模块文件"""

    def test_collector_directory_exists(self):
        collector_dir = Path("src/collector")
        assert collector_dir.is_dir()

    @pytest.mark.parametrize("module_file", ["__init__.py", "adapter.py", "schemas.py", "storage.py"])
    def test_collector_module_files_exist(self, module_file):
        assert Path(f"src/collector/{module_file}").is_file()

    def test_state_module_exists(self):
        assert Path("src/state.py").is_file()

    def test_state_imports_successfully(self):
        from src.state import AnalysisState

        assert AnalysisState is not None

    def test_state_has_required_fields(self):
        from src.state import AnalysisState

        annotations = AnalysisState.__annotations__
        assert "symbol" in annotations
        assert "raw_data" in annotations
        assert "technical_report" in annotations
        assert "decision_report" in annotations
        assert "human_approved" in annotations


# ── 行为 2：Pydantic 数据模型 ──────────────────────────────


class TestPydanticSchemas:
    """RawData 等模型可正常实例化和 .model_dump()"""

    def test_daily_quote_data_creation(self):
        from src.collector.schemas import DailyQuoteData

        row = {
            "ts_code": "600519.SH",
            "trade_date": "20260529",
            "open": 1800.0,
            "high": 1860.0,
            "low": 1795.0,
            "close": 1850.0,
            "vol": 50000.0,
            "amount": 9250000.0,
            "source": "tushare:daily",
            "fetched_at": "2026-05-30T10:00:00+08:00",
            "raw_value": '{"ts_code": "600519.SH"}',
        }
        data = DailyQuoteData(data=[row])
        assert len(data.data) == 1
        assert data.data[0].close == 1850.0

    def test_fund_data_creation(self):
        from src.collector.schemas import FundData

        fund = FundData(
            daily_basic=[{"ts_code": "600519.SH", "trade_date": "20260529", "pe": 30.5}],
            fina_indicator=[{"ts_code": "600519.SH", "end_date": "20260331", "roe": 0.31}],
            income=[{"ts_code": "600519.SH", "end_date": "20260331", "total_revenue": 500000000000}],
        )
        assert len(fund.daily_basic) == 1
        assert len(fund.fina_indicator) == 1
        assert len(fund.income) == 1

    def test_capital_flow_data_creation(self):
        from src.collector.schemas import CapitalFlowData

        capital = CapitalFlowData(
            data=[{"ts_code": "600519.SH", "trade_date": "20260529", "net_mf_amount": -2300000.0}]
        )
        assert len(capital.data) == 1
        assert capital.insufficient is False

    def test_capital_flow_data_insufficient(self):
        from src.collector.schemas import CapitalFlowData

        capital = CapitalFlowData(data=None, insufficient=True)
        assert capital.data is None
        assert capital.insufficient is True

    def test_raw_data_creation_and_dump(self):
        from src.collector.schemas import (
            CapitalFlowData,
            DailyQuoteData,
            FundData,
            RawData,
        )

        raw = RawData(
            daily=DailyQuoteData(data=[]),
            fundamental=FundData(daily_basic=[], fina_indicator=[], income=[]),
            capital=CapitalFlowData(data=None, insufficient=False),
        )
        dumped = raw.model_dump()
        assert "daily" in dumped
        assert "fundamental" in dumped
        assert "capital" in dumped
        assert dumped["capital"]["insufficient"] is False


# ── 行为 3-7：股票代码解析器 ──────────────────────────────


class TestCodeParser:
    """代码补全函数：裸代码补全、已带后缀跳过、无效格式报错"""

    def test_shanghai_stock(self):
        from src.collector.schemas import normalize_symbol

        assert normalize_symbol("600519") == "600519.SH"

    def test_shenzhen_zero_prefix(self):
        from src.collector.schemas import normalize_symbol

        assert normalize_symbol("000001") == "000001.SZ"

    def test_shenzhen_three_prefix(self):
        from src.collector.schemas import normalize_symbol

        assert normalize_symbol("399005") == "399005.SZ"

    def test_beijing_stock(self):
        from src.collector.schemas import normalize_symbol

        assert normalize_symbol("920001") == "920001.BJ"

    def test_already_suffixed(self):
        from src.collector.schemas import normalize_symbol

        assert normalize_symbol("600519.SH") == "600519.SH"
        assert normalize_symbol("000001.SZ") == "000001.SZ"
        assert normalize_symbol("920001.BJ") == "920001.BJ"

    def test_invalid_code_raises(self):
        from src.collector.schemas import normalize_symbol

        with pytest.raises(ValueError, match="无法识别"):
            normalize_symbol("1234567")

    def test_empty_code_raises(self):
        from src.collector.schemas import normalize_symbol

        with pytest.raises(ValueError, match="无法识别"):
            normalize_symbol("")
