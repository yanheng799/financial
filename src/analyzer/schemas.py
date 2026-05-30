"""行情分析 Agent 输出模型——DimensionScore、TechnicalReport、配置加载"""

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class DimensionScore(BaseModel):
    """单维度评分结构"""

    value: int
    reason: str
    data_sufficient: bool

    @field_validator("value")
    @classmethod
    def value_in_range(cls, v: int) -> int:
        if v < -2 or v > 2:
            msg = f"value must be in [-2, +2], got {v}"
            raise ValueError(msg)
        return v


class TechnicalReport(BaseModel):
    """行情分析 Agent 输出结构"""

    symbol: str
    date: str
    scores: dict[str, DimensionScore]
    indicators: dict
    generated_at: str


_CONFIG_CACHE: dict | None = None


def load_scoring_config(config_path: str | Path = "configs/scoring.yaml") -> dict:
    """加载评分阈值配置文件。结果缓存，重复调用不重复读文件。"""
    global _CONFIG_CACHE  # noqa: PLW0603
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    path = Path(config_path)
    if not path.is_file():
        msg = f"Scoring config not found: {path}"
        raise FileNotFoundError(msg)

    with open(path, encoding="utf-8") as f:
        _CONFIG_CACHE = yaml.safe_load(f)
    return _CONFIG_CACHE
