"""LangGraph State 定义——所有 Agent 共享的 State 结构"""

from typing import NotRequired, TypedDict


class AnalysisState(TypedDict):
    """四 Agent 流水线的共享 State"""

    symbol: str
    raw_data: dict
    technical_report: dict
    decision_report: dict
    human_approved: bool
    report_path: NotRequired[str]
    error: NotRequired[dict]
