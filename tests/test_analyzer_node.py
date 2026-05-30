"""Issue #15 测试：LangGraph market_analyzer 节点 + StateGraph 集成"""


def _sample_raw_data():
    return {
        "daily": {
            "data": [
                {
                    "ts_code": "600519.SH",
                    "trade_date": f"20260{i + 1:02d}01",
                    "open": 100.0 + i,
                    "high": 101.0 + i,
                    "low": 99.0 + i,
                    "close": 100.5 + i,
                    "vol": 50000.0 + i * 100,
                    "amount": 5000000.0,
                }
                for i in range(80)
            ]
        },
        "fundamental": {
            "daily_basic": [
                {"ts_code": "600519.SH", "trade_date": f"20250{i+1:02d}01", "pe_ttm": 20.0 + i * 2}
                for i in range(30)
            ],
            "fina_indicator": [
                {"ts_code": "600519.SH", "end_date": "20260331", "roe_yearly": 0.31, "tr_yoy": 0.12, "netprofit_yoy": 0.15}
            ],
            "income": [],
        },
        "capital": {
            "data": [
                {"ts_code": "600519.SH", "trade_date": f"20260{i+1:02d}28", "net_mf_amount": 3000 + i * 500,
                 "buy_lg_amount": 600000.0, "sell_lg_amount": 400000.0}
                for i in range(10)
            ],
            "insufficient": False,
        },
    }


def _sample_raw_data_insufficient_capital():
    data = _sample_raw_data()
    data["capital"] = {"data": None, "insufficient": True}
    return data


INDICATOR_KEYS = [
    "ma5", "ma20", "ma60",
    "macd_hist", "macd_hist_prev", "vol_ratio",
    "pe_ttm", "pe_percentile_1y",
    "roe_yearly", "tr_yoy", "netprofit_yoy",
    "net_mf_amount_5d", "lg_buy_sell_ratio",
]


# ── 行为 1：节点函数 ───────────────────────────────────────────────


class TestMarketAnalyzerAgentNode:
    """market_analyzer_agent(state) → technical_report"""

    def test_writes_technical_report_with_scores(self):
        from src.analyzer.node import market_analyzer_agent

        state = {"symbol": "600519.SH", "raw_data": _sample_raw_data()}
        result = market_analyzer_agent(state)

        assert "technical_report" in result
        report = result["technical_report"]
        assert "scores" in report
        assert "technical" in report["scores"]
        assert "fundamental" in report["scores"]
        assert "capital" in report["scores"]

    def test_indicators_has_all_13_keys(self):
        from src.analyzer.node import market_analyzer_agent

        state = {"symbol": "600519.SH", "raw_data": _sample_raw_data()}
        result = market_analyzer_agent(state)

        indicators = result["technical_report"]["indicators"]
        for key in INDICATOR_KEYS:
            assert key in indicators, f"Missing: {key}"

    def test_technical_score_in_range(self):
        from src.analyzer.node import market_analyzer_agent

        state = {"symbol": "600519.SH", "raw_data": _sample_raw_data()}
        result = market_analyzer_agent(state)

        tech = result["technical_report"]["scores"]["technical"]
        assert -2 <= tech["value"] <= 2
        assert tech["data_sufficient"] is True

    def test_capital_insufficient_degrades(self):
        """资金面积分不足 → capital data_sufficient=False，其他正常"""
        from src.analyzer.node import market_analyzer_agent

        state = {"symbol": "600519.SH", "raw_data": _sample_raw_data_insufficient_capital()}
        result = market_analyzer_agent(state)

        cap = result["technical_report"]["scores"]["capital"]
        assert cap["data_sufficient"] is False
        assert result["technical_report"]["scores"]["technical"]["data_sufficient"] is True

    def test_symbol_preserved_in_report(self):
        from src.analyzer.node import market_analyzer_agent

        state = {"symbol": "000001.SZ", "raw_data": _sample_raw_data()}
        result = market_analyzer_agent(state)

        assert result["technical_report"]["symbol"] == "000001.SZ"


# ── 行为 2：错误处理 ───────────────────────────────────────────────


class TestMarketAnalyzerErrors:
    """节点函数的错误处理"""

    def test_empty_raw_data_returns_error(self):
        from src.analyzer.node import market_analyzer_agent

        state = {"symbol": "600519.SH", "raw_data": {}}
        result = market_analyzer_agent(state)

        assert "error" in result
        assert result["error"]["error_type"] == "input"

    def test_missing_raw_data_returns_error(self):
        from src.analyzer.node import market_analyzer_agent

        state = {"symbol": "600519.SH"}
        result = market_analyzer_agent(state)

        assert "error" in result


# ── 行为 3：StateGraph ──────────────────────────────────────────────


class TestAnalyzerStateGraph:
    """build_analyzer_graph → 可 invoked 的 StateGraph"""

    def test_build_returns_compiled_graph(self):
        from src.analyzer.node import build_analyzer_graph

        graph = build_analyzer_graph()
        assert graph is not None

    def test_graph_invoke_with_mock_data(self):
        from src.analyzer.node import build_analyzer_graph

        graph = build_analyzer_graph()
        result = graph.invoke({"symbol": "600519.SH", "raw_data": _sample_raw_data()})

        assert "technical_report" in result
        assert "scores" in result["technical_report"]
