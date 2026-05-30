"""Issue #5 测试：LangGraph 集成——节点函数、StateGraph、错误处理、重试"""

import os
from unittest.mock import MagicMock, patch

from src.collector.schemas import CapitalFlowData, DailyQuoteData, FundData, RawData


def _sample_raw_data():
    return RawData(
        daily=DailyQuoteData(
            data=[
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
                    "raw_value": "{}",
                }
            ]
        ),
        fundamental=FundData(
            daily_basic=[
                {
                    "ts_code": "600519.SH",
                    "trade_date": "20260102",
                    "pe": 30.5,
                    "source": "tushare:daily_basic",
                    "fetched_at": "2026-05-30",
                    "raw_value": "{}",
                }
            ],
            fina_indicator=[
                {
                    "ts_code": "600519.SH",
                    "end_date": "20260331",
                    "roe": 0.31,
                    "source": "tushare:fina_indicator",
                    "fetched_at": "2026-05-30",
                    "raw_value": "{}",
                }
            ],
            income=[
                {
                    "ts_code": "600519.SH",
                    "end_date": "20260331",
                    "total_revenue": 5e11,
                    "source": "tushare:income",
                    "fetched_at": "2026-05-30",
                    "raw_value": "{}",
                }
            ],
        ),
        capital=CapitalFlowData(data=None, insufficient=True),
    )


def _make_mock_adapter(raw_data):
    """创建返回指定 raw_data 的 mock adapter。"""
    adapter = MagicMock()
    adapter.fetch_all.return_value = raw_data
    return adapter


# ── 行为 1：data_collector_agent 节点函数 ────────────────────


class TestDataCollectorAgentNode:
    """data_collector_agent(state) 读取 symbol，调 fetch_all，写 raw_data"""

    def test_reads_symbol_and_writes_raw_data(self, tmp_path):
        from src.collector.node import data_collector_agent

        state = {"symbol": "600519"}
        mock_adapter = _make_mock_adapter(_sample_raw_data())

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
        ):
            result = data_collector_agent(state)

        mock_adapter.fetch_all.assert_called_once_with("600519.SH")
        assert "raw_data" in result
        assert "daily" in result["raw_data"]

    def test_auto_completes_bare_symbol(self, tmp_path):
        """输入裸代码 600519 → 自动补全为 600519.SH"""
        from src.collector.node import data_collector_agent

        state = {"symbol": "600519"}
        mock_adapter = _make_mock_adapter(_sample_raw_data())

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
        ):
            data_collector_agent(state)

        mock_adapter.fetch_all.assert_called_once_with("600519.SH")

    def test_keeps_full_symbol_unchanged(self, tmp_path):
        """输入完整代码 600519.SH → 不做补全"""
        from src.collector.node import data_collector_agent

        state = {"symbol": "600519.SH"}
        mock_adapter = _make_mock_adapter(_sample_raw_data())

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
        ):
            data_collector_agent(state)

        mock_adapter.fetch_all.assert_called_once_with("600519.SH")

    def test_token_missing_returns_structured_error(self, tmp_path):
        """TUSHARE_TOKEN 未配置 → 结构化错误"""
        from src.collector.node import data_collector_agent

        state = {"symbol": "600519"}

        with patch.dict(os.environ, {}, clear=True), patch("src.collector.node._get_data_dir", return_value=tmp_path):
            result = data_collector_agent(state)

        assert "error" in result
        assert result["error"]["error_type"] == "config"
        assert "TUSHARE_TOKEN" in result["error"]["message"]

    def test_invalid_symbol_returns_error(self, tmp_path):
        """无效股票代码 → 结构化错误"""
        from src.collector.node import data_collector_agent

        state = {"symbol": "1234567"}
        mock_adapter = _make_mock_adapter(_sample_raw_data())

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
        ):
            result = data_collector_agent(state)

        assert "error" in result
        assert result["error"]["error_type"] == "input"

    def test_empty_tushare_result_returns_stock_not_found_error(self, tmp_path):
        """代码格式正确但 Tushare 返回空数据 → "未找到该股票" 错误"""
        from src.collector.node import data_collector_agent

        empty_raw = RawData(
            daily=DailyQuoteData(data=[]),
            fundamental=FundData(daily_basic=[], fina_indicator=[], income=[]),
            capital=CapitalFlowData(data=None, insufficient=False),
        )
        mock_adapter = MagicMock()
        mock_adapter.fetch_all.return_value = empty_raw

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
        ):
            result = data_collector_agent({"symbol": "600000"})

        assert "error" in result
        assert result["error"]["error_type"] == "not_found"
        assert "未找到" in result["error"]["message"]


# ── 行为 2：StateGraph 构建 ────────────────────────────────


class TestStateGraph:
    """最简 StateGraph 包含 data_collector 节点"""

    def test_build_graph_returns_compiled_graph(self):
        from src.collector.node import build_graph

        graph = build_graph()
        assert graph is not None

    def test_graph_execution_with_mock(self, tmp_path):
        """StateGraph 执行 data_collector 节点，raw_data 写入 state"""
        from src.collector.node import build_graph

        mock_adapter = _make_mock_adapter(_sample_raw_data())

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
        ):
            graph = build_graph()
            result = graph.invoke({"symbol": "600519"})

        assert "raw_data" in result
        assert "daily" in result["raw_data"]


# ── 行为 3：重试机制 ──────────────────────────────────────


class TestRetryMechanism:
    """API 超时重试 2 次，参数错误不重试"""

    def test_retries_on_timeout(self, tmp_path):
        """超时重试 2 次后成功 → 用户无感知"""
        from src.collector.node import data_collector_agent

        mock_adapter = MagicMock()
        mock_adapter.fetch_all.side_effect = [
            TimeoutError("connection timeout"),
            _sample_raw_data(),  # 第二次成功
        ]

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
            patch("src.collector.node.time"),
        ):
            result = data_collector_agent({"symbol": "600519"})

        assert "raw_data" in result
        assert mock_adapter.fetch_all.call_count == 2

    def test_retries_exhausted_returns_error(self, tmp_path):
        """超时重试 2 次仍失败 → 返回错误"""
        from src.collector.node import data_collector_agent

        mock_adapter = MagicMock()
        mock_adapter.fetch_all.side_effect = TimeoutError("connection timeout")

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
            patch("src.collector.node.time"),
        ):
            result = data_collector_agent({"symbol": "600519"})

        assert "error" in result
        assert result["error"]["error_type"] == "network"
        assert mock_adapter.fetch_all.call_count == 3  # 1 initial + 2 retries

    def test_no_retry_on_permission_error(self, tmp_path):
        """权限错误（如 moneyflow 积分不足）不触发重试"""
        from src.collector.node import data_collector_agent

        mock_adapter = MagicMock()
        mock_adapter.fetch_all.side_effect = PermissionError("积分不足")

        with (
            patch("src.collector.node.TushareAdapter", return_value=mock_adapter),
            patch("src.collector.node._get_data_dir", return_value=tmp_path),
        ):
            result = data_collector_agent({"symbol": "600519"})

        assert "error" in result
        assert result["error"]["error_type"] == "permission"
        assert mock_adapter.fetch_all.call_count == 1  # 不重试

    def test_structured_error_has_required_fields(self, tmp_path):
        """错误字典包含 error_type、message、detail"""
        from src.collector.node import data_collector_agent

        with patch.dict(os.environ, {}, clear=True), patch("src.collector.node._get_data_dir", return_value=tmp_path):
            result = data_collector_agent({"symbol": "600519"})

        error = result["error"]
        assert "error_type" in error
        assert "message" in error
        assert "detail" in error
