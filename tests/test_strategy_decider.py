"""Issue #25 测试：strategy_decider_agent 节点函数"""

import json
from unittest.mock import MagicMock, patch


def _sample_technical_report():
    from src.analyzer.schemas import DimensionScore

    return {
        "symbol": "600519.SH",
        "date": "20260530",
        "scores": {
            "technical": DimensionScore(value=1, reason="均线多头排列", data_sufficient=True),
            "fundamental": DimensionScore(value=1, reason="PE低位", data_sufficient=True),
            "capital": DimensionScore(value=-1, reason="净流出", data_sufficient=True),
        },
        "indicators": {
            "ma5": 1850.2, "ma20": 1820.5, "ma60": 1780.0,
            "macd_hist": 0.04, "macd_hist_prev": 0.02, "vol_ratio": 1.8,
            "pe_ttm": 30.5, "pe_percentile_1y": 25.0,
            "roe_yearly": 0.31, "tr_yoy": 0.12, "netprofit_yoy": 0.15,
            "net_mf_amount_5d": -2.3e8, "lg_buy_sell_ratio": 0.6,
        },
    }


def _valid_llm_5_field_response():
    """重构后的 LLM 只需输出 5 个推理字段"""
    return json.dumps({
        "conflict_detail": "技术面偏多，资金面偏空",
        "overall_judgment": "中性偏谨慎",
        "key_driver": "资金面净流出",
        "risk_warning": "风险提示",
        "bearish_factor": "主力净流出明显",
    })


def _make_mock_llm(response_text):
    """创建返回指定文本的 mock LLM"""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content=response_text)
    return mock


class TestStrategyDeciderAgent:
    def test_returns_decision_report_on_success(self):
        from src.strategist.node import strategy_decider_agent

        mock_llm = _make_mock_llm(_valid_llm_5_field_response())

        with patch("src.strategist.node.create_llm_client", return_value=mock_llm):
            state = {"symbol": "600519.SH", "technical_report": _sample_technical_report()}
            result = strategy_decider_agent(state)

        assert "decision_report" in result
        report = result["decision_report"]
        assert report["symbol"] == "600519.SH"
        assert report["confidence_level"] == "低"  # 代码注入（max-min=2 >= 2）
        assert report["conflict_detected"] is True  # 代码注入（+1, +1, -1）
        assert report["scores"]["technical"]["confidence"] == "determined"

    def test_empty_tech_report_returns_error(self):
        from src.strategist.node import strategy_decider_agent

        state = {"symbol": "600519.SH", "technical_report": {}}
        result = strategy_decider_agent(state)

        assert "error" in result
        assert result["error"]["error_type"] == "input"

    def test_parse_error_retries_once(self):
        """非 JSON 响应 → 重试 1 次 → 仍失败"""
        from src.strategist.node import strategy_decider_agent

        mock_llm = _make_mock_llm("not json at all")

        with patch("src.strategist.node.create_llm_client", return_value=mock_llm):
            state = {"symbol": "600519.SH", "technical_report": _sample_technical_report()}
            result = strategy_decider_agent(state)

        # 两次调用（初始 + 1 次重试）
        assert mock_llm.invoke.call_count == 2
        assert result["error"]["error_type"] == "llm_parse_error"

    def test_all_dimensions_insufficient_returns_error(self):
        from src.analyzer.schemas import DimensionScore
        from src.strategist.node import strategy_decider_agent

        report = _sample_technical_report()
        report["scores"] = {
            "technical": DimensionScore(value=0, reason="", data_sufficient=False),
            "fundamental": DimensionScore(value=0, reason="", data_sufficient=False),
            "capital": DimensionScore(value=0, reason="", data_sufficient=False),
        }

        state = {"symbol": "600519.SH", "technical_report": report}
        result = strategy_decider_agent(state)

        assert "error" in result
        assert result["error"]["error_type"] == "input"

    def test_missing_technical_report_key_returns_error(self):
        from src.strategist.node import strategy_decider_agent

        state = {"symbol": "600519.SH"}
        result = strategy_decider_agent(state)

        assert "error" in result
        assert result["error"]["error_type"] == "input"
