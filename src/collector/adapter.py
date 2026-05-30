"""Tushare API 调用封装——Token 初始化 + 各接口数据拉取"""

import json
import os
from datetime import date, timedelta

import tushare as ts

from src.collector.schemas import CapitalFlowData, DailyQuoteData, FundData, RawData


def calc_date_range(years: int = 0, quarters: int = 0) -> tuple[str, str]:
    """计算起止日期，返回 YYYYMMDD 格式字符串。

    Args:
        years: 往前推的年数（近似按 365 天/年计算）
        quarters: 往前推的季度数（近似按 90 天/季度计算）

    Returns:
        (start_date, end_date) 元组，YYYYMMDD 格式
    """
    today = date.today()
    days_back = years * 365 + quarters * 90
    start = today - timedelta(days=days_back)
    return start.strftime("%Y%m%d"), today.strftime("%Y%m%d")


class SegmentFetchError(Exception):
    """分段拉取某一段失败时抛出。"""


def _split_date_range(start_date: str, end_date: str, days_per_segment: int = 180) -> list[tuple[str, str]]:
    """将日期范围按指定天数拆分为不重叠的段。"""
    from datetime import datetime

    start = datetime.strptime(start_date, "%Y%m%d").date()
    end = datetime.strptime(end_date, "%Y%m%d").date()
    segments: list[tuple[str, str]] = []
    current_start = start
    while current_start <= end:
        current_end = min(current_start + timedelta(days=days_per_segment), end)
        segments.append((current_start.strftime("%Y%m%d"), current_end.strftime("%Y%m%d")))
        current_start = current_end + timedelta(days=1)
    return segments


def _annotate_and_dedup(
    rows: list[dict],
    source: str,
    dedup_fields: list[str],
    sort_field: str,
) -> list[dict]:
    """为数据行附加可追溯性字段，按指定字段去重并排序。"""
    fetched_at = date.today().isoformat()
    seen: set[str] = set()
    result: list[dict] = []
    for row in rows:
        key = "_".join(str(row[f]) for f in dedup_fields)
        if key not in seen:
            seen.add(key)
            raw_value = json.dumps(row, ensure_ascii=False, default=str)
            row["source"] = source
            row["fetched_at"] = fetched_at
            row["raw_value"] = raw_value
            result.append(row)
    result.sort(key=lambda r: r[sort_field], reverse=True)
    return result


def _fetch_segmented(
    api_fn,
    ts_code: str,
    start_date: str,
    end_date: str,
    source: str,
    dedup_fields: list[str],
    sort_field: str,
    days_per_segment: int = 180,
) -> list[dict]:
    """分段拉取 API 数据，合并后标注、去重、排序。任一段失败则抛出 SegmentFetchError。"""
    segments = _split_date_range(start_date, end_date, days_per_segment)
    all_rows: list[dict] = []
    for i, (seg_start, seg_end) in enumerate(segments, 1):
        df = api_fn(ts_code=ts_code, start_date=seg_start, end_date=seg_end)
        if df is None:
            msg = f"分段拉取失败：{source} 第 {i}/{len(segments)} 段（{seg_start}~{seg_end}）返回空数据"
            raise SegmentFetchError(msg)
        if not df.empty:
            all_rows.extend(df.to_dict(orient="records"))
    return _annotate_and_dedup(all_rows, source, dedup_fields, sort_field)


class TushareAdapter:
    """Tushare API 调用适配器，封装数据拉取、校验、可追溯性标注。

    使用前需设置环境变量 TUSHARE_TOKEN。
    """

    def __init__(self) -> None:
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        if not token:
            msg = (
                "TUSHARE_TOKEN 环境变量未配置。"
                "请执行 export TUSHARE_TOKEN=your_token 后重试。"
                "Token 可在 https://tushare.pro/register 获取。"
            )
            raise ValueError(msg)
        self._pro = ts.pro_api(token)

    def fetch_daily(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> DailyQuoteData:
        """拉取日线行情数据（daily 接口），按半年分段拉取。"""
        if start_date is None or end_date is None:
            default_start, default_end = calc_date_range(years=1)
            start_date = start_date or default_start
            end_date = end_date or default_end

        rows = _fetch_segmented(
            self._pro.daily,
            ts_code,
            start_date,
            end_date,
            source="tushare:daily",
            dedup_fields=["ts_code", "trade_date"],
            sort_field="trade_date",
        )
        return DailyQuoteData(data=rows)

    def fetch_daily_basic(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """拉取日频估值数据（daily_basic 接口），按半年分段拉取。"""
        if start_date is None or end_date is None:
            default_start, default_end = calc_date_range(years=1)
            start_date = start_date or default_start
            end_date = end_date or default_end

        return _fetch_segmented(
            self._pro.daily_basic,
            ts_code,
            start_date,
            end_date,
            source="tushare:daily_basic",
            dedup_fields=["ts_code", "trade_date"],
            sort_field="trade_date",
        )

    def fetch_fina_indicator(self, ts_code: str) -> list[dict]:
        """拉取季频财务质量指标（fina_indicator 接口，近 8 季度）。"""
        start_date, end_date = calc_date_range(quarters=8)
        raw_df = self._pro.fina_indicator(ts_code=ts_code, start_date=start_date, end_date=end_date)

        if raw_df is None or raw_df.empty:
            return []

        return _annotate_and_dedup(
            raw_df.to_dict(orient="records"),
            source="tushare:fina_indicator",
            dedup_fields=["ts_code", "end_date"],
            sort_field="end_date",
        )

    def fetch_income(self, ts_code: str) -> list[dict]:
        """拉取季频营收利润（income 接口，近 8 季度）。"""
        start_date, end_date = calc_date_range(quarters=8)
        raw_df = self._pro.income(ts_code=ts_code, start_date=start_date, end_date=end_date)

        if raw_df is None or raw_df.empty:
            return []

        return _annotate_and_dedup(
            raw_df.to_dict(orient="records"),
            source="tushare:income",
            dedup_fields=["ts_code", "end_date"],
            sort_field="end_date",
        )

    def fetch_moneyflow(self, ts_code: str) -> CapitalFlowData:
        """拉取日频资金流数据（moneyflow 接口，近 1 个月）。积分不足时降级。"""
        start_date = (date.today() - timedelta(days=30)).strftime("%Y%m%d")
        end_date = date.today().strftime("%Y%m%d")

        try:
            raw_df = self._pro.moneyflow(ts_code=ts_code, start_date=start_date, end_date=end_date)
        except Exception:
            return CapitalFlowData(data=None, insufficient=True)

        if raw_df is None or raw_df.empty:
            return CapitalFlowData(data=None, insufficient=True)

        rows = _annotate_and_dedup(
            raw_df.to_dict(orient="records"),
            source="tushare:moneyflow",
            dedup_fields=["ts_code", "trade_date"],
            sort_field="trade_date",
        )
        return CapitalFlowData(data=rows, insufficient=False)

    def fetch_all(self, ts_code: str) -> RawData:
        """一次性拉取全部 5 个接口数据，返回 RawData。moneyflow 失败时降级。"""
        daily = self.fetch_daily(ts_code)
        daily_basic = self.fetch_daily_basic(ts_code)
        fina_indicator = self.fetch_fina_indicator(ts_code)
        income = self.fetch_income(ts_code)
        capital = self.fetch_moneyflow(ts_code)

        return RawData(
            daily=daily,
            fundamental=FundData(
                daily_basic=daily_basic,
                fina_indicator=fina_indicator,
                income=income,
            ),
            capital=capital,
        )
