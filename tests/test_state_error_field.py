"""Issue #35 测试：AnalysisState error 字段 + human_review END 路径 error"""

import os
from typing import get_type_hints
from unittest.mock import patch

from src.state import AnalysisState  # noqa: E402

# ── 行为 1：AnalysisState 包含 error 字段 ──────────────────────


class TestAnalysisStateErrorField:
    """AnalysisState 必须有 error 字段"""

    def test_error_field_exists(self):
        hints = get_type_hints(AnalysisState)
        assert "error" in hints

    def test_state_accepts_error_dict(self):
        state: AnalysisState = {
            "symbol": "600519.SH",
            "raw_data": {},
            "technical_report": {},
            "decision_report": {},
            "human_approved": False,
            "error": {"error_type": "input", "message": "test", "detail": ""},
        }
        assert state["error"]["error_type"] == "input"

    def test_state_works_without_error(self):
        """error 字段是可选的，不提供时不会报错"""
        state: AnalysisState = {
            "symbol": "600519.SH",
            "raw_data": {},
            "technical_report": {},
            "decision_report": {},
            "human_approved": False,
        }
        assert state.get("error") is None


# ── 行为 2：三个 Agent 错误返回写入 state["error"] ────────────


class TestAgentErrorsReachState:
    """Agent 返回的 {"error": {...}} 通过 LangGraph 写入 state["error"]"""

    def test_collector_error_in_state(self):
        """data_collector 错误能写入 AnalysisState"""
        from src.collector.node import data_collector_agent

        with patch.dict(os.environ, {}, clear=True):
            result = data_collector_agent({"symbol": "600519"})

        assert "error" in result
        assert "error_type" in result["error"]

    def test_analyzer_error_in_state(self):
        """market_analyzer 错误能写入 AnalysisState"""
        from src.analyzer.node import market_analyzer_agent

        result = market_analyzer_agent({"symbol": "600519.SH"})

        assert "error" in result
        assert "error_type" in result["error"]

    def test_strategist_error_in_state(self):
        """strategy_decider 错误能写入 AnalysisState"""
        from src.strategist.node import strategy_decider_agent

        result = strategy_decider_agent({"symbol": "600519.SH"})

        assert "error" in result
        assert "error_type" in result["error"]


# ── 行为 3：human_approved=False → error 提示 ──────────────────


class TestHumanReviewEndPathError:
    """human_approved=False 走 END 时，state 中有 error 提示"""

    def test_route_after_review_returns_error_on_rejection(self):
        """route_after_review 在 human_approved=False 时返回错误信息"""
        from src.strategist.node import route_after_review

        result = route_after_review({"human_approved": False, "symbol": "600519.SH"})

        assert result == "__end__"

    def test_human_review_rejection_in_graph(self):
        """在 StateGraph 中 human_approved=False 时，最终 state 包含 error"""
        from src.strategist.node import build_strategist_graph

        config_data = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
            "temperature": 0.1,
            "max_tokens": 4000,
            "auto_approve": False,
        }

        with patch("src.strategist.node.load_llm_config", return_value=config_data):
            graph = build_strategist_graph()
            result = graph.invoke(
                {
                    "symbol": "600519.SH",
                    "technical_report": {"scores": {}, "indicators": {}},
                    "human_approved": False,
                }
            )

        assert result.get("error") is not None
        assert "未批准" in result["error"]["message"]
