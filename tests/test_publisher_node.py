"""Issue #45 测试：report_publisher_agent 节点 — 组装 AnalysisReport + Parquet + storage error"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd


def _sample_technical_report():
    return {
        "symbol": "600519.SH",
        "date": "20260530",
        "scores": {
            "technical": {"value": 1, "reason": "多头", "data_sufficient": True},
            "fundamental": {"value": 1, "reason": "PE低位", "data_sufficient": True},
            "capital": {"value": -1, "reason": "净流出", "data_sufficient": True},
        },
        "indicators": {"ma5": 1850.0, "pe_ttm": 30.5},
    }


def _sample_decision_report():
    return {
        "symbol": "600519.SH",
        "date": "20260530",
        "scores": {
            "technical": {"value": 1, "reason": "多头", "confidence": "determined"},
            "fundamental": {"value": 1, "reason": "PE低位", "confidence": "determined"},
            "capital": {"value": -1, "reason": "净流出", "confidence": "determined"},
        },
        "conflict_detected": True,
        "conflict_detail": "技术面偏多，资金面偏空",
        "overall_judgment": "中性偏谨慎",
        "confidence_level": "低",
        "key_driver": "资金面净流出",
        "risk_warning": "风险提示",
        "bearish_factor": "主力净流出",
        "data_sources": ["Tushare daily"],
        "generated_at": "2026-05-30T16:30:00",
    }


# ── 行为 1：正常流程 - 组装 + Parquet 落盘 ──────────────────────


class TestReportPublisherAgentSuccess:
    def test_writes_parquet_file(self):
        from src.publisher.node import report_publisher_agent

        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.publisher.node.DATA_DIR", tmp):
                state = {
                    "symbol": "600519.SH",
                    "technical_report": _sample_technical_report(),
                    "decision_report": _sample_decision_report(),
                }
                result = report_publisher_agent(state)

            assert "report_path" in result
            report_path = Path(result["report_path"])
            assert report_path.exists()
            assert report_path.suffix == ".parquet"

    def test_parquet_content_has_all_fields(self):
        from src.publisher.node import report_publisher_agent

        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.publisher.node.DATA_DIR", tmp):
                state = {
                    "symbol": "600519.SH",
                    "technical_report": _sample_technical_report(),
                    "decision_report": _sample_decision_report(),
                }
                result = report_publisher_agent(state)

            df = pd.read_parquet(result["report_path"])
            report = df.to_dict("records")[0]
            for key in ["symbol", "date", "overall_judgment", "confidence_level",
                         "conflict_detected", "bearish_factor"]:
                assert key in report, f"Missing: {key}"

    def test_scores_embedded_in_parquet(self):
        from src.publisher.node import report_publisher_agent

        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.publisher.node.DATA_DIR", tmp):
                state = {
                    "symbol": "600519.SH",
                    "technical_report": _sample_technical_report(),
                    "decision_report": _sample_decision_report(),
                }
                result = report_publisher_agent(state)

            df = pd.read_parquet(result["report_path"])
            report = df.to_dict("records")[0]
            assert report["scores"]["technical"]["value"] == 1
            assert report["scores"]["technical"]["confidence"] == "determined"

    def test_creates_reports_directory(self):
        from src.publisher.node import report_publisher_agent

        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp) / "reports"
            with patch("src.publisher.node.DATA_DIR", tmp):
                state = {
                    "symbol": "600519.SH",
                    "technical_report": _sample_technical_report(),
                    "decision_report": _sample_decision_report(),
                }
                report_publisher_agent(state)

            assert reports_dir.exists()


# ── 行为 2：错误处理 — Parquet 落盘失败 ─────────────────────────


class TestReportPublisherAgentError:
    def test_storage_error_on_write_failure(self):
        from src.publisher.node import report_publisher_agent

        state = {
            "symbol": "600519.SH",
            "technical_report": _sample_technical_report(),
            "decision_report": _sample_decision_report(),
        }

        with patch("src.publisher.node.pd.DataFrame.to_parquet") as mock_write:
            mock_write.side_effect = OSError("disk full")
            result = report_publisher_agent(state)

        assert "error" in result
        assert result["error"]["error_type"] == "storage"


# ── 行为 3：raw_data_paths 反推 ────────────────────────────────


class TestRawDataPathsInReport:
    def test_raw_data_paths_in_parquet(self):
        from src.publisher.node import report_publisher_agent

        with tempfile.TemporaryDirectory() as tmp:
            with patch("src.publisher.node.DATA_DIR", tmp):
                state = {
                    "symbol": "600519.SH",
                    "technical_report": _sample_technical_report(),
                    "decision_report": _sample_decision_report(),
                }
                result = report_publisher_agent(state)

            df = pd.read_parquet(result["report_path"])
            report = df.to_dict("records")[0]
            assert "raw_data_paths" in report
            paths = report["raw_data_paths"]
            for key in ["daily", "daily_basic", "fina_indicator", "income", "moneyflow"]:
                assert key in paths
            # 这些文件在临时目录中不存在，都应返回 None
            assert paths["daily"] is None
