"""Issue #23 测试：LLM prompt 构造"""


def _sample_report():
    """构造 mock TechnicalReport 数据"""
    from src.analyzer.schemas import DimensionScore

    return {
        "symbol": "600519.SH",
        "date": "20260530",
        "scores": {
            "technical": DimensionScore(value=1, reason="均线多头排列；MACD柱扩张", data_sufficient=True),
            "fundamental": DimensionScore(value=1, reason="PE处于近一年低位；ROE优秀(>15%)", data_sufficient=True),
            "capital": DimensionScore(value=-1, reason="近5日主力净流出", data_sufficient=True),
        },
        "indicators": {
            "ma5": 1850.2, "ma20": 1820.5, "ma60": 1780.0,
            "macd_hist": 0.04, "macd_hist_prev": 0.02, "vol_ratio": 1.8,
            "pe_ttm": 30.5, "pe_percentile_1y": 25.0,
            "roe_yearly": 0.31, "tr_yoy": 0.12, "netprofit_yoy": 0.15,
            "net_mf_amount_5d": -2.3e8, "lg_buy_sell_ratio": 0.6,
        },
    }


def _report_with_insufficient():
    """含 data_sufficient=False 维度的报告"""
    from src.analyzer.schemas import DimensionScore

    report = _sample_report()
    report["scores"]["capital"] = DimensionScore(value=0, reason="资金面数据不足", data_sufficient=False)
    return report


class TestBuildPrompt:
    def test_prompt_contains_all_scores(self):
        from src.strategist.node import build_prompt

        prompt = build_prompt(_sample_report())
        assert "技术面评分" in prompt
        assert "基本面评分" in prompt
        assert "资金面评分" in prompt

    def test_prompt_contains_score_values_and_reasons(self):
        from src.strategist.node import build_prompt

        prompt = build_prompt(_sample_report())
        assert "均线多头排列" in prompt
        assert "PE处于近一年低位" in prompt
        assert "近5日主力净流出" in prompt

    def test_prompt_contains_key_indicators(self):
        from src.strategist.node import build_prompt

        prompt = build_prompt(_sample_report())
        assert "MA5" in prompt
        assert "PE_TTM" in prompt
        assert "近5日主力净流入" in prompt

    def test_prompt_has_max_diff(self):
        from src.strategist.node import build_prompt

        prompt = build_prompt(_sample_report())
        assert "最大分差" in prompt

    def test_prompt_has_json_template(self):
        from src.strategist.node import build_prompt

        prompt = build_prompt(_sample_report())
        assert "overall_judgment" in prompt
        assert "bearish_factor" in prompt
        assert "conflict_detail" in prompt

    def test_prompt_excludes_code_injected_fields(self):
        """prompt 不再要求 LLM 输出代码注入的字段"""
        from src.strategist.node import build_prompt

        prompt = build_prompt(_sample_report())
        json_section = prompt[prompt.index("JSON"):]
        assert "confidence_level" not in json_section
        assert "conflict_detected" not in json_section
        assert '"symbol"' not in json_section
        assert '"date"' not in json_section
        assert '"scores"' not in json_section
        assert '"data_sources"' not in json_section
        assert '"generated_at"' not in json_section

    def test_prompt_has_constraints(self):
        from src.strategist.node import build_prompt

        prompt = build_prompt(_sample_report())
        assert "不得输出 JSON 之外的文字" in prompt
        assert "bearish_factor" in prompt
        assert "不要编造" in prompt

    def test_insufficient_dimension_annotated(self):
        from src.strategist.node import build_prompt

        prompt = build_prompt(_report_with_insufficient())
        assert "数据不足" in prompt
        assert "仅供参考" in prompt

    def test_prompt_is_string(self):
        from src.strategist.node import build_prompt

        prompt = build_prompt(_sample_report())
        assert isinstance(prompt, str)
        assert len(prompt) > 500
