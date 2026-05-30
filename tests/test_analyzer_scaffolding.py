"""Issue #11 测试：行情分析 Agent 脚手架——模块结构、Pydantic 模型、配置文件、pandas-ta 兼容性"""

from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

# ── 行为 1：模块骨架 ────────────────────────────────────────


class TestModuleStructure:
    """src/analyzer/ 目录和文件结构"""

    @pytest.mark.parametrize(
        "filename",
        ["__init__.py", "schemas.py", "indicators.py", "scoring.py", "node.py"],
    )
    def test_analyzer_module_files_exist(self, filename):
        from src import analyzer

        analyzer_dir = Path(analyzer.__file__).parent
        assert (analyzer_dir / filename).is_file(), f"Missing {filename} in src/analyzer/"

    def test_analyzer_directory_is_package(self):
        import src.analyzer

        assert hasattr(src.analyzer, "__file__")


# ── 行为 2：DimensionScore Pydantic 模型 ──────────────────────


class TestDimensionScore:
    """DimensionScore 可实例化，value 在 -2~+2"""

    def test_positive_score(self):
        from src.analyzer.schemas import DimensionScore

        score = DimensionScore(value=2, reason="均线多头排列；MACD柱扩张", data_sufficient=True)
        assert score.value == 2
        assert score.data_sufficient is True

    def test_negative_score(self):
        from src.analyzer.schemas import DimensionScore

        score = DimensionScore(value=-2, reason="均线空头排列", data_sufficient=True)
        assert score.value == -2

    def test_zero_score_with_insufficient_data(self):
        from src.analyzer.schemas import DimensionScore

        score = DimensionScore(value=0, reason="数据不足", data_sufficient=False)
        assert score.value == 0
        assert score.data_sufficient is False

    def test_value_above_range_raises(self):
        from src.analyzer.schemas import DimensionScore

        with pytest.raises(ValidationError):
            DimensionScore(value=3, reason="超出范围", data_sufficient=True)

    def test_value_below_range_raises(self):
        from src.analyzer.schemas import DimensionScore

        with pytest.raises(ValidationError):
            DimensionScore(value=-3, reason="超出范围", data_sufficient=True)


# ── 行为 3：TechnicalReport Pydantic 模型 ──────────────────────


class TestTechnicalReport:
    """TechnicalReport 可实例化并 model_dump() 返回完整 dict"""

    def _make_report(self):
        from src.analyzer.schemas import DimensionScore, TechnicalReport

        return TechnicalReport(
            symbol="600519.SH",
            date="20260530",
            scores={
                "technical": DimensionScore(value=1, reason="均线多头排列", data_sufficient=True),
                "fundamental": DimensionScore(value=0, reason="数据不足", data_sufficient=False),
                "capital": DimensionScore(value=-1, reason="近5日主力净流出", data_sufficient=True),
            },
            indicators={"ma5": 1850.2, "vol_ratio": 1.8},
            generated_at="2026-05-30T14:30:00",
        )

    def test_model_dump_returns_dict(self):
        report = self._make_report()
        dumped = report.model_dump()
        assert isinstance(dumped, dict)
        assert dumped["symbol"] == "600519.SH"
        assert dumped["date"] == "20260530"

    def test_scores_is_dict_of_dimension_scores(self):
        report = self._make_report()
        dumped = report.model_dump()
        assert "scores" in dumped
        assert "technical" in dumped["scores"]
        assert dumped["scores"]["technical"]["value"] == 1
        assert dumped["scores"]["fundamental"]["data_sufficient"] is False

    def test_indicators_is_dict(self):
        report = self._make_report()
        dumped = report.model_dump()
        assert isinstance(dumped["indicators"], dict)
        assert dumped["indicators"]["ma5"] == 1850.2


# ── 行为 4：配置文件 ──────────────────────────────────────


class TestScoringConfig:
    """configs/scoring.yaml 包含所有阈值参数，可被 Python 代码读取"""

    def test_config_file_exists(self):
        assert Path("configs/scoring.yaml").is_file()

    def test_config_contains_all_thresholds(self):
        from src.analyzer.schemas import load_scoring_config

        config = load_scoring_config()
        # Technical
        assert config["vol_ratio"]["confirm"] == 1.5
        assert config["vol_ratio"]["weaken"] == 0.7
        assert config["min_daily_rows"] == 5
        # Fundamental
        assert config["pe"]["low_percentile"] == 30
        assert config["pe"]["high_percentile"] == 70
        assert config["roe"]["high"] == 15
        assert config["roe"]["low"] == 3
        assert config["yoy"]["high"] == 10
        # Capital
        assert config["capital_flow"]["days"] == 5
        assert config["lg_ratio"]["strong"] == 1.5
        assert config["lg_ratio"]["weak"] == 0.67

    def test_config_returns_dict(self):
        from src.analyzer.schemas import load_scoring_config

        config = load_scoring_config()
        assert isinstance(config, dict)


# ── 行为 5：pandas-ta 兼容性验证 ──────────────────────────────


class TestPandasTaCompatibility:
    """pandas-ta 在 Python 3.11 + pandas 2.x 下可正常计算 MA 和 MACD"""

    def test_sma_calculation(self):
        import pandas_ta_classic as ta

        df = pd.DataFrame({"close": [float(i) for i in range(1, 21)]})
        sma5 = ta.sma(df["close"], length=5)
        # SMA5 at last row = mean(16, 17, 18, 19, 20) = 18.0
        assert sma5.iloc[-1] == 18.0

    def test_macd_calculation(self):
        import pandas_ta_classic as ta

        df = pd.DataFrame({"close": [100 + i * 0.5 for i in range(100)]})
        result = ta.macd(df["close"], fast=12, slow=26, signal=9)
        assert "MACD_12_26_9" in result.columns
        assert "MACDh_12_26_9" in result.columns
        assert "MACDs_12_26_9" in result.columns
        # MACD histogram should have values (not all NaN)
        assert result["MACDh_12_26_9"].notna().any()
