"""Issue #44 测试：publisher scaffolding — AnalysisReport model + _build_raw_data_paths"""

import tempfile
from pathlib import Path

# ── 行为 1：模块结构 ───────────────────────────────────────────


class TestModuleStructure:
    def test_publisher_module_exists(self):
        from src import publisher

        assert publisher.__file__ is not None

    def test_schemas_file_exists(self):
        from src.publisher import schemas

        assert schemas.__file__ is not None


# ── 行为 2：AnalysisReport 模型 ──────────────────────────────────


class TestAnalysisReport:
    def _make_report(self, **overrides):
        from src.publisher.schemas import AnalysisReport
        from src.strategist.schemas import ScoreEntry

        return AnalysisReport(
            symbol="600519.SH",
            date="20260530",
            generated_at="2026-05-30T16:30:00",
            scores={
                "technical": ScoreEntry(value=1, reason="多头", confidence="determined"),
                "fundamental": ScoreEntry(value=1, reason="PE低位", confidence="determined"),
                "capital": ScoreEntry(value=-1, reason="净流出", confidence="determined"),
            },
            indicators={"ma5": 100.0, "pe_ttm": 30.0},
            overall_judgment="中性偏谨慎",
            confidence_level="低",
            conflict_detected=True,
            conflict_detail="技术面偏多，资金面偏空",
            key_driver="资金面净流出",
            risk_warning="注意风险",
            bearish_factor="主力净流出",
            data_sources=["Tushare daily"],
            raw_data_paths={"daily": "data/600519.SH/daily.parquet", "moneyflow": None},
            **overrides,
        )

    def test_model_dump_has_all_14_fields(self):
        report = self._make_report()
        d = report.model_dump()
        expected = [
            "symbol", "date", "generated_at",
            "scores", "indicators",
            "overall_judgment", "confidence_level", "conflict_detected",
            "conflict_detail", "key_driver", "risk_warning", "bearish_factor",
            "data_sources", "raw_data_paths",
        ]
        for key in expected:
            assert key in d, f"Missing field: {key}"

    def test_scores_are_score_entries(self):
        from src.strategist.schemas import ScoreEntry

        report = self._make_report()
        assert isinstance(report.scores["technical"], ScoreEntry)

    def test_raw_data_paths_accepts_none(self):
        report = self._make_report()
        assert report.raw_data_paths["moneyflow"] is None


# ── 行为 3：_build_raw_data_paths ────────────────────────────────


class TestBuildRawDataPaths:
    def test_returns_dict_with_expected_keys(self):
        from src.publisher.schemas import _build_raw_data_paths

        with tempfile.TemporaryDirectory() as tmp:
            paths = _build_raw_data_paths("600519.SH", data_root=tmp)
            for key in ["daily", "daily_basic", "fina_indicator", "income", "moneyflow"]:
                assert key in paths

    def test_existing_file_returns_path_string(self):
        from src.publisher.schemas import _build_raw_data_paths

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "600519.SH"
            data_dir.mkdir(parents=True)
            (data_dir / "daily.parquet").touch()

            paths = _build_raw_data_paths("600519.SH", data_root=tmp)
            assert paths["daily"] is not None
            assert "daily.parquet" in str(paths["daily"])

    def test_missing_file_returns_none(self):
        from src.publisher.schemas import _build_raw_data_paths

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "600519.SH"
            data_dir.mkdir(parents=True)

            paths = _build_raw_data_paths("600519.SH", data_root=tmp)
            assert paths["daily"] is None
            assert paths["moneyflow"] is None
