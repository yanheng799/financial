"""策略决策 Agent 输出模型——ScoreEntry、DecisionReport、LLM 配置加载"""

from pathlib import Path
from typing import Literal

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
