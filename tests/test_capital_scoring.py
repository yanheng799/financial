"""Issue #14 测试：资金面指标计算 + score_capital() 评分函数"""

from src.analyzer.schemas import load_scoring_config


def _make_capital_data(net_mf_values=None, buy_lg=500000.0, sell_lg=400000.0, insufficient=False):
    """构造 mock 资金流数据。capital.data 已按 trade_date 降序排列。"""
    data = []
    if net_mf_values:
        for i, mf in enumerate(net_mf_values):
            data.append({
                "ts_code": "600519.SH",
                "trade_date": f"20260{5 - i:02d}28",
                "net_mf_amount": mf,
                "buy_lg_amount": buy_lg,
                "sell_lg_amount": sell_lg,
            })
    return {"data": data, "insufficient": insufficient}


# ── 行为 1：指标计算 ──────────────────────────────────────


class TestComputeCapitalIndicators:
    """compute_capital_indicators 从资金流数据提取指标"""

    def test_returns_required_keys(self):
        from src.analyzer.indicators import compute_capital_indicators

        data = _make_capital_data(net_mf_values=[1000, 2000, -500, 3000, 1500])
        result = compute_capital_indicators(data)
        assert "net_mf_amount_5d" in result
        assert "lg_buy_sell_ratio" in result

    def test_net_flow_sum(self):
        """近 5 日净流入合计正确"""
        from src.analyzer.indicators import compute_capital_indicators

        data = _make_capital_data(net_mf_values=[1000, 2000, -500, 3000, 1500])
        result = compute_capital_indicators(data)
        assert result["net_mf_amount_5d"] == 7000.0  # sum = 1000+2000-500+3000+1500

    def test_lg_ratio(self):
        """大单买卖比率正确"""
        from src.analyzer.indicators import compute_capital_indicators

        data = _make_capital_data(net_mf_values=[1000], buy_lg=750000.0, sell_lg=500000.0)
        result = compute_capital_indicators(data)
        assert result["lg_buy_sell_ratio"] == 1.5

    def test_insufficient_data_skips(self):
        """不足回看天数 → 对应指标为 None"""
        from src.analyzer.indicators import compute_capital_indicators

        data = _make_capital_data(net_mf_values=[1000])  # only 1 row
        result = compute_capital_indicators(data)
        assert result["net_mf_amount_5d"] is None

    def test_empty_data_returns_none(self):
        """资金流数据为空 → 所有指标为 None"""
        from src.analyzer.indicators import compute_capital_indicators

        data = _make_capital_data(net_mf_values=[])
        result = compute_capital_indicators(data)
        assert result["net_mf_amount_5d"] is None
        assert result["lg_buy_sell_ratio"] is None


# ── 行为 2：评分规则 ──────────────────────────────────────


class TestScoreCapitalRules:
    """score_capital 两条规则正确触发"""

    def test_bullish_scores_plus2(self):
        """净流入 + 大单买入强势 → value=2"""
        from src.analyzer.scoring import score_capital

        indicators = {"net_mf_amount_5d": 5000.0, "lg_buy_sell_ratio": 2.0}
        result = score_capital(indicators, insufficient=False, has_data=True)
        assert result.value == 2
        assert "近5日主力净流入" in result.reason
        assert "大单买入强势" in result.reason

    def test_bearish_scores_minus2(self):
        """净流出 + 大单卖出弱势 → value=-2"""
        from src.analyzer.scoring import score_capital

        indicators = {"net_mf_amount_5d": -3000.0, "lg_buy_sell_ratio": 0.5}
        result = score_capital(indicators, insufficient=False, has_data=True)
        assert result.value == -2
        assert "近5日主力净流出" in result.reason
        assert "大单卖出强势" in result.reason

    def test_neutral_flow_no_signal(self):
        """无明确信号 → value=0"""
        from src.analyzer.scoring import score_capital

        indicators = {"net_mf_amount_5d": 0, "lg_buy_sell_ratio": 1.0}
        result = score_capital(indicators, insufficient=False, has_data=True)
        assert result.value == 0


# ── 行为 3：降级处理 ──────────────────────────────────────


class TestScoreCapitalDegradation:
    """数据不足时的降级"""

    def test_insufficient_flag(self):
        """insufficient=True → value=0, data_sufficient=False"""
        from src.analyzer.scoring import score_capital

        indicators = {"net_mf_amount_5d": None, "lg_buy_sell_ratio": None}
        result = score_capital(indicators, insufficient=True, has_data=False)
        assert result.value == 0
        assert result.data_sufficient is False
        assert "资金面数据不足" in result.reason

    def test_empty_data_not_insufficient(self):
        """数据为空但非 insufficient → value=0, data_sufficient=False"""
        from src.analyzer.scoring import score_capital

        indicators = {"net_mf_amount_5d": None, "lg_buy_sell_ratio": None}
        result = score_capital(indicators, insufficient=False, has_data=False)
        assert result.value == 0
        assert result.data_sufficient is False

    def test_partial_data_still_sufficient(self):
        """数据仅 2 行 → 按可用数据计算, data_sufficient=True"""
        from src.analyzer.scoring import score_capital

        # 仅大单比率可用，净流入不可用
        indicators = {"net_mf_amount_5d": None, "lg_buy_sell_ratio": 2.0}
        result = score_capital(indicators, insufficient=False, has_data=True)
        assert result.data_sufficient is True
        assert result.value >= 0  # 至少大单规则得分


# ── 行为 4：阈值可配置 ──────────────────────────────────


class TestScoreCapitalConfig:
    """阈值从配置文件读取"""

    def test_ratio_thresholds_from_config(self):
        from src.analyzer.scoring import score_capital

        config = load_scoring_config()
        strong = config["lg_ratio"]["strong"]  # 1.5
        weak = config["lg_ratio"]["weak"]  # 0.67

        # 比率 = strong - 0.01 → 不触发"大单买入强势"
        indicators = {"net_mf_amount_5d": 0, "lg_buy_sell_ratio": strong - 0.01}
        result = score_capital(indicators, insufficient=False, has_data=True)
        assert "大单买入强势" not in result.reason

        # 比率 = weak + 0.01 → 不触发"大单卖出强势"
        indicators2 = {"net_mf_amount_5d": 0, "lg_buy_sell_ratio": weak + 0.01}
        result2 = score_capital(indicators2, insufficient=False, has_data=True)
        assert "大单卖出强势" not in result2.reason

    def test_days_from_config(self):
        from src.analyzer.indicators import compute_capital_indicators

        config = load_scoring_config()
        days = config["capital_flow"]["days"]
        assert days == 5

        # 构造 days 行数据 → 应该能计算出净流入
        data = _make_capital_data(net_mf_values=[100] * days)
        result = compute_capital_indicators(data)
        assert result["net_mf_amount_5d"] == 100 * days
