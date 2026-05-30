"""Tushare API 调用封装——Token 初始化 + daily 接口数据拉取"""

import json
import os
from datetime import date, timedelta

import tushare as ts

from src.collector.schemas import DailyQuoteData


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
        """拉取日线行情数据（daily 接口）。

        Args:
            ts_code: 股票代码，如 '600519.SH'
            start_date: 起始日期 YYYYMMDD，默认近 1 年
            end_date: 结束日期 YYYYMMDD，默认今天

        Returns:
            DailyQuoteData——经 Pydantic 校验、去重、降序排列的日线数据
        """
        if start_date is None or end_date is None:
            default_start, default_end = calc_date_range(years=1)
            start_date = start_date or default_start
            end_date = end_date or default_end

        raw_df = self._pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)

        if raw_df is None or raw_df.empty:
            return DailyQuoteData(data=[])

        fetched_at = date.today().isoformat()
        source = "tushare:daily"

        rows = raw_df.to_dict(orient="records")

        # 按 ts_code + trade_date 去重（保留首次出现的行）
        seen: set[str] = set()
        deduped: list[dict] = []
        for row in rows:
            key = f"{row['ts_code']}_{row['trade_date']}"
            if key not in seen:
                seen.add(key)
                raw_value = json.dumps(row, ensure_ascii=False, default=str)
                row["source"] = source
                row["fetched_at"] = fetched_at
                row["raw_value"] = raw_value
                deduped.append(row)

        # 按 trade_date 降序排列（最新在前）
        deduped.sort(key=lambda r: r["trade_date"], reverse=True)

        return DailyQuoteData(data=deduped)
