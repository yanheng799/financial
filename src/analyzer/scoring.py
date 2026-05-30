"""三维评分函数——score_technical、score_fundamental、score_capital"""

from src.analyzer.schemas import DimensionScore, load_scoring_config


def score_technical(indicators: dict, daily_count: int) -> DimensionScore:
    """技术面评分：MA 排列 + MACD 柱方向 + 成交量修正。

    Args:
        indicators: compute_technical_indicators() 的输出
        daily_count: 可用日线行数，用于判断降级

    Returns:
        DimensionScore（value 在 -2~+2）
    """
    config = load_scoring_config()
    min_rows = config["min_daily_rows"]

    # 数据不足
    if daily_count < min_rows:
        return DimensionScore(value=0, reason="日线数据不足，无法计算技术指标", data_sufficient=False)

    score = 0
    reasons = []

    # MA 排列（需要 ma60）
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

    # MACD 柱方向
    macd_hist = indicators.get("macd_hist")
    macd_hist_prev = indicators.get("macd_hist_prev")

    if macd_hist is not None and macd_hist_prev is not None:
        if macd_hist > 0 and macd_hist > macd_hist_prev:
            score += 1
            reasons.append("MACD柱扩张")
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            score -= 1
            reasons.append("MACD柱缩减")

    # 成交量修正
    vol_ratio = indicators.get("vol_ratio")
    if vol_ratio is not None and vol_ratio < config["vol_ratio"]["weaken"]:
        score = int(score * 0.5)
        # vol_ratio >= confirm → 保持分数（放量确认）

    # clamp
    score = max(-2, min(2, score))

    return DimensionScore(
        value=score,
        reason="；".join(reasons) if reasons else "无明显信号",
        data_sufficient=True,
    )
