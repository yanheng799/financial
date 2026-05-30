"""Issue #21 测试：置信度计算 + DimensionScore → ScoreEntry 映射"""

import pytest

# ── helpers ──────────────────────────────────────────────────────────


def _ds(value, sufficient=True):
    """快速构造 DimensionScore"""
    from src.analyzer.schemas import DimensionScore

    return DimensionScore(value=value, reason="test", data_sufficient=sufficient)


# ── 行为 1：置信度计算 ───────────────────────────────────────


class TestComputeConfidence:
    def test_three_same_sign_high(self):
        """3 维方向一致 → 高"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(1),
            "fundamental": _ds(1),
            "capital": _ds(1),
        }
        assert compute_confidence(scores) == "高"

    def test_two_same_mid(self):
        """3 维中 2 维一致且无大分差 → 中"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(1),
            "fundamental": _ds(1),
            "capital": _ds(0),  # 0 不是同方向，但分差 = 1 不会触发低
        }
        assert compute_confidence(scores) == "中"

    def test_all_different_low(self):
        """3 维各不相同 → 低"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(1),
            "fundamental": _ds(0),
            "capital": _ds(-1),
        }
        assert compute_confidence(scores) == "低"

    def test_large_diff_low(self):
        """任意两维差 ≥ 2 → 低"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(2),
            "fundamental": _ds(2),
            "capital": _ds(-1),
        }
        # diff = |2 - (-1)| = 3 >= 2 → 低
        assert compute_confidence(scores) == "低"

    def test_two_dim_after_filter_agree_high(self):
        """排除 insufficient 后 2 维一致 → 高"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(1),
            "fundamental": _ds(-1, sufficient=False),  # 排除
            "capital": _ds(1),
        }
        assert compute_confidence(scores) == "高"

    def test_two_dim_after_filter_disagree_low(self):
        """排除 insufficient 后 2 维不一致 → 低"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(1),
            "fundamental": _ds(-1, sufficient=False),  # 排除
            "capital": _ds(-1),
        }
        assert compute_confidence(scores) == "低"

    def test_one_dim_low(self):
        """仅 1 维有效 → 低"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(1),
            "fundamental": _ds(0, sufficient=False),
            "capital": _ds(0, sufficient=False),
        }
        assert compute_confidence(scores) == "低"

    def test_zero_dim_raises(self):
        """0 维有效 → ValueError"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(0, sufficient=False),
            "fundamental": _ds(0, sufficient=False),
            "capital": _ds(0, sufficient=False),
        }
        with pytest.raises(ValueError):
            compute_confidence(scores)

    def test_all_zero_scores_high(self):
        """所有维得分为 0 且方向一致（同为零）→ 高"""
        from src.strategist.schemas import compute_confidence

        scores = {
            "technical": _ds(0),
            "fundamental": _ds(0),
            "capital": _ds(0),
        }
        assert compute_confidence(scores) == "高"


# ── 行为 2：DimensionScore → ScoreEntry 映射 ────────────────


class TestToScoreEntry:
    def test_determined(self):
        from src.analyzer.schemas import DimensionScore
        from src.strategist.schemas import to_score_entry

        ds = DimensionScore(value=1, reason="多头", data_sufficient=True)
        entry = to_score_entry(ds)
        assert entry.value == 1
        assert entry.confidence == "determined"

    def test_insufficient(self):
        from src.analyzer.schemas import DimensionScore
        from src.strategist.schemas import to_score_entry

        ds = DimensionScore(value=0, reason="数据不足", data_sufficient=False)
        entry = to_score_entry(ds)
        assert entry.value == 0
        assert entry.confidence == "insufficient"

    def test_reason_preserved(self):
        from src.analyzer.schemas import DimensionScore
        from src.strategist.schemas import to_score_entry

        ds = DimensionScore(value=-1, reason="MACD缩减", data_sufficient=True)
        entry = to_score_entry(ds)
        assert entry.reason == "MACD缩减"
