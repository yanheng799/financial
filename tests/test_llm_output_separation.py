"""Issue #36 测试：LLMOutput/DecisionReport 分离 — 7 字段代码注入"""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

# ── 行为 1：LLMOutput 模型只含 5 个 LLM 推理字段 ──────────────


class TestLLMOutputModel:
    def test_llm_output_has_five_fields(self):
        from src.strategist.schemas import LLMOutput

        fields = set(LLMOutput.model_fields.keys())
        assert fields == {"conflict_detail", "overall_judgment", "key_driver", "risk_warning", "bearish_factor"}

    def test_llm_output_valid_instantiation(self):
        from src.strategist.schemas import LLMOutput

        out = LLMOutput(
            conflict_detail="技术面+基本面偏多，资金面偏空",
            overall_judgment="中性偏谨慎",
            key_driver="资金面净流出弱化了技术面信号",
            risk_warning="主力持续净流出",
            bearish_factor="近5日主力净流出明显",
        )
        assert out.overall_judgment == "中性偏谨慎"

    def test_llm_output_rejects_invalid_judgment(self):
        from src.strategist.schemas import LLMOutput

        with pytest.raises(ValidationError):
            LLMOutput(
                conflict_detail="",
                overall_judgment="坏",
                key_driver="",
                risk_warning="",
                bearish_factor="",
            )

    def test_llm_output_rejects_extra_fields(self):
        """LLMOutput 不应接受 confidence_level 等代码注入字段"""
        from src.strategist.schemas import LLMOutput

        out = LLMOutput(
            conflict_detail="",
            overall_judgment="中性",
            key_driver="",
            risk_warning="",
            bearish_factor="",
            confidence_level="高",
        )
        # extra fields should be ignored
        assert not hasattr(out, "confidence_level") or "confidence_level" not in out.model_fields_set


# ── 行为 2：detect_conflict 正确判断冲突 ────────────────────────


class TestDetectConflict:
    def test_mixed_signs_is_conflict(self):
        from src.strategist.schemas import detect_conflict

        scores = {
            "technical": {"value": 1, "data_sufficient": True},
            "fundamental": {"value": -1, "data_sufficient": True},
        }
        assert detect_conflict(scores) is True

    def test_all_positive_no_conflict(self):
        from src.strategist.schemas import detect_conflict

        scores = {
            "technical": {"value": 1, "data_sufficient": True},
            "fundamental": {"value": 2, "data_sufficient": True},
            "capital": {"value": 1, "data_sufficient": True},
        }
        assert detect_conflict(scores) is False

    def test_all_negative_no_conflict(self):
        from src.strategist.schemas import detect_conflict

        scores = {
            "technical": {"value": -1, "data_sufficient": True},
            "fundamental": {"value": -2, "data_sufficient": True},
        }
        assert detect_conflict(scores) is False

    def test_zero_value_does_not_count_as_direction(self):
        """零值不算方向：+1 和 0 不算冲突"""
        from src.strategist.schemas import detect_conflict

        scores = {
            "technical": {"value": 1, "data_sufficient": True},
            "fundamental": {"value": 0, "data_sufficient": True},
        }
        assert detect_conflict(scores) is False

    def test_positive_and_negative_with_zero_is_conflict(self):
        """+1 和 -1 之间有 0，仍然是冲突"""
        from src.strategist.schemas import detect_conflict

        scores = {
            "technical": {"value": 1, "data_sufficient": True},
            "fundamental": {"value": 0, "data_sufficient": True},
            "capital": {"value": -1, "data_sufficient": True},
        }
        assert detect_conflict(scores) is True

    def test_insufficient_dimensions_ignored(self):
        """data_sufficient=False 的维度不参与冲突判断"""
        from src.strategist.schemas import detect_conflict

        scores = {
            "technical": {"value": 1, "data_sufficient": True},
            "fundamental": {"value": -1, "data_sufficient": False},
        }
        assert detect_conflict(scores) is False

    def test_all_zeros_no_conflict(self):
        from src.strategist.schemas import detect_conflict

        scores = {
            "technical": {"value": 0, "data_sufficient": True},
            "fundamental": {"value": 0, "data_sufficient": True},
            "capital": {"value": 0, "data_sufficient": True},
        }
        assert detect_conflict(scores) is False


# ── 行为 3：build_data_sources 只包含 sufficient 维度 ───────────


class TestBuildDataSources:
    def test_only_sufficient_dimensions(self):
        from src.strategist.schemas import build_data_sources

        scores = {
            "technical": {"value": 1, "data_sufficient": True},
            "fundamental": {"value": 0, "data_sufficient": False},
            "capital": {"value": -1, "data_sufficient": True},
        }
        dim_sources = {
            "technical": "Tushare daily",
            "fundamental": "Tushare fina_indicator",
            "capital": "Tushare moneyflow",
        }
        result = build_data_sources(scores, dim_sources)
        assert "Tushare daily" in result
        assert "Tushare moneyflow" in result
        assert "Tushare fina_indicator" not in result

    def test_empty_when_all_insufficient(self):
        from src.strategist.schemas import build_data_sources

        scores = {
            "technical": {"value": 0, "data_sufficient": False},
        }
        result = build_data_sources(scores, {"technical": "Tushare daily"})
        assert result == []


# ── 行为 4：DecisionReport 有 model_config extra="ignore" ──────


class TestDecisionReportConfig:
    def test_extra_fields_ignored(self):
        from src.strategist.schemas import DecisionReport, ScoreEntry

        data = {
            "symbol": "600519.SH",
            "date": "20260530",
            "scores": {"technical": ScoreEntry(value=1, reason="test", confidence="determined").model_dump()},
            "conflict_detected": False,
            "conflict_detail": "",
            "overall_judgment": "中性",
            "confidence_level": "高",
            "key_driver": "",
            "risk_warning": "",
            "bearish_factor": "",
            "data_sources": [],
            "generated_at": "2026-05-30T00:00:00",
            "extra_field_from_llm": "should be ignored",
        }
        report = DecisionReport.model_validate(data)
        assert report.symbol == "600519.SH"
        assert not hasattr(report, "extra_field_from_llm")


# ── 行为 5：build_prompt 只要求 LLM 输出 5 个字段 ──────────────


class TestBuildPromptSimplified:
    def test_prompt_json_template_has_five_fields(self):
        from src.strategist.node import build_prompt

        report = {
            "symbol": "600519.SH",
            "date": "20260530",
            "scores": {
                "technical": {"value": 1, "reason": "test", "data_sufficient": True},
                "fundamental": {"value": 1, "reason": "test", "data_sufficient": True},
                "capital": {"value": -1, "reason": "test", "data_sufficient": True},
            },
            "indicators": {"ma5": 100.0},
        }
        prompt = build_prompt(report)

        # LLM 需要输出的 5 个字段应在模板中
        assert "conflict_detail" in prompt
        assert "overall_judgment" in prompt
        assert "key_driver" in prompt
        assert "risk_warning" in prompt
        assert "bearish_factor" in prompt

    def test_prompt_does_not_ask_for_code_injected_fields(self):
        from src.strategist.node import build_prompt

        report = {
            "symbol": "600519.SH",
            "date": "20260530",
            "scores": {
                "technical": {"value": 1, "reason": "test", "data_sufficient": True},
            },
            "indicators": {},
        }
        prompt = build_prompt(report)

        # JSON 模板中不应要求 LLM 输出这些字段
        json_section = prompt[prompt.index("JSON"):]
        assert '"symbol"' not in json_section
        assert '"date"' not in json_section
        assert '"scores"' not in json_section
        assert '"confidence_level"' not in json_section
        assert '"conflict_detected"' not in json_section
        assert '"data_sources"' not in json_section
        assert '"generated_at"' not in json_section


# ── 行为 6：strategy_decider_agent 用 LLMOutput 校验 → 合并 → DecisionReport


class TestStrategyDeciderRefactored:
    def _sample_technical_report(self):
        return {
            "symbol": "600519.SH",
            "date": "20260530",
            "scores": {
                "technical": {"value": 1, "reason": "多头", "data_sufficient": True},
                "fundamental": {"value": 1, "reason": "合理", "data_sufficient": True},
                "capital": {"value": -1, "reason": "净流出", "data_sufficient": True},
            },
            "indicators": {"ma5": 100.0, "pe_ttm": 30.0},
        }

    def _mock_llm_5_field_response(self):
        return json.dumps({
            "conflict_detail": "技术面+基本面偏多，资金面偏空",
            "overall_judgment": "中性偏谨慎",
            "key_driver": "资金面净流出弱化了技术面多头信号",
            "risk_warning": "主力持续净流出风险",
            "bearish_factor": "近5日主力净流出明显",
        })

    def test_llm_5_fields_produces_full_12_field_report(self):
        """LLM 只输出 5 字段 → decision_report 包含完整 12 字段"""
        from src.strategist.node import strategy_decider_agent

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = self._mock_llm_5_field_response()
        mock_client.invoke.return_value = mock_response

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            result = strategy_decider_agent({"symbol": "600519.SH", "technical_report": self._sample_technical_report()})

        assert "decision_report" in result
        report = result["decision_report"]
        # 代码注入的 7 个字段
        assert report["symbol"] == "600519.SH"
        assert report["date"] == "20260530"
        assert "confidence_level" in report
        assert "conflict_detected" in report
        assert "scores" in report
        assert "data_sources" in report
        assert "generated_at" in report
        # LLM 的 5 个字段
        assert report["conflict_detail"] == "技术面+基本面偏多，资金面偏空"
        assert report["overall_judgment"] == "中性偏谨慎"
        assert report["key_driver"] == "资金面净流出弱化了技术面多头信号"
        assert report["risk_warning"] == "主力持续净流出风险"
        assert report["bearish_factor"] == "近5日主力净流出明显"

    def test_conflict_detected_is_code_computed(self):
        """conflict_detected 由代码判断，非 LLM"""
        from src.strategist.node import strategy_decider_agent

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = self._mock_llm_5_field_response()
        mock_client.invoke.return_value = mock_response

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            result = strategy_decider_agent({"symbol": "600519.SH", "technical_report": self._sample_technical_report()})

        # tech=+1, fund=+1, cap=-1 → 既有正又有负 → conflict_detected=True
        assert result["decision_report"]["conflict_detected"] is True

    def test_generated_at_is_iso_format(self):
        """generated_at 由代码注入，ISO 8601 格式"""
        from src.strategist.node import strategy_decider_agent

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = self._mock_llm_5_field_response()
        mock_client.invoke.return_value = mock_response

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            result = strategy_decider_agent({"symbol": "600519.SH", "technical_report": self._sample_technical_report()})

        generated_at = result["decision_report"]["generated_at"]
        # 应该是有效的 ISO 8601 格式
        datetime.fromisoformat(generated_at)

    def test_data_sources_only_contains_sufficient_dims(self):
        """data_sources 只包含 data_sufficient=True 的维度"""
        from src.strategist.node import strategy_decider_agent

        report = self._sample_technical_report()
        report["scores"]["fundamental"]["data_sufficient"] = False

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "conflict_detail": "", "overall_judgment": "中性",
            "key_driver": "", "risk_warning": "", "bearish_factor": "风险",
        })
        mock_client.invoke.return_value = mock_response

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            result = strategy_decider_agent({"symbol": "600519.SH", "technical_report": report})

        sources = result["decision_report"]["data_sources"]
        assert any("daily" in s for s in sources)  # technical
        assert any("moneyflow" in s for s in sources)  # capital
        assert not any("fina_indicator" in s for s in sources)  # fundamental insufficient

    def test_retry_with_llm_output_validation(self):
        """LLM 输出不符合 LLMOutput schema 时重试 1 次"""
        from src.strategist.node import strategy_decider_agent

        mock_client = MagicMock()
        bad_response = MagicMock()
        bad_response.content = json.dumps({"conflict_detail": "", "overall_judgment": "坏判断"})
        good_response = MagicMock()
        good_response.content = self._mock_llm_5_field_response()
        mock_client.invoke.side_effect = [bad_response, good_response]

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            result = strategy_decider_agent({"symbol": "600519.SH", "technical_report": self._sample_technical_report()})

        assert "decision_report" in result
        assert mock_client.invoke.call_count == 2


# ── 行为 7：端到端 StateGraph ──────────────────────────────────


class TestEndToEndWithRefactoredSchema:
    def test_graph_invoke_with_5_field_llm(self):
        from src.strategist.node import build_strategist_graph

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "conflict_detail": "技术面偏多，资金面偏空",
            "overall_judgment": "中性偏谨慎",
            "key_driver": "资金面净流出",
            "risk_warning": "注意风险",
            "bearish_factor": "主力净流出",
        })
        mock_client.invoke.return_value = mock_response

        with patch("src.strategist.node.create_llm_client", return_value=mock_client):
            graph = build_strategist_graph()
            result = graph.invoke({
                "symbol": "600519.SH",
                "technical_report": {
                    "symbol": "600519.SH",
                    "date": "20260530",
                    "scores": {
                        "technical": {"value": 1, "reason": "多头", "data_sufficient": True},
                        "fundamental": {"value": 1, "reason": "合理", "data_sufficient": True},
                        "capital": {"value": -1, "reason": "净流出", "data_sufficient": True},
                    },
                    "indicators": {"ma5": 100.0},
                },
            })

        report = result["decision_report"]
        assert report["symbol"] == "600519.SH"
        assert report["conflict_detected"] is True
        assert report["confidence_level"] == "低"  # max-min=2 >= 2
        assert "generated_at" in report
        assert "data_sources" in report
