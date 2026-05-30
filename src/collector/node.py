"""数据采集 Agent 的 LangGraph 节点函数与 StateGraph 构建"""

import logging
import time
from pathlib import Path

from langgraph.graph.state import StateGraph

from src.collector.adapter import TushareAdapter
from src.collector.schemas import normalize_symbol
from src.collector.storage import is_cached, load, save_all
from src.state import AnalysisState

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRY_DELAY = 3  # seconds
_RETRYABLE_ERRORS = (TimeoutError, ConnectionError)


def _get_data_dir() -> Path:
    """返回数据存储根目录。"""
    return Path("data")


def _make_error(error_type: str, message: str, detail: str = "") -> dict:
    """构造结构化错误字典。"""
    return {"error_type": error_type, "message": message, "detail": detail}


def data_collector_agent(state: AnalysisState) -> dict:
    """LangGraph 节点函数：读取 symbol → 调 fetch_all → 写 raw_data。

    Args:
        state: LangGraph 共享 State，需含 "symbol" 键

    Returns:
        更新后的 state 字典，含 raw_data 或 error
    """
    symbol = state.get("symbol", "").strip()
    if not symbol:
        return {"error": _make_error("input", "股票代码不能为空")}

    # 代码补全
    try:
        ts_code = normalize_symbol(symbol)
    except ValueError as e:
        return {"error": _make_error("input", str(e))}

    # Token 预检
    data_dir = _get_data_dir()
    try:
        adapter = TushareAdapter()
    except ValueError as e:
        return {"error": _make_error("config", str(e))}

    # 缓存优先
    if is_cached(ts_code, data_dir):
        raw_data = load(ts_code, data_dir)
        return {"raw_data": raw_data.model_dump()}

    # 带重试的 API 调用
    last_error = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            raw_data = adapter.fetch_all(ts_code)

            # 空数据检测：日线为空且所有财务子维度也为空 → 未找到该股票
            if not raw_data.daily.data and not any(
                [raw_data.fundamental.daily_basic, raw_data.fundamental.fina_indicator, raw_data.fundamental.income]
            ):
                return {"error": _make_error("not_found", f"未找到该股票: {ts_code}")}

            save_all(raw_data, data_dir)
            return {"raw_data": raw_data.model_dump()}
        except PermissionError as e:
            return {"error": _make_error("permission", str(e))}
        except _RETRYABLE_ERRORS as e:
            last_error = e
            if attempt < _MAX_RETRIES:
                logger.warning("API 超时/网络错误，第 %d 次重试（共 %d 次）", attempt + 1, _MAX_RETRIES)
                time.sleep(_RETRY_DELAY)
        except Exception as e:
            return {"error": _make_error("api", f"数据采集失败: {e}")}

    return {"error": _make_error("network", f"API 请求超时，重试 {_MAX_RETRIES} 次后仍失败", detail=str(last_error))}


def build_graph() -> StateGraph:
    """构建包含 data_collector 节点的 StateGraph。

    Returns:
        编译后的 StateGraph，可直接 invoke
    """
    graph = StateGraph(AnalysisState)
    graph.add_node("data_collector", data_collector_agent)
    graph.set_entry_point("data_collector")
    graph.set_finish_point("data_collector")
    return graph.compile()
