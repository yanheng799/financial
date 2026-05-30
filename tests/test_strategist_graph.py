"""Issue #26 测试：策略决策 Agent StateGraph 组装——build_strategist_graph + 条件边路由"""

import json
from unittest.mock import MagicMock, patch


def _sample_technical_report():
    """构造供 strategy_decider 使用的 mock technical_report"""
    return {
        "symbol": "600519.SH",
        "date": "20260530",
        "scores": {
            "technical": {"value": 1, "reason": "均线多头排列", "data_sufficient": True},
            "fundamental": {"value": 1, "reason": "PE 合理", "data_sufficient": True},
            "capital": {"value": -1, "reason": "主力净流出", "data_sufficient": True},
        },
        "indicators": {
            "ma5": 1850.0,
            "ma20": 1830.0,
            "ma60": 1800.0,
            "macd_hist": 5.2,
            "vol_ratio": 1.3,
            "pe_ttm": 30.5,
            "pe_percentile_1y": 45.0,
            "roe_yearly": 0.31,
            "tr_yoy": 0.12,
            "netprofit_yoy": 0.15,
            "net_mf_amount_5d": -5000.0,
            "lg_buy_sell_ratio": 0.8,
        },
        "generated_at": "2026-05-30",
    }


def _mock_llm_response():
    """构造合法的 LLM JSON 返回"""
    return json.dumps({
        "symbol": "600519.SH",
        "date": "20260530",
        "scores": {
            "technical": {"value": 1, "reason": "多头", "confidence": "determined"},
            "fundamental": {"value": 1, "reason": "合理", "confidence": "determined"},
            "capital": {"value": -1, "reason": "净流出", "confidence": "determined"},
        },
        "conflict_detected": True,
        "conflict_detail": "技术面+基本面偏多，资金面偏空",
        "overall_judgment": "中性偏谨慎",
        "key_driver": "资金面净流出弱化了技术面多头信号",
        "risk_warning": "主力持续净流出风险",
        "bearish_factor": "近5日主力净流出明显",
        "data_sources": ["Tushare daily", "Tushare moneyflow"],
        "generated_at": "2026-05-30T16:30:00",
    })


# ── 行为 1：build_strategist_graph 返回编译后的 StateGraph ──────


class TestBuildStrategistGraph:
    """AC#1: build_strategist_graph() 返回编译后的 StateGraph"""

    def test_returns_compiled_graph(self):
        from src.strategist.node import build_strategist_graph

        graph = build_strategist_graph()
        assert graph is not None

    def test_graph_has_expected_nodes(self):
        """编译后的 graph 应包含 human_review 和 strategy_decider 节点"""
        from src.strategist.node import build_strategist_graph

        graph = build_strategist_graph()
        # CompiledGraph.nodes 暴露节点名称
        node_names = set(graph.nodes.keys())
        assert "human_review" in node_names
        assert "strategy_decider" in node_names


# ── 行为 2：端到端 invoke（auto_approve + mock LLM）─────────────


class TestEndToEndInvoke:
    """AC#2: mock technical_report + mock LLM → decision_report 包含完整 DecisionReport"""

    def test_invoke_produces_decision_report(self):
        from src.strategist.node import build_strategist_graph

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = _mock_llm_response()
        mock_client.invoke.return_value = mock_response

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            graph = build_strategist_graph()
            result = graph.invoke({
                "symbol": "600519.SH",
                "technical_report": _sample_technical_report(),
            })

        assert "decision_report" in result
        report = result["decision_report"]
        assert report["symbol"] == "600519.SH"
        # tech=+1, fund=+1, cap=-1: max-min=2 ≥ 2 → "低"
        assert report["confidence_level"] == "低"
        assert "scores" in report
        assert report["conflict_detected"] is True
        assert "bearish_factor" in report

    def test_invoke_injects_code_computed_confidence(self):
        """confidence_level 由代码注入（非 LLM 输出）"""
        from src.strategist.node import build_strategist_graph

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = _mock_llm_response()
        mock_client.invoke.return_value = mock_response

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            graph = build_strategist_graph()
            result = graph.invoke({
                "symbol": "600519.SH",
                "technical_report": _sample_technical_report(),
            })

        # scores: tech=+1, fund=+1, cap=-1: max-min=2 ≥ 2 → "低"
        assert result["decision_report"]["confidence_level"] == "低"


# ── 行为 3：human_approved=False → END ────────────────────────


class TestRouteAfterReviewReject:
    """AC#3: human_approved=False → 路由到 END，不执行 strategy_decider"""

    def test_rejected_human_review_stops_at_end(self):
        from src.strategist.node import route_after_review

        result = route_after_review({"human_approved": False})
        assert result == "__end__"

    def test_no_llm_called_when_not_approved(self):
        """当 human_approved=False 时，strategy_decider 不应被调用"""
        from src.strategist.node import build_strategist_graph

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = _mock_llm_response()
        mock_client.invoke.return_value = mock_response

        # 强制 auto_approve=False，手动设置 human_approved=False
        config_data = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "temperature": 0.1,
            "max_tokens": 4000,
            "auto_approve": False,
        }

        with (
            patch("src.strategist.node.load_llm_config", return_value=config_data),
            patch("src.strategist.node.create_llm_client", return_value=mock_client),
        ):
            graph = build_strategist_graph()
            # 手动注入 human_approved=False 模拟用户拒绝
            result = graph.invoke({
                "symbol": "600519.SH",
                "technical_report": _sample_technical_report(),
                "human_approved": False,
            })

        # strategy_decider 未被调用，不应有 decision_report
        assert "decision_report" not in result
        mock_client.invoke.assert_not_called()


# ── 行为 4：human_approved=True → strategy_decider ─────────────


class TestRouteAfterReviewApprove:
    """AC#4: human_approved=True → 路由到 strategy_decider"""

    def test_approved_routes_to_strategy_decider(self):
        from src.strategist.node import route_after_review

        result = route_after_review({"human_approved": True})
        assert result == "strategy_decider"

    def test_approved_runs_full_pipeline(self):
        """auto_approve=True → human_review 自动通过 → strategy_decider 被执行"""
        from src.strategist.node import build_strategist_graph

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = _mock_llm_response()
        mock_client.invoke.return_value = mock_response

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            graph = build_strategist_graph()
            result = graph.invoke({
                "symbol": "600519.SH",
                "technical_report": _sample_technical_report(),
            })

        # auto_approve=True → human_review 自动通过 → strategy_decider 执行
        assert "decision_report" in result
        mock_client.invoke.assert_called_once()
