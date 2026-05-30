"""策略决策 Agent — human_review + build_prompt + strategy_decider"""

import json
import logging

from langgraph.types import interrupt

from src.state import AnalysisState
from src.strategist.schemas import (
    DecisionReport,
    compute_confidence,
    create_llm_client,
    load_llm_config,
    to_score_entry,
)

logger = logging.getLogger(__name__)


def human_review_agent(state: AnalysisState) -> dict:
    config = load_llm_config()
    if config.get("auto_approve", True):
        return {"human_approved": True}
    return interrupt("请确认 technical_report，批准后继续")


def _dim_name(key: str) -> str:
    return {"technical": "技术面评分", "fundamental": "基本面评分", "capital": "资金面评分"}.get(key, key)


def _fmt_val(val) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.4g}"
    return str(val)


def _make_error(error_type: str, message: str, detail: str = "") -> dict:
    return {"error_type": error_type, "message": message, "detail": detail}



def build_prompt(technical_report: dict) -> str:
    scores = technical_report.get("scores", {})
    indicators = technical_report.get("indicators", {})
    symbol = technical_report.get("symbol", "")
    date_str = technical_report.get("date", "")

    score_lines = []
    score_values = []
    dim_sources = {
        "technical": "Tushare daily",
        "fundamental": "Tushare daily_basic/fina_indicator",
        "capital": "Tushare moneyflow",
    }

    for dim_key in ["technical", "fundamental", "capital"]:
        dim = scores.get(dim_key)
        if dim is None:
            continue
        value = dim.value if hasattr(dim, "value") else dim.get("value", 0)
        reason = dim.reason if hasattr(dim, "reason") else dim.get("reason", "")
        sufficient = dim.data_sufficient if hasattr(dim, "data_sufficient") else dim.get("data_sufficient", True)
        conf_label = "确定性数据支撑" if sufficient else "数据不足，仅供参考"
        source = dim_sources.get(dim_key, "")
        if not sufficient:
            score_lines.append(f"{_dim_name(dim_key)}：{value}（{reason}）【{conf_label}】")
        else:
            score_lines.append(f"{_dim_name(dim_key)}：{value}（{reason}）【{conf_label}，来源：{source}】")
        score_values.append(value)

    key_indicators = [
        ("ma5", "MA5"), ("ma20", "MA20"), ("ma60", "MA60"),
        ("macd_hist", "MACD柱"), ("vol_ratio", "成交量比"),
        ("pe_ttm", "PE_TTM"), ("pe_percentile_1y", "PE分位数(%)"),
        ("roe_yearly", "年化ROE"), ("tr_yoy", "营收YoY(%)"),
        ("netprofit_yoy", "净利润YoY(%)"),
        ("net_mf_amount_5d", "近5日主力净流入"), ("lg_buy_sell_ratio", "大单买卖比"),
    ]
    indicator_lines = [
        f"  {label}: {_fmt_val(indicators.get(key))}"
        for key, label in key_indicators
        if indicators.get(key) is not None
    ]

    max_diff = max(score_values) - min(score_values) if len(score_values) >= 2 else 0

    return f"""股票代码：{symbol}
分析日期：{date_str}

{chr(10).join(score_lines)}

关键指标：
{chr(10).join(indicator_lines)}

最大分差：{max_diff}

请基于以上评分进行交叉分析，严格按照以下 JSON 格式输出：
{{
  "symbol": "{symbol}",
  "date": "{date_str}",
  "scores": {{ ... 回填传入的评分，confidence 用 "determined"/"insufficient" }},
  "conflict_detected": true/false,
  "conflict_detail": "例如：技术面+基本面偏多，资金面偏空",
  "overall_judgment": "乐观/中性/谨慎/中性偏谨慎/中性偏乐观",
  "key_driver": "哪个维度权重最大及原因",
  "risk_warning": "如果判断偏乐观，必须列出风险因素",
  "bearish_factor": "强制输出一条最不支持当前判断的反向理由",
  "data_sources": ["数据来源列表"],
  "generated_at": "ISO 8601"
}}

注意：不要输出 confidence_level，该字段由代码注入。

规则：
1. 仅基于提供的数据进行分析，不要编造未提供的信息
2. 数据不足时标注"该维度数据不足"并说明缺少哪类数据
3. 无论综合判断如何，必须输出 bearish_factor
4. 不得输出 JSON 之外的文字"""


def strategy_decider_agent(state: AnalysisState) -> dict:
    technical_report = state.get("technical_report")
    if not technical_report:
        return {"error": _make_error("input", "technical_report 为空，请先执行行情分析 Agent")}

    scores = technical_report.get("scores", {})
    if not scores:
        return {"error": _make_error("input", "technical_report.scores 为空")}

    all_insufficient = all(
        (s.data_sufficient if hasattr(s, "data_sufficient") else s.get("data_sufficient", True)) is False
        for s in scores.values()
    )
    if all_insufficient:
        return {"error": _make_error("input", "所有维度均数据不足，无法进行策略分析")}

    confidence_level = compute_confidence(scores)
    entries = {dim: to_score_entry(s) for dim, s in scores.items()}
    prompt = build_prompt(technical_report)

    try:
        client = create_llm_client()
    except ValueError as e:
        return {"error": _make_error("config", str(e))}

    for attempt in range(2):
        try:
            response = client.invoke(prompt)
            raw = response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            return {"error": _make_error("llm_call", f"LLM 调用失败: {e}")}

        # Parse JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            if attempt == 0:
                prompt += "\n\n【重要】上一次输出格式错误，请严格按 JSON 模板输出。"
                continue
            return {"error": _make_error("llm_parse_error", "LLM 返回非 JSON，重试后仍失败", detail=raw[:200])}

        # 注入代码计算的值 (must happen before Pydantic validation)
        data["confidence_level"] = confidence_level
        data["scores"] = {
            dim: e.model_dump() if hasattr(e, "model_dump") else {"value": e.value, "reason": e.reason, "confidence": e.confidence}
            for dim, e in entries.items()
        }

        # Validate
        try:
            report = DecisionReport.model_validate(data)
        except Exception as e:
            if attempt == 0:
                prompt += f"\n\n【重要】上一次输出不符合 schema: {e}。请严格按 JSON 模板输出。"
                continue
            return {"error": _make_error("llm_parse_error", f"LLM 输出不符合 schema: {e}", detail=raw[:200])}

        return {"decision_report": report.model_dump()}

    return {"error": _make_error("llm_parse_error", "LLM 输出校验失败，重试后仍失败")}
