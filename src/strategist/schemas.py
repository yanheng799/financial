"""策略决策 Agent — ScoreEntry, DecisionReport, 配置, 置信度, LLM client"""

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel


class ScoreEntry(BaseModel):
    """单维度评分条目"""
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
    """加载 LLM 配置文件。结果缓存。"""
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


def create_llm_client():
    """从 configs/llm.yaml 创建 LangChain ChatOpenAI 实例。"""
    from langchain_openai import ChatOpenAI

    config = load_llm_config()
    key_env = config["api_key_env"]
    api_key = os.environ.get(key_env, "")
    if not api_key:
        msg = f"LLM API key not set. Please set the {key_env} environment variable."
        raise ValueError(msg)
    return ChatOpenAI(
        model=config["model"],
        base_url=config["base_url"],
        api_key=api_key,
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
        max_retries=2,
    )


def compute_confidence(scores: dict[str, Any]) -> Literal["高", "中", "低"]:
    """根据维度一致性计算置信度（代码实现，非 LLM）。"""
    valid = {k: v for k, v in scores.items() if _get_data_sufficient(v)}
    if len(valid) == 0:
        msg = "所有维度均数据不足，无法计算置信度"
        raise ValueError(msg)
    if len(valid) == 1:
        return "低"

    values = [v.value for v in valid.values()]
    if max(values) - min(values) >= 2:
        return "低"

    signs = [_sign(v) for v in values]
    if len(valid) == 3:
        if len(set(signs)) == 1:
            return "高"
        if len(set(signs)) == 2:
            return "中"
        return "低"
    # 2 维
    if signs[0] == signs[1]:
        return "高"
    return "低"


def to_score_entry(dim_score: Any) -> ScoreEntry:
    """DimensionScore → ScoreEntry。"""
    confidence = "determined" if _get_data_sufficient(dim_score) else "insufficient"
    return ScoreEntry(value=dim_score.value, reason=dim_score.reason, confidence=confidence)


def _sign(v: int) -> int:
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


def _get_data_sufficient(obj: Any) -> bool:
    return getattr(obj, "data_sufficient", True)
