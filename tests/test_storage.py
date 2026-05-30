"""Issue #4 测试：Parquet 存储与缓存——落盘、读取、缓存策略"""

import os
from unittest.mock import MagicMock, patch

import pandas as pd

from src.collector.schemas import CapitalFlowData, DailyQuoteData, FundData, RawData

# ── 共享测试数据 ──────────────────────────────────────────


def _sample_daily_rows():
    return [
        {
            "ts_code": "600519.SH",
            "trade_date": "20260102",
            "open": 1800.0,
            "high": 1810.0,
            "low": 1795.0,
            "close": 1805.0,
            "vol": 50000.0,
            "amount": 9000000.0,
            "source": "tushare:daily",
            "fetched_at": "2026-05-30",
            "raw_value": '{"ts_code": "600519.SH", "trade_date": "20260102"}',
        },
    ]


def _sample_daily_basic_rows():
    return [
        {
            "ts_code": "600519.SH",
            "trade_date": "20260102",
            "pe": 30.5,
            "pe_ttm": 31.0,
            "pb": 10.2,
            "turnover_rate": 0.8,
            "source": "tushare:daily_basic",
            "fetched_at": "2026-05-30",
            "raw_value": '{"ts_code": "600519.SH"}',
        },
    ]


def _sample_fina_indicator_rows():
    return [
        {
            "ts_code": "600519.SH",
            "ann_date": "20260430",
            "end_date": "20260331",
            "roe": 0.31,
            "source": "tushare:fina_indicator",
            "fetched_at": "2026-05-30",
            "raw_value": "{}",
        },
    ]


def _sample_income_rows():
    return [
        {
            "ts_code": "600519.SH",
            "ann_date": "20260430",
            "end_date": "20260331",
            "total_revenue": 500000000000,
            "source": "tushare:income",
            "fetched_at": "2026-05-30",
            "raw_value": "{}",
        },
    ]


def _sample_moneyflow_rows():
    return [
        {
            "ts_code": "600519.SH",
            "trade_date": "20260102",
            "net_mf_amount": 30000.0,
            "source": "tushare:moneyflow",
            "fetched_at": "2026-05-30",
            "raw_value": "{}",
        },
    ]


def _sample_raw_data():
    return RawData(
        daily=DailyQuoteData(data=_sample_daily_rows()),
        fundamental=FundData(
            daily_basic=_sample_daily_basic_rows(),
            fina_indicator=_sample_fina_indicator_rows(),
            income=_sample_income_rows(),
        ),
        capital=CapitalFlowData(data=_sample_moneyflow_rows(), insufficient=False),
    )


def _sample_raw_data_insufficient():
    return RawData(
        daily=DailyQuoteData(data=_sample_daily_rows()),
        fundamental=FundData(
            daily_basic=_sample_daily_basic_rows(),
            fina_indicator=_sample_fina_indicator_rows(),
            income=_sample_income_rows(),
        ),
        capital=CapitalFlowData(data=None, insufficient=True),
    )


# ── 行为 1：Parquet 写入与读取 ─────────────────────────────


class TestParquetWriteAndRead:
    """storage.save_all 写入 Parquet，storage.load 读回数据"""

    def test_save_creates_parquet_files(self, tmp_path):
        from src.collector.storage import save_all

        save_all(_sample_raw_data(), base_dir=tmp_path)

        assert (tmp_path / "daily" / "600519.SH.parquet").is_file()
        assert (tmp_path / "fundamental" / "600519.SH_daily_basic.parquet").is_file()
        assert (tmp_path / "fundamental" / "600519.SH_fina_indicator.parquet").is_file()
        assert (tmp_path / "fundamental" / "600519.SH_income.parquet").is_file()
        assert (tmp_path / "capital" / "600519.SH.parquet").is_file()

    def test_saved_files_contain_traceability_columns(self, tmp_path):
        from src.collector.storage import save_all

        save_all(_sample_raw_data(), base_dir=tmp_path)

        df = pd.read_parquet(tmp_path / "daily" / "600519.SH.parquet")
        assert "source" in df.columns
        assert "fetched_at" in df.columns
        assert "raw_value" in df.columns

    def test_load_returns_raw_data(self, tmp_path):
        from src.collector.storage import load, save_all

        save_all(_sample_raw_data(), base_dir=tmp_path)
        loaded = load("600519.SH", base_dir=tmp_path)

        assert isinstance(loaded, RawData)
        assert len(loaded.daily.data) == 1
        assert loaded.daily.data[0].trade_date == "20260102"
        assert len(loaded.fundamental.daily_basic) == 1
        assert len(loaded.fundamental.fina_indicator) == 1
        assert len(loaded.fundamental.income) == 1
        assert loaded.capital.insufficient is False

    def test_insufficient_capital_writes_no_file(self, tmp_path):
        from src.collector.storage import save_all

        save_all(_sample_raw_data_insufficient(), base_dir=tmp_path)

        assert (tmp_path / "daily" / "600519.SH.parquet").is_file()
        assert not (tmp_path / "capital" / "600519.SH.parquet").is_file()

    def test_load_insufficient_capital(self, tmp_path):
        from src.collector.storage import load, save_all

        save_all(_sample_raw_data_insufficient(), base_dir=tmp_path)
        loaded = load("600519.SH", base_dir=tmp_path)

        assert loaded.capital.insufficient is True
        assert loaded.capital.data is None


# ── 行为 2：缓存判断 ──────────────────────────────────────


class TestCacheCheck:
    """is_cached 检查本地是否已有全部必要文件"""

    def test_not_cached_when_no_files(self, tmp_path):
        from src.collector.storage import is_cached

        assert is_cached("600519.SH", base_dir=tmp_path) is False

    def test_not_cached_when_partial_files(self, tmp_path):
        from src.collector.storage import is_cached

        # Only save daily, missing fundamental and capital
        raw = _sample_raw_data()
        from src.collector.storage import _save_daily

        _save_daily(raw.daily, base_dir=tmp_path)

        assert is_cached("600519.SH", base_dir=tmp_path) is False

    def test_cached_when_all_files_exist(self, tmp_path):
        from src.collector.storage import is_cached, save_all

        save_all(_sample_raw_data(), base_dir=tmp_path)

        assert is_cached("600519.SH", base_dir=tmp_path) is True

    def test_cached_when_capital_insufficient_but_others_present(self, tmp_path):
        """资金流 insufficient 时不需要 capital 文件"""
        from src.collector.storage import is_cached, save_all

        save_all(_sample_raw_data_insufficient(), base_dir=tmp_path)

        # daily + fundamental 存在, capital 不存在但 insufficient
        assert is_cached("600519.SH", base_dir=tmp_path) is True


# ── 行为 3：fetch_all 缓存集成 ────────────────────────────


class TestFetchAllCaching:
    """fetch_all 先检查缓存，force_refresh 跳过缓存"""

    def test_fetch_all_uses_cache(self, tmp_path):
        """本地有全部文件时 fetch_all 不调 API"""
        from src.collector.adapter import TushareAdapter
        from src.collector.storage import save_all

        save_all(_sample_raw_data(), base_dir=tmp_path)

        mock_pro = MagicMock()
        with (
            patch.dict(os.environ, {"TUSHARE_TOKEN": "test_token"}, clear=False),
            patch("tushare.pro_api", return_value=mock_pro),
            patch("src.collector.adapter._get_data_dir", return_value=tmp_path),
        ):
            adapter = TushareAdapter()
            result = adapter.fetch_all("600519.SH")

        # API 不应该被调用
        mock_pro.daily.assert_not_called()
        assert isinstance(result, RawData)
        assert len(result.daily.data) == 1

    def test_fetch_all_calls_api_when_no_cache(self, tmp_path):
        """本地无文件时 fetch_all 调 API 并落盘"""
        from src.collector.adapter import TushareAdapter

        mock_pro = MagicMock()
        mock_pro.daily.return_value = pd.DataFrame(_sample_daily_rows())
        mock_pro.daily_basic.return_value = pd.DataFrame(_sample_daily_basic_rows())
        mock_pro.fina_indicator.return_value = pd.DataFrame(_sample_fina_indicator_rows())
        mock_pro.income.return_value = pd.DataFrame(_sample_income_rows())
        mock_pro.moneyflow.return_value = pd.DataFrame(_sample_moneyflow_rows())

        with (
            patch.dict(os.environ, {"TUSHARE_TOKEN": "test_token"}, clear=False),
            patch("tushare.pro_api", return_value=mock_pro),
            patch("src.collector.adapter._get_data_dir", return_value=tmp_path),
        ):
            adapter = TushareAdapter()
            result = adapter.fetch_all("600519.SH")

        mock_pro.daily.assert_called()
        assert (tmp_path / "daily" / "600519.SH.parquet").is_file()
        assert isinstance(result, RawData)

    def test_fetch_all_force_refresh_overwrites(self, tmp_path):
        """force_refresh=True 时调 API 并覆盖本地文件"""
        from src.collector.adapter import TushareAdapter
        from src.collector.storage import save_all

        # 先写入旧数据
        save_all(_sample_raw_data(), base_dir=tmp_path)

        mock_pro = MagicMock()
        mock_pro.daily.return_value = pd.DataFrame(_sample_daily_rows())
        mock_pro.daily_basic.return_value = pd.DataFrame(_sample_daily_basic_rows())
        mock_pro.fina_indicator.return_value = pd.DataFrame(_sample_fina_indicator_rows())
        mock_pro.income.return_value = pd.DataFrame(_sample_income_rows())
        mock_pro.moneyflow.return_value = pd.DataFrame(_sample_moneyflow_rows())

        with (
            patch.dict(os.environ, {"TUSHARE_TOKEN": "test_token"}, clear=False),
            patch("tushare.pro_api", return_value=mock_pro),
            patch("src.collector.adapter._get_data_dir", return_value=tmp_path),
        ):
            adapter = TushareAdapter()
            result = adapter.fetch_all("600519.SH", force_refresh=True)

        mock_pro.daily.assert_called()
        assert isinstance(result, RawData)
