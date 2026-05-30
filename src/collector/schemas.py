"""数据采集 Agent 的 Pydantic 数据模型与股票代码解析器"""

import re

from pydantic import BaseModel


# ── Pydantic 数据模型 ────────────────────────────────────


class DailyQuoteData(BaseModel):
    """日线行情数据（daily 接口），每行含 source/fetched_at/raw_value"""

    data: list[dict]


class FundData(BaseModel):
    """估值与财务指标：daily_basic（日频）+ fina_indicator（季频）+ income（季频）"""

    daily_basic: list[dict]
    fina_indicator: list[dict]
    income: list[dict]


class CapitalFlowData(BaseModel):
    """资金流数据（moneyflow 接口），积分不足时 data 为 None"""

    data: list[dict] | None
    insufficient: bool = False


class RawData(BaseModel):
    """数据采集 Agent 的完整输出——按三维拆分"""

    daily: DailyQuoteData
    fundamental: FundData
    capital: CapitalFlowData


# ── 股票代码解析器 ───────────────────────────────────────

# 交易所后缀规则
_SUFFIX_RULES = {
    "6": ".SH",  # 上海证券交易所（沪市主板、科创板）
    "0": ".SZ",  # 深圳证券交易所（深市主板）
    "3": ".SZ",  # 深圳证券交易所（创业板）
    "9": ".BJ",  # 北京证券交易所
}

_VALID_SUFFIXES = {".SH", ".SZ", ".BJ"}
_SUFFIXED_PATTERN = re.compile(r"^(\d{4,6})\.(SH|SZ|BJ)$")
_BARE_PATTERN = re.compile(r"^\d{4,6}$")


def normalize_symbol(code: str) -> str:
    """将股票代码标准化为带交易所后缀的格式。

    Args:
        code: 裸代码（如 '600519'）或完整代码（如 '600519.SH'）

    Returns:
        标准化后的完整代码（如 '600519.SH'）

    Raises:
        ValueError: 无法识别的代码格式
    """
    code = code.strip()

    # 已带后缀——直接返回
    match = _SUFFIXED_PATTERN.match(code)
    if match:
        return code

    # 裸代码——按首位数字补全
    match = _BARE_PATTERN.match(code)
    if match:
        first_char = code[0]
        suffix = _SUFFIX_RULES.get(first_char)
        if suffix is None:
            raise ValueError(f"无法识别的股票代码: {code}（首位 '{first_char}' 不匹配已知交易所规则）")
        return f"{code}{suffix}"

    raise ValueError(f"无法识别的股票代码格式: '{code}'")
