"""Parquet 文件读写与缓存逻辑——数据采集 Agent 的持久化层"""

from pathlib import Path

import pandas as pd

from src.collector.schemas import (
    CapitalFlowData,
    DailyQuoteData,
    FundData,
    RawData,
)

# ── 目录结构常量 ──────────────────────────────────────────

_DIR_DAILY = "daily"
_DIR_FUNDAMENTAL = "fundamental"
_DIR_CAPITAL = "capital"


def _ensure_dir(path: Path) -> None:
    """确保目录存在。"""
    path.mkdir(parents=True, exist_ok=True)


# ── 写入函数 ──────────────────────────────────────────────


def _save_daily(data: DailyQuoteData, base_dir: Path) -> None:
    """将日线数据写入 Parquet 文件。"""
    if not data.data:
        return
    rows = [row.model_dump() for row in data.data]
    ts_code = rows[0]["ts_code"]
    out_dir = base_dir / _DIR_DAILY
    _ensure_dir(out_dir)
    pd.DataFrame(rows).to_parquet(out_dir / f"{ts_code}.parquet", index=False)


def _save_fundamental(fund: FundData, base_dir: Path) -> None:
    """将基本面数据按接口拆分为 3 个 Parquet 文件。"""
    ts_code = _extract_ts_code(fund)
    if ts_code is None:
        return
    out_dir = base_dir / _DIR_FUNDAMENTAL
    _ensure_dir(out_dir)
    for suffix, rows in [
        ("daily_basic", fund.daily_basic),
        ("fina_indicator", fund.fina_indicator),
        ("income", fund.income),
    ]:
        if rows:
            pd.DataFrame(rows).to_parquet(out_dir / f"{ts_code}_{suffix}.parquet", index=False)


def _save_capital(capital: CapitalFlowData, base_dir: Path) -> None:
    """将资金流数据写入 Parquet 文件。insufficient 或空数据时不写文件。"""
    if capital.insufficient or capital.data is None or len(capital.data) == 0:
        return
    ts_code = capital.data[0]["ts_code"]
    out_dir = base_dir / _DIR_CAPITAL
    _ensure_dir(out_dir)
    pd.DataFrame(capital.data).to_parquet(out_dir / f"{ts_code}.parquet", index=False)


def _extract_ts_code(fund: FundData) -> str | None:
    """从 FundData 的任一非空列表中提取 ts_code。"""
    for rows in [fund.daily_basic, fund.fina_indicator, fund.income]:
        if rows:
            return rows[0].get("ts_code")
    return None


def save_all(raw: RawData, base_dir: Path) -> None:
    """将 RawData 按维度写入 Parquet 文件。

    Args:
        raw: 完整的采集数据
        base_dir: 数据根目录（如 Path("data")）
    """
    _save_daily(raw.daily, base_dir)
    _save_fundamental(raw.fundamental, base_dir)
    _save_capital(raw.capital, base_dir)


# ── 读取函数 ──────────────────────────────────────────────


def _load_daily(ts_code: str, base_dir: Path) -> DailyQuoteData:
    """从 Parquet 文件读取日线数据。"""
    path = base_dir / _DIR_DAILY / f"{ts_code}.parquet"
    if not path.is_file():
        return DailyQuoteData(data=[])
    rows = pd.read_parquet(path).to_dict(orient="records")
    return DailyQuoteData(data=rows)


def _load_fundamental(ts_code: str, base_dir: Path) -> FundData:
    """从 3 个 Parquet 文件读取基本面数据。"""
    fund_dir = base_dir / _DIR_FUNDAMENTAL
    result = {}
    for suffix in ["daily_basic", "fina_indicator", "income"]:
        path = fund_dir / f"{ts_code}_{suffix}.parquet"
        if path.is_file():
            result[suffix] = pd.read_parquet(path).to_dict(orient="records")
        else:
            result[suffix] = []
    return FundData(**result)


def _load_capital(ts_code: str, base_dir: Path) -> CapitalFlowData:
    """从 Parquet 文件读取资金流数据。文件不存在时返回 insufficient。"""
    path = base_dir / _DIR_CAPITAL / f"{ts_code}.parquet"
    if not path.is_file():
        return CapitalFlowData(data=None, insufficient=True)
    rows = pd.read_parquet(path).to_dict(orient="records")
    return CapitalFlowData(data=rows, insufficient=False)


def load(ts_code: str, base_dir: Path) -> RawData:
    """从本地 Parquet 文件加载数据为 RawData。

    Args:
        ts_code: 股票代码（如 '600519.SH'）
        base_dir: 数据根目录

    Returns:
        RawData 对象
    """
    return RawData(
        daily=_load_daily(ts_code, base_dir),
        fundamental=_load_fundamental(ts_code, base_dir),
        capital=_load_capital(ts_code, base_dir),
    )


# ── 缓存判断 ──────────────────────────────────────────────

# 缓存所需的文件模式：(子目录, 文件名模板)
_REQUIRED_FILES = [
    (_DIR_DAILY, "{ts_code}.parquet"),
    (_DIR_FUNDAMENTAL, "{ts_code}_daily_basic.parquet"),
    (_DIR_FUNDAMENTAL, "{ts_code}_fina_indicator.parquet"),
    (_DIR_FUNDAMENTAL, "{ts_code}_income.parquet"),
]
# capital 文件可选（insufficient 时不存在）


def is_cached(ts_code: str, base_dir: Path) -> bool:
    """检查本地是否已有全部必要维度的 Parquet 文件。

    daily + 3 个 fundamental 文件必须存在。capital 文件可选。

    Args:
        ts_code: 股票代码
        base_dir: 数据根目录

    Returns:
        True 如果全部必要文件都存在
    """
    for subdir, filename_tmpl in _REQUIRED_FILES:
        path = base_dir / subdir / filename_tmpl.format(ts_code=ts_code)
        if not path.is_file():
            return False
    return True
