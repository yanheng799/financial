"""Issue #12 测试：技术指标计算 + score_technical() 评分函数"""

from src.analyzer.schemas import load_scoring_config


def _make_daily_data(rows: int, trend: str = "up") -> list[dict]:
    """生成 mock 日线数据。trend='up' 递增, 'down' 递减, 'flat' 平坦"""
    data = []
    for i in range(rows):
        if trend == "up":
            close = 100.0 + i * 1.0
        elif trend == "down":
            close = 200.0 - i * 1.0
        else:
            close = 150.0
        data.append(
            {
                "ts_code": "600519.SH",
                "trade_date": f"20260{i + 1:02d}01",
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "vol": 50000.0,
                "amount": 9000000.0,
            }
        )
    return data


def _make_daily_with_volume(rows: int, vol_multiplier: float = 1.0) -> list[dict]:
    """生成带特定成交量的日线数据（上升趋势）"""
    data = []
    for i in range(rows):
        close = 100.0 + i * 1.0
        data.append(
            {
                "ts_code": "600519.SH",
                "trade_date": f"20260{i + 1:02d}01",
                "open": close - 0.5,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "vol": 50000.0 * vol_multiplier,
                "amount": 9000000.0 * vol_multiplier,
            }
        )
    return data


# ── 行为 1：指标计算 compute_technical_indicators ─────────────


class TestComputeTechnicalIndicators:
    """compute_technical_indicators 从 OHLCV 数据计算 MA/MACD/vol_ratio"""

    def test_returns_dict_with_required_keys(self):
        from src.analyzer.indicators import compute_technical_indicators

        data = _make_daily_data(100)
        result = compute_technical_indicators(data)
        assert "ma5" in result
        assert "ma20" in result
        assert "ma60" in result
        assert "macd_hist" in result
        assert "macd_hist_prev" in result
        assert "vol_ratio" in result

    def test_ma_values_are_floats(self):
        from src.analyzer.indicators import compute_technical_indicators

        data = _make_daily_data(100)
        result = compute_technical_indicators(data)
        assert isinstance(result["ma5"], float)
        assert isinstance(result["ma20"], float)
        assert isinstance(result["ma60"], float)

    def test_vol_ratio_calculation(self):
        from src.analyzer.indicators import compute_technical_indicators

        # 构造数据：所有行 vol=50000，最新一行 vol=100000
        data = []
        for i in range(99):
            data.append(
                {
                    "ts_code": "600519.SH",
                    "trade_date": f"202501{i + 1:02d}",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.0,
                    "vol": 50000.0,
                    "amount": 5000000.0,
                }
            )
        data.append(
            {
                "ts_code": "600519.SH",
                "trade_date": "20260101",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "vol": 100000.0,
                "amount": 10000000.0,
            }
        )
        result = compute_technical_indicators(data)
        # vol_ratio = last_vol / mean(last 20 vols)
        # = 100000 / (19*50000 + 100000)/20 = 100000 / 52500 ≈ 1.905
        assert result["vol_ratio"] > 1.8  # 明确高于均量
        assert isinstance(result["vol_ratio"], float)

    def test_insufficient_data_returns_none_indicators(self):
        from src.analyzer.indicators import compute_technical_indicators

        data = _make_daily_data(3)
        result = compute_technical_indicators(data)
        # MA60 不可用时为 None
        assert result["ma60"] is None
        assert result["macd_hist"] is None
        assert result["macd_hist_prev"] is None


# ── 行为 2：score_technical 评分规则 ─────────────────────────


class TestScoreTechnicalBullish:
    """多头排列 + MACD 扩张"""

    def test_full_bullish_with_high_volume(self):
        """MA 多头 + MACD 扩张 + 放量 → value=2"""
        from src.analyzer.scoring import score_technical

        indicators = {
            "ma5": 150.0,
            "ma20": 145.0,
            "ma60": 140.0,
            "macd_hist": 0.5,
            "macd_hist_prev": 0.3,
            "vol_ratio": 1.8,
        }
        result = score_technical(indicators, daily_count=100)
        assert result.value == 2
        assert "均线多头排列" in result.reason
        assert "MACD柱扩张" in result.reason

    def test_bullish_ma_only(self):
        """仅多头排列，MACD 不扩张 → value=1"""
        from src.analyzer.scoring import score_technical

        indicators = {
            "ma5": 150.0,
            "ma20": 145.0,
            "ma60": 140.0,
            "macd_hist": 0.5,
            "macd_hist_prev": 0.6,  # 收缩
            "vol_ratio": 1.0,
        }
        result = score_technical(indicators, daily_count=100)
        assert result.value == 1
        assert "均线多头排列" in result.reason


class TestScoreTechnicalBearish:
    """空头排列 + MACD 缩减"""

    def test_full_bearish(self):
        """MA 空头 + MACD 缩减 → value=-2"""
        from src.analyzer.scoring import score_technical

        indicators = {
            "ma5": 140.0,
            "ma20": 145.0,
            "ma60": 150.0,
            "macd_hist": -0.5,
            "macd_hist_prev": -0.3,
            "vol_ratio": 1.0,
        }
        result = score_technical(indicators, daily_count=100)
        assert result.value == -2
        assert "均线空头排列" in result.reason
        assert "MACD柱缩减" in result.reason

    def test_bearish_ma_only(self):
        """仅空头排列 → value=-1"""
        from src.analyzer.scoring import score_technical

        indicators = {
            "ma5": 140.0,
            "ma20": 145.0,
            "ma60": 150.0,
            "macd_hist": -0.5,
            "macd_hist_prev": -0.6,  # 收窄（不是缩减）
            "vol_ratio": 1.0,
        }
        result = score_technical(indicators, daily_count=100)
        assert result.value == -1


class TestScoreTechnicalVolumeModifier:
    """成交量修正：放量确认、缩量削弱"""

    def test_low_volume_weakens_score(self):
        """vol_ratio < 0.7 → 分数削弱为 int(score * 0.5)"""
        from src.analyzer.scoring import score_technical

        # 多头 + MACD 扩张 → raw score = 2, 缩量 → int(2 * 0.5) = 1
        indicators = {
            "ma5": 150.0,
            "ma20": 145.0,
            "ma60": 140.0,
            "macd_hist": 0.5,
            "macd_hist_prev": 0.3,
            "vol_ratio": 0.5,
        }
        result = score_technical(indicators, daily_count=100)
        assert result.value == 1

    def test_high_volume_preserves_score(self):
        """vol_ratio > 1.5 → 分数不变"""
        from src.analyzer.scoring import score_technical

        # 多头 → raw score = 1, 放量 → 保持 1
        indicators = {
            "ma5": 150.0,
            "ma20": 145.0,
            "ma60": 140.0,
            "macd_hist": 0.5,
            "macd_hist_prev": 0.6,
            "vol_ratio": 1.8,
        }
        result = score_technical(indicators, daily_count=100)
        assert result.value == 1


# ── 行为 3：降级处理 ──────────────────────────────────────


class TestScoreTechnicalDegradation:
    """数据不足时的降级行为"""

    def test_no_ma60_skips_ma_arrangement(self):
        """日线 30 行（MA60 不可用）→ 跳过 MA 排列，data_sufficient=True"""
        from src.analyzer.scoring import score_technical

        indicators = {
            "ma5": 150.0,
            "ma20": 145.0,
            "ma60": None,
            "macd_hist": 0.5,
            "macd_hist_prev": 0.3,
            "vol_ratio": 1.0,
        }
        result = score_technical(indicators, daily_count=30)
        assert result.data_sufficient is True
        assert "均线" not in result.reason  # MA 排列被跳过
        assert result.value == 1  # 仅 MACD +1

    def test_too_few_rows_returns_zero(self):
        """日线仅 3 行 → value=0, data_sufficient=False"""
        from src.analyzer.scoring import score_technical

        indicators = {
            "ma5": None,
            "ma20": None,
            "ma60": None,
            "macd_hist": None,
            "macd_hist_prev": None,
            "vol_ratio": None,
        }
        result = score_technical(indicators, daily_count=3)
        assert result.value == 0
        assert result.data_sufficient is False
        assert "数据不足" in result.reason


# ── 行为 4：阈值从配置文件读取 ──────────────────────────────


class TestScoreTechnicalConfig:
    """vol_ratio 阈值从配置文件读取，不硬编码"""

    def test_thresholds_match_config(self):
        from src.analyzer.scoring import score_technical

        config = load_scoring_config()
        # 确认函数使用了配置中的阈值（通过行为验证）
        # vol_ratio = confirm - 0.01 → 不触发确认（恰好低于阈值）
        indicators = {
            "ma5": 150.0,
            "ma20": 145.0,
            "ma60": 140.0,
            "macd_hist": 0.5,
            "macd_hist_prev": 0.3,
            "vol_ratio": config["vol_ratio"]["weaken"] - 0.01,  # 0.69
        }
        result = score_technical(indicators, daily_count=100)
        # vol_ratio=0.69 < 0.7 → 削弱：int(2 * 0.5) = 1
        assert result.value == 1
