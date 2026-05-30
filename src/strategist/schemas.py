"""策略决策 Agent 输出模型——ScoreEntry、DecisionReport、LLM 配置加载"""

import os
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
