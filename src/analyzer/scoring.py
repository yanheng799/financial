"""三维评分函数——score_technical、score_fundamental、score_capital"""

from src.analyzer.schemas import DimensionScore, load_scoring_config


def score_technical(indicators: dict, daily_count: int) -> DimensionScore:
    """技术面评分：MA 排列 + MACD 柱方向 + 成交量修正。"""
    config = load_scoring_config()
    min_rows = config["min_daily_rows"]

    if daily_count < min_rows:
        return DimensionScore(value=0, reason="日线数据不足，无法计算技术指标", data_sufficient=False)

    score = 0
    reasons = []

    ma5 = indicators.get("ma5")
    ma20 = indicators.get("ma20")
    ma60 = indicators.get("ma60")

    if ma5 is not None and ma20 is not None and ma60 is not None:
        if ma5 > ma20 > ma60:
            score += 1
            reasons.append("均线多头排列")
        elif ma5 < ma20 < ma60:
            score -= 1
            reasons.append("均线空头排列")

    macd_hist = indicators.get("macd_hist")
    macd_hist_prev = indicators.get("macd_hist_prev")

    if macd_hist is not None and macd_hist_prev is not None:
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            score += 1
            reasons.append("MACD柱扩张")
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            score -= 1
            reasons.append("MACD柱缩减")

    vol_ratio = indicators.get("vol_ratio")
    if vol_ratio is not None and vol_ratio < config["vol_ratio"]["weaken"]:
        score = int(score * 0.5)

    score = max(-2, min(2, score))

    return DimensionScore(
        value=score,
        reason="；".join(reasons) if reasons else "无明显信号",
        data_sufficient=True,
    )


def score_fundamental(indicators: dict, has_fundamental: bool) -> DimensionScore:
    """基本面评分：PE 分位数 + ROE + 成长趋势。

    Args:
        indicators: compute_fundamental_indicators() 的输出
        has_fundamental: 是否有财报数据（fina_indicator 非空）

    Returns:
        DimensionScore（value 在 -2~+2）
    """
    config = load_scoring_config()

    # 完全无财务数据
    if not has_fundamental:
        return DimensionScore(value=0, reason="暂无财务数据", data_sufficient=False)

    score = 0
    reasons = []

    # 估值位置
    pe_percentile = indicators.get("pe_percentile_1y")
    if pe_percentile is not None:
        if pe_percentile < config["pe"]["low_percentile"]:
            score += 1
            reasons.append("PE处于近一年低位")
        elif pe_percentile >= config["pe"]["high_percentile"]:
            score -= 1
            reasons.append("PE处于近一年高位")

    # 盈利能力
    roe = indicators.get("roe_yearly")
    if roe is not None:
        roe_pct = roe * 100 if roe < 1 else roe  # 兼容小数和百分比两种格式
        if roe_pct > config["roe"]["high"]:
            score += 1
            reasons.append("ROE优秀(>15%)")
        elif roe_pct < config["roe"]["low"]:
            score -= 1
            reasons.append("ROE偏低(<3%)")

    # 成长趋势
    tr_yoy = indicators.get("tr_yoy")
    netprofit_yoy = indicators.get("netprofit_yoy")
    if tr_yoy is not None and netprofit_yoy is not None:
        tr_pct = tr_yoy * 100 if tr_yoy < 1 else tr_yoy
        np_pct = netprofit_yoy * 100 if netprofit_yoy < 1 else netprofit_yoy
        if tr_pct > config["yoy"]["high"] and np_pct > config["yoy"]["high"]:
            score += 1
            reasons.append("营收净利润双增长")
        elif tr_pct < 0 and np_pct < 0:
            score -= 1
            reasons.append("营收净利润双降")

    score = max(-2, min(2, score))

    return DimensionScore(
        value=score,
        reason="；".join(reasons) if reasons else "无明显信号",
        data_sufficient=True,
    )
