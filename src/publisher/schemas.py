"""报告推送 Agent — AnalysisReport 模型 + raw_data_paths 反推"""

from pathlib import Path

from pydantic import BaseModel

from src.strategist.schemas import ScoreEntry

# 上游原始数据类型 → 文件名映射
_DATA_FILES = ["daily", "daily_basic", "fina_indicator", "income", "moneyflow"]


class AnalysisReport(BaseModel):
    """策略决策 Agent 最终输出的汇总报告。14 字段：元信息 + 三维评分 + 指标 + LLM 研判 + 数据引用。"""

    symbol: str
    date: str
    generated_at: str
    scores: dict[str, ScoreEntry]
    indicators: dict[str, float | None]
    overall_judgment: str
    confidence_level: str
    conflict_detected: bool
    conflict_detail: str
    key_driver: str
    risk_warning: str
    bearish_factor: str
    data_sources: list[str]
    raw_data_paths: dict[str, str | None]


def _build_raw_data_paths(symbol: str, data_root: str = "data") -> dict[str, str | None]:
    """通过已知目录结构反推原始数据路径。文件不存在时值为 None。"""
    base = Path(data_root) / symbol
    return {
        name: str(base / f"{name}.parquet") if (base / f"{name}.parquet").is_file() else None
        for name in _DATA_FILES
    }
