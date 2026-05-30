"""报告推送 Agent — report_publisher_agent 节点函数"""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.publisher.schemas import AnalysisReport, _build_raw_data_paths
from src.state import AnalysisState

logger = logging.getLogger(__name__)

DATA_DIR = "data"


def report_publisher_agent(state: AnalysisState) -> dict:
    """从 technical_report + decision_report 组装 AnalysisReport → Parquet 归档。

    Returns:
        {"report_path": "..."} 或 {"error": {"error_type": "storage", ...}}
    """
    technical_report = state.get("technical_report", {})
    decision_report = state.get("decision_report", {})
    symbol = state.get("symbol", "")

    # 组装 AnalysisReport
    report = AnalysisReport(
        symbol=symbol,
        date=technical_report.get("date", ""),
        generated_at=datetime.now().isoformat(),
        scores=decision_report.get("scores", {}),
        indicators=technical_report.get("indicators", {}),
        overall_judgment=decision_report.get("overall_judgment", ""),
        confidence_level=decision_report.get("confidence_level", ""),
        conflict_detected=decision_report.get("conflict_detected", False),
        conflict_detail=decision_report.get("conflict_detail", ""),
        key_driver=decision_report.get("key_driver", ""),
        risk_warning=decision_report.get("risk_warning", ""),
        bearish_factor=decision_report.get("bearish_factor", ""),
        data_sources=decision_report.get("data_sources", []),
        raw_data_paths=_build_raw_data_paths(symbol, DATA_DIR),
    )

    # Parquet 落盘（空 scores 时跳过——pyarrow 无法序列化空 struct）
    scores = report.scores
    if not scores:
        return {"report_path": ""}

    report_dir = Path(DATA_DIR) / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    report_path = report_dir / f"{symbol}_{timestamp}.parquet"

    try:
        pd.DataFrame([report.model_dump()]).to_parquet(report_path, index=False)
    except OSError as e:
        return {"error": {"error_type": "storage", "message": f"报告存档失败: {e}"}}

    logger.info("Report saved: %s", report_path)
    return {"report_path": str(report_path)}


def build_publisher_graph():
    """构建报告推送 Agent 最简 StateGraph。单节点，无条件边。"""
    from langgraph.graph.state import StateGraph

    graph = StateGraph(AnalysisState)
    graph.add_node("report_publisher", report_publisher_agent)
    graph.set_entry_point("report_publisher")
    graph.set_finish_point("report_publisher")
    return graph.compile()
