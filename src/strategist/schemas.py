"""策略决策 Agent 输出模型——ScoreEntry、DecisionReport、LLM 配置加载、置信度计算"""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel


class ScoreEntry(BaseModel):
    """单维度评分条目（用于 LLM prompt 和 DecisionReport）"""

    value: int
    reason: str
    confidence: Literal["determined", "insufficient", "deferred"]


class DecisionReport(BaseModel):
    """策略决策 Agent 输出结构"""

    symbol: str
    date: str
    scores: dict[str, ScoreEntry]
    conflict_detected: bool
    conflict_detail: str
    overall_judgment: Literal["乐观", "中性", "谨慎", "中性偏谨慎", "中性偏乐观"]
    confidence_level: Literal["高", "中", "低"]  # 代码注入，非 LLM 输出
    key_driver: str
    risk_warning: str
    bearish_factor: str
    data_sources: list[str]
    generated_at: str


_LLM_CONFIG_CACHE: dict | None = None


def load_llm_config(config_path: str | Path = "configs/llm.yaml") -> dict:
    """加载 LLM 配置文件。结果缓存，重复调用不重复读文件。"""
    global _LLM_CONFIG_CACHE  # noqa: PLW0603
    if _LLM_CONFIG_CACHE is not None:
        return _LLM_CONFIG_CACHE

    path = Path(config_path)
    if not path.is_file():
        msg = f"LLM config not found: {path}"
        raise FileNotFoundError(msg)

    with open(path, encoding="utf-8") as f:
        _LLM_CONFIG_CACHE = yaml.safe_load(f)
    return _LLM_CONFIG_CACHE


def compute_confidence(scores: dict[str, Any]) -> Literal["高", "中", "低"]:
    """根据维度一致性计算置信度（代码实现，非 LLM）。

    Args:
        scores: 维度名到 DimensionScore 的映射。
                data_sufficient=False 的维度不参与计算。

    Returns:
        "高" | "中" | "低"

    Raises:
        ValueError: 当所有维度均数据不足时
    """
    valid = {k: v for k, v in scores.items() if _get_data_sufficient(v)}

    if len(valid) == 0:
        msg = "所有维度均数据不足，无法计算置信度"
        raise ValueError(msg)

    if len(valid) == 1:
        return "低"

    values = [v.value for v in valid.values()]
    signs = [_sign(v) for v in values]

    # 任意两维得分差 >= 2 → 低
    if max(values) - min(values) >= 2:
        return "低"

    # 方向一致性
    if len(valid) == 3:
        if len(set(signs)) == 1:
            return "高"
        if len(set(signs)) == 2:
            return "中"
        return "低"

    # len(valid) == 2
    if signs[0] == signs[1]:
        return "高"
    return "低"


def to_score_entry(dim_score: Any) -> ScoreEntry:
    """将行情分析 Agent 的 DimensionScore 转换为策略决策 Agent 的 ScoreEntry。

    data_sufficient=True → confidence="determined"
    data_sufficient=False → confidence="insufficient"
    """
    confidence = "determined" if _get_data_sufficient(dim_score) else "insufficient"
    return ScoreEntry(value=dim_score.value, reason=dim_score.reason, confidence=confidence)


def _sign(v: int) -> int:
    """符号函数：正→1 负→-1 零→0"""
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


def _get_data_sufficient(obj: Any) -> bool:
    """安全获取 data_sufficient 属性，默认 True"""
    return getattr(obj, "data_sufficient", True)
