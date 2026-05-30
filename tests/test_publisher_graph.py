"""Issue #46 测试：build_publisher_graph — simple StateGraph + end-to-end invoke"""

import tempfile
from pathlib import Path
from unittest.mock import patch


def _sample_state():
    return {
        "symbol": "600519.SH",
        "technical_report": {
            "symbol": "600519.SH",
            "date": "20260530",
            "scores": {
                "technical": {"value": 1, "reason": "多头", "data_sufficient": True},
            },
            "indicators": {"ma5": 100.0},
        },
        "decision_report": {
            "symbol": "600519.SH",
            "date": "20260530",
            "scores": {
                "technical": {"value": 1, "reason": "多头", "confidence": "determined"},
            },
            "conflict_detected": False,
            "conflict_detail": "",
            "overall_judgment": "中性",
            "confidence_level": "中",
            "key_driver": "",
            "risk_warning": "",
            "bearish_factor": "",
            "data_sources": [],
            "generated_at": "",
        },
    }


class TestBuildPublisherGraph:
    def test_returns_compiled_graph(self):
        from src.publisher.node import build_publisher_graph

        graph = build_publisher_graph()
        assert graph is not None

    def test_graph_invoke_writes_parquet(self):
        from src.publisher.node import build_publisher_graph

        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.publisher.node.DATA_DIR", tmp):
                graph = build_publisher_graph()
                result = graph.invoke(_sample_state())

            assert "report_path" in result
            assert Path(result["report_path"]).exists()

    def test_graph_invoke_with_empty_decision_report(self):
        """空 decision_report → publisher 图不崩溃"""
        from src.publisher.node import build_publisher_graph

        state = {
            "symbol": "600519.SH",
            "technical_report": {"scores": {}, "indicators": {}, "date": ""},
            "decision_report": {},
        }

        with tempfile.TemporaryDirectory() as tmp, patch("src.publisher.node.DATA_DIR", tmp):
            graph = build_publisher_graph()
            result = graph.invoke(state)

        # 图正常完成，不抛异常
        assert isinstance(result, dict)

    def test_graph_has_publisher_node(self):
        from src.publisher.node import build_publisher_graph

        graph = build_publisher_graph()
        assert "report_publisher" in graph.nodes
