"""行情分析 Agent LangGraph 节点函数"""

from datetime import date

from langgraph.graph.state import StateGraph

from src.analyzer.indicators import (
    compute_capital_indicators,
    compute_fundamental_indicators,
    compute_technical_indicators,
)
from src.analyzer.schemas import TechnicalReport
from src.analyzer.scoring import score_capital, score_fundamental, score_technical
from src.state import AnalysisState


def market_analyzer_agent(state: AnalysisState) -> dict:
    """LangGraph 节点函数：读取 raw_data → 算指标 → 三维评分 → 写 technical_report。

    Args:
        state: LangGraph 共享 State，需含 "symbol" 和 "raw_data"

    Returns:
        更新后的 state 字典，含 technical_report 或 error
    """
    raw_data = state.get("raw_data")
    symbol = state.get("symbol", "")

    if not raw_data:
        return {"error": _make_error("input", "raw_data 为空，请先执行数据采集 Agent")}

    # 调用三个维度的指标计算
    daily_data = raw_data.get("daily", {}).get("data") or []
    daily_count = len(daily_data)
    tech_indicators = compute_technical_indicators(daily_data)

    fundamental_data = raw_data.get("fundamental", {})
    fund_indicators = compute_fundamental_indicators(fundamental_data)
    has_fundamental = bool(fundamental_data.get("fina_indicator"))

    capital_data = raw_data.get("capital", {})
    cap_indicators = compute_capital_indicators(capital_data)
    cap_insufficient = capital_data.get("insufficient", False)
    has_capital = bool(capital_data.get("data"))

    # 三维评分
    tech_score = score_technical(tech_indicators, daily_count)
    fund_score = score_fundamental(fund_indicators, has_fundamental)
    cap_score = score_capital(cap_indicators, cap_insufficient, has_capital)

    # 合并所有指标
    indicators = {}
    indicators.update(tech_indicators)
    indicators.update(fund_indicators)
    indicators.update(cap_indicators)

    report = TechnicalReport(
        symbol=symbol,
        date=date.today().strftime("%Y%m%d"),
        scores={
            "technical": tech_score,
            "fundamental": fund_score,
            "capital": cap_score,
        },
        indicators=indicators,
        generated_at=date.today().isoformat(),
    )

    return {"technical_report": report.model_dump()}


def build_analyzer_graph() -> StateGraph:
    """构建包含 market_analyzer 节点的 StateGraph。"""
    graph = StateGraph(AnalysisState)
    graph.add_node("market_analyzer", market_analyzer_agent)
    graph.set_entry_point("market_analyzer")
    graph.set_finish_point("market_analyzer")
    return graph.compile()


def _make_error(error_type: str, message: str, detail: str = "") -> dict:
    return {"error_type": error_type, "message": message, "detail": detail}
