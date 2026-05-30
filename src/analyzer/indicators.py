"""技术指标计算——MA、MACD、成交量比"""

import pandas as pd
import pandas_ta_classic as ta


def compute_technical_indicators(daily_data: list[dict]) -> dict:
    """从 OHLCV 日线数据计算技术指标。

    Args:
        daily_data: daily 接口返回的数据行列表（list[dict]），
                    已按 trade_date 降序排列（最新在前）

    Returns:
        包含 ma5/ma20/ma60/macd_hist/macd_hist_prev/vol_ratio 的 dict。
        不可计算的指标值为 None。
    """
    if not daily_data:
        return _empty_indicators()

    df = pd.DataFrame(daily_data)
    # 转为升序（最旧在前），便于计算均线
    df = df.sort_values("trade_date", ascending=True).reset_index(drop=True)

    close = df["close"].astype(float)
    vol = df["vol"].astype(float)

    result = {}

    # MA
    sma5 = ta.sma(close, length=5)
    sma20 = ta.sma(close, length=20)
    sma60 = ta.sma(close, length=60)
    result["ma5"] = _last_value(sma5)
    result["ma20"] = _last_value(sma20)
    result["ma60"] = _last_value(sma60)

    # MACD
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty and len(macd_df) >= 2:
        hist = macd_df["MACDh_12_26_9"]
        result["macd_hist"] = _last_value(hist)
        result["macd_hist_prev"] = _value_at(hist, -2)
    else:
        result["macd_hist"] = None
        result["macd_hist_prev"] = None

    # vol_ratio：当日 vol / 近 20 日均值
    if len(vol) >= 20:
        mean_vol = vol.iloc[-20:].mean()
        result["vol_ratio"] = round(float(vol.iloc[-1]) / mean_vol, 4) if mean_vol > 0 else None
    else:
        result["vol_ratio"] = None

    return result


def _last_value(series: pd.Series | None) -> float | None:
    """取 Series 最后一个非 NaN 值。pandas-ta 数据不足时返回 None。"""
    if series is None:
        return None
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])


def _value_at(series: pd.Series, pos: int) -> float | None:
    """取 Series 指定位置的最后一个非 NaN 值"""
    valid = series.dropna()
    idx = len(valid) + pos  # pos 是负数，如 -2 表示倒数第二个
    if idx < 0 or idx >= len(valid):
        return None
    return float(valid.iloc[idx])


def _empty_indicators() -> dict:
    return {
        "ma5": None,
        "ma20": None,
        "ma60": None,
        "macd_hist": None,
        "macd_hist_prev": None,
        "vol_ratio": None,
    }
