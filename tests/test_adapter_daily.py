"""Issue #2 测试：TushareAdapter 日线端到端——Token 初始化 + fetch_daily 全链路"""

import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.collector.schemas import DailyQuoteData

# ── 行为 1：Token 缺失时给出配置指引 ────────────────────────


class TestTokenInitialization:
    """TushareAdapter 初始化时检查 TUSHARE_TOKEN 环境变量"""

    def test_token_missing_raises_with_guidance(self):
        from src.collector.adapter import TushareAdapter

        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match="TUSHARE_TOKEN"):
            TushareAdapter()

    def test_token_present_initializes_successfully(self):
        from src.collector.adapter import TushareAdapter

        with (
            patch.dict(os.environ, {"TUSHARE_TOKEN": "test_token_123"}, clear=False),
            patch("tushare.pro_api") as mock_pro_api,
        ):
            adapter = TushareAdapter()
            assert adapter is not None
            mock_pro_api.assert_called_once_with("test_token_123")


# ── 行为 2：fetch_daily 返回 DailyQuoteData，含可追溯性字段 ────


# 共享 mock 数据工厂
def _make_daily_df(rows=None):
    """构造模拟 Tushare daily 接口返回的 DataFrame"""
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
            {
                "ts_code": "600519.SH",
                "trade_date": "20260101",
                "open": 1790.0,
                "high": 1800.0,
                "low": 1785.0,
                "close": 1795.0,
                "vol": 55000.0,
                "amount": 9800000.0,
            },
        ]
    return pd.DataFrame(rows)


def _create_adapter():
    """在 mock 环境下创建 TushareAdapter"""
    from src.collector.adapter import TushareAdapter

    with patch.dict(os.environ, {"TUSHARE_TOKEN": "test_token"}, clear=False):
        adapter = TushareAdapter()
    return adapter


class TestFetchDaily:
    """fetch_daily 全链路：API 调用 → 校验 → 可追溯性 → 去重 → 排序"""

    def test_returns_daily_quote_data(self):
        with patch("tushare.pro_api") as mock_pro_api:
            mock_pro = MagicMock()
            mock_pro_api.return_value = mock_pro
            mock_pro.daily.return_value = _make_daily_df()

            adapter = _create_adapter()
            result = adapter.fetch_daily("600519.SH")

            assert isinstance(result, DailyQuoteData)
            assert len(result.data) == 2

    def test_traceability_fields_present(self):
        """每行数据包含 source、fetched_at、raw_value"""
        with patch("tushare.pro_api") as mock_pro_api:
            mock_pro = MagicMock()
            mock_pro_api.return_value = mock_pro
            mock_pro.daily.return_value = _make_daily_df()

            adapter = _create_adapter()
            result = adapter.fetch_daily("600519.SH")

            row = result.data[0]
            assert row.source == "tushare:daily"
            assert row.fetched_at  # non-empty ISO 8601 string
            assert row.raw_value  # non-empty JSON string
            # raw_value 应包含原始 ts_code
            assert "600519.SH" in row.raw_value

    def test_deduplicates_by_ts_code_and_trade_date(self):
        """按 ts_code + trade_date 去重"""
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
            {
                "ts_code": "600519.SH",
                "trade_date": "20260101",
                "open": 1790.0,
                "high": 1800.0,
                "low": 1785.0,
                "close": 1795.0,
                "vol": 55000.0,
                "amount": 9800000.0,
            },
        ]

        with patch("tushare.pro_api") as mock_pro_api:
            mock_pro = MagicMock()
            mock_pro_api.return_value = mock_pro
            mock_pro.daily.return_value = _make_daily_df(rows)

            adapter = _create_adapter()
            result = adapter.fetch_daily("600519.SH")

            assert len(result.data) == 2
            dates = [row.trade_date for row in result.data]
            assert dates.count("20260102") == 1

    def test_sorted_by_trade_date_descending(self):
        """按 trade_date 降序排列（最新在前）"""
        rows = [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260101",
                "open": 1790.0,
                "high": 1800.0,
                "low": 1785.0,
                "close": 1795.0,
                "vol": 55000.0,
                "amount": 9800000.0,
            },
            {
                "ts_code": "600519.SH",
                "trade_date": "20260103",
                "open": 1810.0,
                "high": 1820.0,
                "low": 1800.0,
                "close": 1815.0,
                "vol": 48000.0,
                "amount": 8700000.0,
            },
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

        with patch("tushare.pro_api") as mock_pro_api:
            mock_pro = MagicMock()
            mock_pro_api.return_value = mock_pro
            mock_pro.daily.return_value = _make_daily_df(rows)

            adapter = _create_adapter()
            result = adapter.fetch_daily("600519.SH")

            dates = [row.trade_date for row in result.data]
            assert dates == ["20260103", "20260102", "20260101"]

    def test_calls_daily_api_with_correct_params(self):
        """验证 pro.daily() 被正确调用（分段模式下多次调用）"""

        with patch("tushare.pro_api") as mock_pro_api:
            mock_pro = MagicMock()
            mock_pro_api.return_value = mock_pro
            mock_pro.daily.return_value = _make_daily_df()

            adapter = _create_adapter()
            adapter.fetch_daily("600519.SH", start_date="20250101", end_date="20251231")

            # 分段模式下会被调用多次，每段都带 ts_code
            for call in mock_pro.daily.call_args_list:
                assert call.kwargs["ts_code"] == "600519.SH"


# ── 行为 3：Pydantic 校验拦截缺失关键字段的数据 ─────────────


class TestPydanticValidation:
    """DailyQuoteRow 校验关键字段存在性和类型"""

    def test_rejects_missing_close_field(self):
        """mock Tushare 返回缺失 close 字段的数据 → Pydantic 拦截报错"""
        from pydantic import ValidationError

        from src.collector.schemas import DailyQuoteData

        rows = [
            {
                "ts_code": "600519.SH",
                "trade_date": "20260102",
                "open": 1800.0,
                "high": 1810.0,
                "low": 1795.0,
                # close 字段缺失
                "vol": 50000.0,
                "amount": 9000000.0,
                "source": "tushare:daily",
                "fetched_at": "2026-05-30",
                "raw_value": "{}",
            },
        ]
        with pytest.raises(ValidationError, match="close"):
            DailyQuoteData(data=rows)

    def test_rejects_missing_ts_code_field(self):
        """缺失 ts_code → Pydantic 拦截报错"""
        from pydantic import ValidationError

        from src.collector.schemas import DailyQuoteData

        rows = [
            {
                "trade_date": "20260102",
                "open": 1800.0,
                "high": 1810.0,
                "low": 1795.0,
                "close": 1805.0,
                "vol": 50000.0,
                "amount": 9000000.0,
                "source": "tushare:daily",
                "fetched_at": "2026-05-30",
                "raw_value": "{}",
            },
        ]
        with pytest.raises(ValidationError, match="ts_code"):
            DailyQuoteData(data=rows)


# ── 行为 4：时间范围计算工具 ────────────────────────────────


class TestCalcDateRange:
    """calc_date_range 按 年/季度 计算 start_date/end_date"""

    def test_default_returns_today_as_end(self):
        from src.collector.adapter import calc_date_range

        start, end = calc_date_range()
        assert end == date.today().strftime("%Y%m%d")
        assert len(end) == 8

    def test_one_year_range(self):
        from src.collector.adapter import calc_date_range

        start, end = calc_date_range(years=1)
        expected_start = (date.today() - timedelta(days=365)).strftime("%Y%m%d")
        assert start == expected_start
        assert end == date.today().strftime("%Y%m%d")

    def test_eight_quarters_range(self):
        from src.collector.adapter import calc_date_range

        start, end = calc_date_range(quarters=8)
        expected_start = (date.today() - timedelta(days=720)).strftime("%Y%m%d")
        assert start == expected_start

    def test_fetch_daily_uses_default_one_year(self):
        """不传 start/end 时 fetch_daily 默认拉取近 1 年（分段模式，首段起点≈1 年前）"""
        from src.collector.adapter import calc_date_range

        with patch("tushare.pro_api") as mock_pro_api:
            mock_pro = MagicMock()
            mock_pro_api.return_value = mock_pro
            mock_pro.daily.return_value = _make_daily_df()

            adapter = _create_adapter()
            adapter.fetch_daily("600519.SH")

            first_call = mock_pro.daily.call_args_list[0]
            actual_start = first_call.kwargs["start_date"]
            expected_start, _expected_end = calc_date_range(years=1)
            assert actual_start == expected_start
