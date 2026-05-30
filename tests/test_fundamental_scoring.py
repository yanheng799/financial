"""Issue #13 测试：基本面指标计算 + score_fundamental() 评分函数"""

from src.analyzer.schemas import load_scoring_config


def _make_fundamental_data(pe_ttm_values=None, roe_yearly=None, tr_yoy=None, netprofit_yoy=None, pe_empty=False):
    """构造 mock fundamental 数据。

    Args:
        pe_ttm_values: daily_basic 中的 pe_ttm 值列表（用于分位数计算）
        roe_yearly: 最新季年化 ROE
        tr_yoy: 营收同比
        netprofit_yoy: 净利润同比
        pe_empty: 是否让 pe_ttm 全部为 None
    """
    daily_basic = []
    if pe_ttm_values:
        for i, pe in enumerate(pe_ttm_values):
            daily_basic.append({
                "ts_code": "600519.SH",
                "trade_date": f"2025{i+1:02d}01",
                "pe_ttm": None if pe_empty else pe,
                "pb": 5.0,
            })
    fina_indicator = []
    if roe_yearly is not None or tr_yoy is not None or netprofit_yoy is not None:
        row = {
            "ts_code": "600519.SH",
            "end_date": "20260331",
        }
        if roe_yearly is not None:
            row["roe_yearly"] = roe_yearly
        if tr_yoy is not None:
            row["tr_yoy"] = tr_yoy
        if netprofit_yoy is not None:
            row["netprofit_yoy"] = netprofit_yoy
        fina_indicator.append(row)
    return {"daily_basic": daily_basic, "fina_indicator": fina_indicator}


# ── 行为 1：指标计算 ──────────────────────────────────────


class TestComputeFundamentalIndicators:
    """compute_fundamental_indicators 从估值和财务数据提取指标"""

    def test_returns_required_keys(self):
        from src.analyzer.indicators import compute_fundamental_indicators

        data = _make_fundamental_data(
            pe_ttm_values=[20.0, 25.0, 30.0, 35.0, 40.0],
            roe_yearly=0.31,
            tr_yoy=0.12,
            netprofit_yoy=0.15,
        )
        result = compute_fundamental_indicators(data)
        assert "pe_ttm" in result
        assert "pe_percentile_1y" in result
        assert "roe_yearly" in result
        assert "tr_yoy" in result
        assert "netprofit_yoy" in result

    def test_pe_percentile_low(self):
        """最新 PE 处于低位 → 低百分位"""
        from src.analyzer.indicators import compute_fundamental_indicators

        # 最后一项 trade_date 最大（最新），pe=20 为最低值
        data = _make_fundamental_data(pe_ttm_values=[40.0, 35.0, 30.0, 25.0, 20.0])
        result = compute_fundamental_indicators(data)
        assert result["pe_ttm"] == 20.0
        assert result["pe_percentile_1y"] < 30

    def test_pe_percentile_high(self):
        """最新 PE 处于高位 → 高百分位"""
        from src.analyzer.indicators import compute_fundamental_indicators

        # 最后一项 trade_date 最大（最新），pe=40 为最高值
        data = _make_fundamental_data(pe_ttm_values=[20.0, 25.0, 30.0, 35.0, 40.0])
        result = compute_fundamental_indicators(data)
        assert result["pe_ttm"] == 40.0
        assert result["pe_percentile_1y"] > 70

    def test_pe_empty_returns_none(self):
        """PE_TTM 不存在时返回 None"""
        from src.analyzer.indicators import compute_fundamental_indicators

        data = _make_fundamental_data(pe_ttm_values=[], pe_empty=True)
        result = compute_fundamental_indicators(data)
        assert result["pe_ttm"] is None
        assert result["pe_percentile_1y"] is None

    def test_no_fina_indicator_returns_none(self):
        """无财报数据时 roe/yoy 指标为 None"""
        from src.analyzer.indicators import compute_fundamental_indicators

        data = _make_fundamental_data(pe_ttm_values=[20.0, 30.0])
        result = compute_fundamental_indicators(data)
        assert result["roe_yearly"] is None
        assert result["tr_yoy"] is None
        assert result["netprofit_yoy"] is None


# ── 行为 2：评分规则 ──────────────────────────────────────


class TestScoreFundamentalRules:
    """score_fundamental 三条规则正确触发"""

    def test_all_bullish_scores_plus2(self):
        """PE 低位 + ROE 优秀 + 双增长 → value=2"""
        from src.analyzer.scoring import score_fundamental

        indicators = {
            "pe_ttm": 25.0,
            "pe_percentile_1y": 25.0,
            "roe_yearly": 0.20,
            "tr_yoy": 0.15,
            "netprofit_yoy": 0.12,
        }
        result = score_fundamental(indicators, has_fundamental=True)
        assert result.value == 2
        assert "PE处于近一年低位" in result.reason
        assert "ROE优秀" in result.reason
        assert "营收净利润双增长" in result.reason

    def test_pe_high_scores_minus1(self):
        """仅 PE 高位，其余中性 → value=-1"""
        from src.analyzer.scoring import score_fundamental

        indicators = {
            "pe_ttm": 35.0,
            "pe_percentile_1y": 80.0,
            "roe_yearly": 0.10,  # 中性
            "tr_yoy": 0.05,  # 中性
            "netprofit_yoy": 0.05,  # 中性
        }
        result = score_fundamental(indicators, has_fundamental=True)
        assert result.value == -1
        assert "PE处于近一年高位" in result.reason

    def test_double_decline_scores_minus1(self):
        """仅双降，其余中性 → value=-1"""
        from src.analyzer.scoring import score_fundamental

        indicators = {
            "pe_ttm": None,
            "pe_percentile_1y": 50.0,  # 中性分位
            "roe_yearly": 0.10,  # 中性
            "tr_yoy": -0.05,
            "netprofit_yoy": -0.08,
        }
        result = score_fundamental(indicators, has_fundamental=True)
        assert result.value == -1
        assert "营收净利润双降" in result.reason

    def test_roe_low_scores_minus1(self):
        """ROE 偏低 → value=-1"""
        from src.analyzer.scoring import score_fundamental

        indicators = {
            "pe_ttm": None,
            "pe_percentile_1y": None,
            "roe_yearly": 0.01,
            "tr_yoy": 0.05,
            "netprofit_yoy": 0.05,
        }
        result = score_fundamental(indicators, has_fundamental=True)
        assert result.value == -1
        assert "ROE偏低" in result.reason


# ── 行为 3：降级处理 ──────────────────────────────────────


class TestScoreFundamentalDegradation:
    """数据不足时的降级行为"""

    def test_pe_empty_skips_valuation(self):
        """PE_TTM 全空 → 跳过估值规则，按 ROE + 成长打分"""
        from src.analyzer.scoring import score_fundamental

        indicators = {
            "pe_ttm": None,
            "pe_percentile_1y": None,
            "roe_yearly": 0.20,
            "tr_yoy": 0.15,
            "netprofit_yoy": 0.12,
        }
        result = score_fundamental(indicators, has_fundamental=True)
        assert result.data_sufficient is True
        assert result.value == 2  # ROE +1, 成长 +1
        assert "PE" not in result.reason

    def test_no_financials_returns_insufficient(self):
        """无财报数据 → value=0, data_sufficient=False"""
        from src.analyzer.scoring import score_fundamental

        indicators = {
            "pe_ttm": None,
            "pe_percentile_1y": None,
            "roe_yearly": None,
            "tr_yoy": None,
            "netprofit_yoy": None,
        }
        result = score_fundamental(indicators, has_fundamental=False)
        assert result.value == 0
        assert result.data_sufficient is False
        assert "暂无财务数据" in result.reason


# ── 行为 4：阈值从配置读取 ──────────────────────────────


class TestScoreFundamentalConfig:
    """评分阈值从配置文件读取"""

    def test_roe_thresholds_from_config(self):
        from src.analyzer.scoring import score_fundamental

        config = load_scoring_config()
        roe_high = config["roe"]["high"]  # 15

        # roe_yearly = high - 0.01 → 恰好低于阈值 → 不触发"ROE优秀"
        indicators = {
            "pe_ttm": None,
            "pe_percentile_1y": None,
            "roe_yearly": (roe_high - 0.01) / 100,
            "tr_yoy": 0.0,
            "netprofit_yoy": 0.0,
        }
        result = score_fundamental(indicators, has_fundamental=True)
        assert "ROE优秀" not in result.reason
        assert "ROE偏低" not in result.reason  # roe=0.14 not below 3%
        assert result.value == 0

    def test_yoy_thresholds_from_config(self):
        from src.analyzer.scoring import score_fundamental

        config = load_scoring_config()
        yoy_high = config["yoy"]["high"]  # 10

        # YoY = high - 0.01 → 恰好低于阈值
        indicators = {
            "pe_ttm": None,
            "pe_percentile_1y": None,
            "roe_yearly": 0.10,
            "tr_yoy": (yoy_high - 0.01) / 100,
            "netprofit_yoy": (yoy_high + 0.01) / 100,  # 只有 netprofit 达标
        }
        result = score_fundamental(indicators, has_fundamental=True)
        # tr_yoy < 10%, netprofit_yoy > 10% → 不满足"双增长"条件
        assert "营收净利润双增长" not in result.reason
        assert result.value == 0
