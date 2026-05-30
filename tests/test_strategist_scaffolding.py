"""Issue #27 测试：策略决策 Agent 脚手架——模块结构、Pydantic 模型、LLM 配置"""

from pathlib import Path

import pytest
from pydantic import ValidationError

# ── 行为 1：模块骨架 ────────────────────────────────────────


class TestModuleStructure:
    @pytest.mark.parametrize("filename", ["__init__.py", "schemas.py", "node.py"])
    def test_strategist_module_files_exist(self, filename):
        from src import strategist

        d = Path(strategist.__file__).parent
        assert (d / filename).is_file(), f"Missing {filename}"


# ── 行为 2：ScoreEntry ──────────────────────────────────────


class TestScoreEntry:
    def test_valid_instantiation(self):
        from src.strategist.schemas import ScoreEntry

        s = ScoreEntry(value=1, reason="均线多头排列", confidence="determined")
        assert s.value == 1
        assert s.confidence == "determined"

    def test_insufficient_confidence(self):
        from src.strategist.schemas import ScoreEntry

        s = ScoreEntry(value=0, reason="数据不足", confidence="insufficient")
        assert s.value == 0
        assert s.confidence == "insufficient"

    def test_deferred_confidence(self):
        from src.strategist.schemas import ScoreEntry

        s = ScoreEntry(value=0, reason="Phase 2", confidence="deferred")
        assert s.confidence == "deferred"

    def test_invalid_confidence_raises(self):
        from src.strategist.schemas import ScoreEntry

        with pytest.raises(ValidationError):
            ScoreEntry(value=0, reason="bad", confidence="invalid")


# ── 行为 3：DecisionReport ──────────────────────────────────


class TestDecisionReport:
    def _make_report(self):
        from src.strategist.schemas import DecisionReport, ScoreEntry

        return DecisionReport(
            symbol="600519.SH",
            date="20260530",
            scores={
                "technical": ScoreEntry(value=1, reason="多头", confidence="determined"),
                "fundamental": ScoreEntry(value=0, reason="数据不足", confidence="insufficient"),
                "capital": ScoreEntry(value=-1, reason="净流出", confidence="determined"),
            },
            conflict_detected=True,
            conflict_detail="技术面偏多，资金面偏空",
            overall_judgment="中性偏谨慎",
            confidence_level="中",
            key_driver="资金面",
            risk_warning="注意风险",
            bearish_factor="主力净流出",
            data_sources=["Tushare"],
            generated_at="2026-05-30T16:30:00",
        )

    def test_model_dump_has_all_fields(self):
        report = self._make_report()
        d = report.model_dump()
        for key in (
            "symbol",
            "date",
            "scores",
            "conflict_detected",
            "conflict_detail",
            "overall_judgment",
            "confidence_level",
            "key_driver",
            "risk_warning",
            "bearish_factor",
            "data_sources",
            "generated_at",
        ):
            assert key in d, f"Missing {key}"

    def test_scores_contains_three_dimensions(self):
        report = self._make_report()
        d = report.model_dump()
        assert "technical" in d["scores"]
        assert "fundamental" in d["scores"]
        assert "capital" in d["scores"]

    def test_invalid_overall_judgment_raises(self):
        from src.strategist.schemas import DecisionReport, ScoreEntry

        with pytest.raises(ValidationError):
            DecisionReport(
                symbol="600519.SH",
                date="20260530",
                scores={"technical": ScoreEntry(value=0, reason="", confidence="determined")},
                conflict_detected=False,
                conflict_detail="",
                overall_judgment="坏",  # invalid
                confidence_level="中",
                key_driver="",
                risk_warning="",
                bearish_factor="",
                data_sources=[],
                generated_at="",
            )


# ── 行为 4：LLM 配置 ───────────────────────────────────────


class TestLLMConfig:
    def test_config_file_exists(self):
        assert Path("configs/llm.yaml").is_file()

    def test_load_llm_config(self):
        from src.strategist.schemas import load_llm_config

        config = load_llm_config()
        assert config["provider"] in ("deepseek", "qwen")
        assert "base_url" in config
        assert "api_key_env" in config
        assert "auto_approve" in config
        assert isinstance(config["auto_approve"], bool)

    def test_config_returns_dict(self):
        from src.strategist.schemas import load_llm_config

        config = load_llm_config()
        assert isinstance(config, dict)
