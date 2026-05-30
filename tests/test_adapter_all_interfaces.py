"""Issue #3 测试：全部 5 个接口 + 分段拉取 + 降级处理 + fetch_all"""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.collector.schemas import CapitalFlowData, RawData

# ── 共享 mock 工厂 ──────────────────────────────────────────


def _make_daily_df(rows=None):
    if rows is None:
        rows = [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260102",
                "open": 1800.0,
                "high": 1810.0,
                "low": 1795.0,
                "close": 1805.0,
                "vol": 50000.0,
                "amount": 9000000.0,
            },
        ]
    return pd.DataFrame(rows)


def _make_daily_basic_df(rows=None):
    if rows is None:
        rows = [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260102",
                "pe": 30.5,
                "pe_ttm": 31.0,
                "pb": 10.2,
                "turnover_rate": 0.8,
            },
            {
                "ts_code": "600519.SH",
                "trade_date": "20260101",
                "pe": 30.0,
                "pe_ttm": 30.5,
                "pb": 10.1,
                "turnover_rate": 0.9,
            },
        ]
    return pd.DataFrame(rows)


def _make_fina_indicator_df(rows=None):
    if rows is None:
        rows = [
            {
                "ts_code": "600519.SH",
                "ann_date": "20260430",
                "end_date": "20260331",
                "roe": 0.31,
                "grossprofit_margin": 0.91,
                "netprofit_margin": 0.49,
                "debt_to_assets": 0.25,
            },
            {
                "ts_code": "600519.SH",
                "ann_date": "20260101",
                "end_date": "20251231",
                "roe": 0.30,
                "grossprofit_margin": 0.90,
                "netprofit_margin": 0.48,
                "debt_to_assets": 0.26,
            },
        ]
    return pd.DataFrame(rows)


def _make_income_df(rows=None):
    if rows is None:
        rows = [
            {
                "ts_code": "600519.SH",
                "ann_date": "20260430",
                "end_date": "20260331",
                "total_revenue": 500000000000,
                "revenue_yoy": 0.10,
                "n_income": 250000000000,
                "netprofit_yoy": 0.12,
            },
            {
                "ts_code": "600519.SH",
                "ann_date": "20260101",
                "end_date": "20251231",
                "total_revenue": 1900000000000,
                "revenue_yoy": 0.11,
                "n_income": 950000000000,
                "netprofit_yoy": 0.13,
            },
        ]
    return pd.DataFrame(rows)


def _make_moneyflow_df(rows=None):
    if rows is None:
        rows = [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260102",
                "buy_sm_amount": 100000.0,
                "sell_sm_amount": 90000.0,
                "buy_lg_amount": 500000.0,
                "sell_lg_amount": 480000.0,
                "net_mf_amount": 30000.0,
            },
        ]
    return pd.DataFrame(rows)


def _create_adapter():
    """创建 TushareAdapter 和绑定的 mock_pro，共享同一个 mock 上下文。"""
    from src.collector.adapter import TushareAdapter

    mock_pro = MagicMock()
    with (
        patch.dict(os.environ, {"TUSHARE_TOKEN": "test_token"}, clear=False),
        patch("tushare.pro_api", return_value=mock_pro),
    ):
        adapter = TushareAdapter()
    return adapter, mock_pro


# ── 行为 1：fina_indicator — 季频数据，按 end_date 去重降序 ──────


class TestFetchFinaIndicator:
    def test_returns_list_with_traceability(self):
        adapter, mock_pro = _create_adapter()
        mock_pro.fina_indicator.return_value = _make_fina_indicator_df()

        result = adapter.fetch_fina_indicator("600519.SH")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["source"] == "tushare:fina_indicator"
        assert result[0]["fetched_at"]
        assert result[0]["raw_value"]
        assert "600519.SH" in result[0]["raw_value"]

    def test_sorted_by_end_date_descending(self):
        rows = [
            {
                "ts_code": "600519.SH",
                "ann_date": "20260101",
                "end_date": "20251231",
                "roe": 0.30,
                "grossprofit_margin": 0.90,
                "netprofit_margin": 0.48,
                "debt_to_assets": 0.26,
            },
            {
                "ts_code": "600519.SH",
                "ann_date": "20260430",
                "end_date": "20260331",
                "roe": 0.31,
                "grossprofit_margin": 0.91,
                "netprofit_margin": 0.49,
                "debt_to_assets": 0.25,
            },
        ]
        adapter, mock_pro = _create_adapter()
        mock_pro.fina_indicator.return_value = _make_fina_indicator_df(rows)

        result = adapter.fetch_fina_indicator("600519.SH")

        dates = [r["end_date"] for r in result]
        assert dates == ["20260331", "20251231"]

    def test_deduplicates_by_ts_code_and_end_date(self):
        rows = [
            {
                "ts_code": "600519.SH",
                "ann_date": "20260430",
                "end_date": "20260331",
                "roe": 0.31,
                "grossprofit_margin": 0.91,
                "netprofit_margin": 0.49,
                "debt_to_assets": 0.25,
            },
            {
                "ts_code": "600519.SH",
                "ann_date": "20260430",
                "end_date": "20260331",
                "roe": 0.31,
                "grossprofit_margin": 0.91,
                "netprofit_margin": 0.49,
                "debt_to_assets": 0.25,
            },
        ]
        adapter, mock_pro = _create_adapter()
        mock_pro.fina_indicator.return_value = _make_fina_indicator_df(rows)

        result = adapter.fetch_fina_indicator("600519.SH")

        assert len(result) == 1


# ── 行为 2：income — 季频数据，按 end_date 去重降序 ──────────


class TestFetchIncome:
    def test_returns_list_with_traceability(self):
        adapter, mock_pro = _create_adapter()
        mock_pro.income.return_value = _make_income_df()

        result = adapter.fetch_income("600519.SH")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["source"] == "tushare:income"
        assert result[0]["fetched_at"]
        assert result[0]["raw_value"]

    def test_sorted_by_end_date_descending(self):
        rows = [
            {
                "ts_code": "600519.SH",
                "ann_date": "20260101",
                "end_date": "20251231",
                "total_revenue": 1900000000000,
                "revenue_yoy": 0.11,
                "n_income": 950000000000,
                "netprofit_yoy": 0.13,
            },
            {
                "ts_code": "600519.SH",
                "ann_date": "20260430",
                "end_date": "20260331",
                "total_revenue": 500000000000,
                "revenue_yoy": 0.10,
                "n_income": 250000000000,
                "netprofit_yoy": 0.12,
            },
        ]
        adapter, mock_pro = _create_adapter()
        mock_pro.income.return_value = _make_income_df(rows)

        result = adapter.fetch_income("600519.SH")

        dates = [r["end_date"] for r in result]
        assert dates == ["20260331", "20251231"]


# ── 行为 3：分段拉取 — daily / daily_basic 按半年分段 ────────


class TestSegmentedFetching:
    """1 年范围拆分为多段，分段失败时不返回部分数据"""

    def test_daily_splits_range_into_segments(self):
        """fetch_daily 对长范围做分段拉取，API 被多次调用"""
        adapter, mock_pro = _create_adapter()
        mock_pro.daily.side_effect = [
            _make_daily_df(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20250701",
                        "open": 1700.0,
                        "high": 1710.0,
                        "low": 1695.0,
                        "close": 1705.0,
                        "vol": 40000.0,
                        "amount": 6800000.0,
                    }
                ]
            ),
            _make_daily_df(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20251101",
                        "open": 1750.0,
                        "high": 1760.0,
                        "low": 1745.0,
                        "close": 1755.0,
                        "vol": 45000.0,
                        "amount": 7900000.0,
                    }
                ]
            ),
            _make_daily_df(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20260301",
                        "open": 1800.0,
                        "high": 1810.0,
                        "low": 1795.0,
                        "close": 1805.0,
                        "vol": 50000.0,
                        "amount": 9000000.0,
                    }
                ]
            ),
        ]

        result = adapter.fetch_daily("600519.SH", start_date="20250530", end_date="20260530")
        assert mock_pro.daily.call_count >= 2
        assert len(result.data) == 3

    def test_daily_segment_failure_raises_error(self):
        """日线分段第 2 段失败 → SegmentFetchError，不返回部分数据"""
        from src.collector.adapter import SegmentFetchError

        adapter, mock_pro = _create_adapter()
        mock_pro.daily.side_effect = [
            _make_daily_df(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20250901",
                        "open": 1700.0,
                        "high": 1710.0,
                        "low": 1695.0,
                        "close": 1705.0,
                        "vol": 40000.0,
                        "amount": 6800000.0,
                    }
                ]
            ),
            None,
        ]

        with pytest.raises(SegmentFetchError, match="分段拉取失败"):
            adapter.fetch_daily("600519.SH", start_date="20250530", end_date="20251130")

    def test_daily_basic_splits_range_into_segments(self):
        """fetch_daily_basic 对长范围做分段拉取"""
        adapter, mock_pro = _create_adapter()
        mock_pro.daily_basic.side_effect = [
            _make_daily_basic_df(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20250701",
                        "pe": 29.0,
                        "pe_ttm": 29.5,
                        "pb": 9.8,
                        "turnover_rate": 0.7,
                    }
                ]
            ),
            _make_daily_basic_df(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20260301",
                        "pe": 30.5,
                        "pe_ttm": 31.0,
                        "pb": 10.2,
                        "turnover_rate": 0.8,
                    }
                ]
            ),
        ]

        result = adapter.fetch_daily_basic("600519.SH", start_date="20250530", end_date="20251130")
        assert mock_pro.daily_basic.call_count == 2
        assert len(result) == 2
        assert result[0]["source"] == "tushare:daily_basic"

    def test_daily_basic_segment_failure_raises_error(self):
        """daily_basic 分段失败 → SegmentFetchError"""
        from src.collector.adapter import SegmentFetchError

        adapter, mock_pro = _create_adapter()
        mock_pro.daily_basic.side_effect = [
            _make_daily_basic_df(
                [
                    {
                        "ts_code": "600519.SH",
                        "trade_date": "20250901",
                        "pe": 29.0,
                        "pe_ttm": 29.5,
                        "pb": 9.8,
                        "turnover_rate": 0.7,
                    }
                ]
            ),
            None,
        ]

        with pytest.raises(SegmentFetchError, match="分段拉取失败"):
            adapter.fetch_daily_basic("600519.SH", start_date="20250530", end_date="20251130")


# ── 行为 4：moneyflow — 资金流数据 + 积分不足降级 ────────────


class TestFetchMoneyflow:
    def test_returns_capital_flow_data(self):
        adapter, mock_pro = _create_adapter()
        mock_pro.moneyflow.return_value = _make_moneyflow_df()

        result = adapter.fetch_moneyflow("600519.SH")

        assert isinstance(result, CapitalFlowData)
        assert result.insufficient is False
        assert len(result.data) == 1
        assert result.data[0]["source"] == "tushare:moneyflow"

    def test_degrades_on_api_exception(self):
        adapter, mock_pro = _create_adapter()
        mock_pro.moneyflow.side_effect = Exception("积分不足，无权限访问")

        result = adapter.fetch_moneyflow("600519.SH")

        assert result.insufficient is True
        assert result.data is None

    def test_degrades_on_none_return(self):
        adapter, mock_pro = _create_adapter()
        mock_pro.moneyflow.return_value = None

        result = adapter.fetch_moneyflow("600519.SH")

        assert result.insufficient is True
        assert result.data is None

    def test_degrades_on_empty_dataframe(self):
        adapter, mock_pro = _create_adapter()
        mock_pro.moneyflow.return_value = pd.DataFrame()

        result = adapter.fetch_moneyflow("600519.SH")

        assert result.insufficient is True
        assert result.data is None


# ── 行为 5：fetch_all — 一次性拉取全部 5 个接口 ──────────────


class TestFetchAll:
    def test_returns_raw_data_with_all_dimensions(self, tmp_path):
        adapter, mock_pro = _create_adapter()
        mock_pro.daily.return_value = _make_daily_df()
        mock_pro.daily_basic.return_value = _make_daily_basic_df()
        mock_pro.fina_indicator.return_value = _make_fina_indicator_df()
        mock_pro.income.return_value = _make_income_df()
        mock_pro.moneyflow.return_value = _make_moneyflow_df()

        with patch("src.collector.adapter._get_data_dir", return_value=tmp_path):
            result = adapter.fetch_all("600519.SH")

        assert isinstance(result, RawData)
        assert len(result.daily.data) >= 1
        assert len(result.fundamental.daily_basic) >= 1
        assert len(result.fundamental.fina_indicator) >= 1
        assert len(result.fundamental.income) >= 1
        assert result.capital.insufficient is False

    def test_moneyflow_degrades_gracefully(self, tmp_path):
        adapter, mock_pro = _create_adapter()
        mock_pro.daily.return_value = _make_daily_df()
        mock_pro.daily_basic.return_value = _make_daily_basic_df()
        mock_pro.fina_indicator.return_value = _make_fina_indicator_df()
        mock_pro.income.return_value = _make_income_df()
        mock_pro.moneyflow.side_effect = Exception("积分不足")

        with patch("src.collector.adapter._get_data_dir", return_value=tmp_path):
            result = adapter.fetch_all("600519.SH")

        assert isinstance(result, RawData)
        assert len(result.daily.data) >= 1
        assert result.capital.insufficient is True
        assert result.capital.data is None
