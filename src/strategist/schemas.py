"""策略决策 Agent — ScoreEntry, DecisionReport, LLMOutput, LLM 配置加载, 置信度计算"""

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict


class ScoreEntry(BaseModel):
    """单维度评分条目（用于 LLM prompt 和 DecisionReport）"""

    value: int
    reason: str
    confidence: Literal["determined", "insufficient", "deferred"]


class LLMOutput(BaseModel):
    """LLM 只需输出的 5 个推理字段。其余 7 个字段由代码注入。"""

    model_config = ConfigDict(extra="ignore")

    conflict_detail: str
    overall_judgment: Literal["乐观", "中性", "谨慎", "中性偏谨慎", "中性偏乐观"]
    key_driver: str
    risk_warning: str
    bearish_factor: str


class DecisionReport(BaseModel):
    """策略决策 Agent 输出结构（12 字段：5 LLM + 7 代码注入）"""

    model_config = ConfigDict(extra="ignore")

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


def create_llm_client():
    """从 configs/llm.yaml 创建 LangChain ChatOpenAI 实例。

    支持 DeepSeek/Qwen 的 OpenAI 兼容端点。api_key 从环境变量读取。
    Raises ValueError if api_key env var is not set.
    """
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


def detect_conflict(scores: dict[str, Any]) -> bool:
    """判断维度间是否存在冲突（既有正分又有负分）。零值不算方向。

    data_sufficient=False 的维度不参与判断。
    """
    valid = {k: v for k, v in scores.items() if _get_data_sufficient(v)}
    values = [_get_value(v) for v in valid.values()]
    has_positive = any(v > 0 for v in values)
    has_negative = any(v < 0 for v in values)
    return has_positive and has_negative


def build_data_sources(scores: dict[str, Any], dim_sources: dict[str, str]) -> list[str]:
    """构建数据来源列表，只包含 data_sufficient=True 的维度。"""
    return [
        dim_sources[dim]
        for dim, score in scores.items()
        if _get_data_sufficient(score) and dim in dim_sources
    ]


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

    values = [_get_value(v) for v in valid.values()]
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
    return ScoreEntry(value=_get_value(dim_score), reason=_get_reason(dim_score), confidence=confidence)


def _sign(v: int) -> int:
    """符号函数：正→1 负→-1 零→0"""
    if v > 0:
        return 1
    if v < 0:
        return -1
    return 0


def _get_data_sufficient(obj: Any) -> bool:
    """安全获取 data_sufficient，兼容对象和 dict，默认 True"""
    if hasattr(obj, "data_sufficient"):
        return obj.data_sufficient
    if isinstance(obj, dict):
        return obj.get("data_sufficient", True)
    return True


def _get_value(obj: Any) -> int:
    """安全获取 value，兼容对象和 dict"""
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, dict):
        return obj.get("value", 0)
    return 0


def _get_reason(obj: Any) -> str:
    """安全获取 reason，兼容对象和 dict"""
    if hasattr(obj, "reason"):
        return obj.reason
    if isinstance(obj, dict):
        return obj.get("reason", "")
    return ""
