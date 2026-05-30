"""技术指标计算——MA、MACD、成交量比、基本面、资金面"""

import pandas as pd
import pandas_ta_classic as ta

from src.analyzer.schemas import load_scoring_config


def compute_technical_indicators(daily_data: list[dict]) -> dict:
    """从 OHLCV 日线数据计算技术指标。"""
    if not daily_data:
        return _empty_indicators()

    df = pd.DataFrame(daily_data)
    df = df.sort_values("trade_date", ascending=True).reset_index(drop=True)

    close = df["close"].astype(float)
    vol = df["vol"].astype(float)

    result = {}

    sma5 = ta.sma(close, length=5)
    sma20 = ta.sma(close, length=20)
    sma60 = ta.sma(close, length=60)
    result["ma5"] = _last_value(sma5)
    result["ma20"] = _last_value(sma20)
    result["ma60"] = _last_value(sma60)

    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty and len(macd_df) >= 2:
        hist = macd_df["MACDh_12_26_9"]
        result["macd_hist"] = _last_value(hist)
        result["macd_hist_prev"] = _value_at(hist, -2)
    else:
        result["macd_hist"] = None
        result["macd_hist_prev"] = None

    if len(vol) >= 20:
        mean_vol = vol.iloc[-20:].mean()
        result["vol_ratio"] = round(float(vol.iloc[-1]) / mean_vol, 4) if mean_vol > 0 else None
    else:
        result["vol_ratio"] = None

    return result


def compute_fundamental_indicators(fundamental_data: dict) -> dict:
    """从估值和财务数据提取基本面指标。"""
    result = {
        "pe_ttm": None,
        "pe_percentile_1y": None,
        "roe_yearly": None,
        "tr_yoy": None,
        "netprofit_yoy": None,
    }

    daily_basic = fundamental_data.get("daily_basic", [])
    if daily_basic:
        pe_values = [(r.get("trade_date", ""), r.get("pe_ttm")) for r in daily_basic if r.get("pe_ttm") is not None]
        if pe_values:
            pe_values.sort(key=lambda x: x[0], reverse=True)
            latest_pe = pe_values[0][1]
            pe_list = [v[1] for v in pe_values]
            rank = sum(1 for p in pe_list if p < latest_pe)
            percentile = round(rank / len(pe_list) * 100, 2)
            result["pe_ttm"] = latest_pe
            result["pe_percentile_1y"] = percentile

    fina = fundamental_data.get("fina_indicator", [])
    if fina:
        sorted_fina = sorted(fina, key=lambda r: r.get("end_date", ""), reverse=True)
        latest = sorted_fina[0]
        result["roe_yearly"] = latest.get("roe_yearly")
        result["tr_yoy"] = latest.get("tr_yoy")
        result["netprofit_yoy"] = latest.get("netprofit_yoy")

    return result


def compute_capital_indicators(capital_data: dict) -> dict:
    """从资金流数据计算资金面指标。"""
    config = load_scoring_config()
    days = config["capital_flow"]["days"]

    result = {
        "net_mf_amount_5d": None,
        "lg_buy_sell_ratio": None,
    }

    data = capital_data.get("data") or []
    if not data:
        return result

    recent = data[:days]

    net_mf_values = [r.get("net_mf_amount") for r in recent if r.get("net_mf_amount") is not None]
    if len(net_mf_values) >= days:
        result["net_mf_amount_5d"] = sum(net_mf_values)

    latest = data[0]
    buy = latest.get("buy_lg_amount")
    sell = latest.get("sell_lg_amount")
    if buy is not None and sell is not None and sell > 0:
        result["lg_buy_sell_ratio"] = round(buy / sell, 4)

    return result


def _last_value(series: pd.Series | None) -> float | None:
    """取 Series 最后一个非 NaN 值。pandas-ta 数据不足时返回 None。"""
    if series is None:
        return None
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])


def _value_at(series: pd.Series | None, pos: int) -> float | None:
    """取 Series 指定位置的最后一个非 NaN 值"""
    if series is None:
        return None
    valid = series.dropna()
    idx = len(valid) + pos
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
