"""策略决策 Agent LangGraph 节点函数"""

from langgraph.types import interrupt

from src.state import AnalysisState
from src.strategist.schemas import load_llm_config


def human_review_agent(state: AnalysisState) -> dict:
    """Human-in-the-loop 审批节点。"""
    config = load_llm_config()
    auto_approve = config.get("auto_approve", True)

    if auto_approve:
        return {"human_approved": True}

    msg = "请确认 technical_report，批准后继续"
    return interrupt(msg)


def build_prompt(technical_report: dict) -> str:
    """从 TechnicalReport 构造 LLM prompt。

    Args:
        technical_report: TechnicalReport.model_dump() 输出

    Returns:
        完整的 LLM prompt 字符串
    """
    scores = technical_report.get("scores", {})
    indicators = technical_report.get("indicators", {})
    symbol = technical_report.get("symbol", "")
    date_str = technical_report.get("date", "")

    # 1. 评分摘要
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
        sufficient = _extract_data_sufficient(dim)

        conf_label = "确定性数据支撑" if sufficient else "数据不足，仅供参考"
        source = dim_sources.get(dim_key, "")

        if not sufficient:
            score_lines.append(f"{_dim_name(dim_key)}：{value}（{reason}）【{conf_label}】")
        else:
            score_lines.append(f"{_dim_name(dim_key)}：{value}（{reason}）【{conf_label}，来源：{source}】")

        score_values.append(value)

    # 2. 关键指标摘要
    key_indicators = [
        ("ma5", "MA5"), ("ma20", "MA20"), ("ma60", "MA60"),
        ("macd_hist", "MACD柱"), ("vol_ratio", "成交量比"),
        ("pe_ttm", "PE_TTM"), ("pe_percentile_1y", "PE分位数(%)"),
        ("roe_yearly", "年化ROE"), ("tr_yoy", "营收YoY(%)"),
        ("netprofit_yoy", "净利润YoY(%)"),
        ("net_mf_amount_5d", "近5日主力净流入"), ("lg_buy_sell_ratio", "大单买卖比"),
    ]
    indicator_lines = []
    for key, label in key_indicators:
        val = indicators.get(key)
        if val is not None:
            indicator_lines.append(f"  {label}: {_fmt_val(val)}")

    # 3. 最大分差
    max_diff = max(score_values) - min(score_values) if len(score_values) >= 2 else 0

    # 4. 组装
    prompt = f"""股票代码：{symbol}
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

    return prompt


def _dim_name(key: str) -> str:
    names = {"technical": "技术面评分", "fundamental": "基本面评分", "capital": "资金面评分"}
    return names.get(key, key)


def _fmt_val(val) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.4g}"
    return str(val)


def _extract_data_sufficient(dim) -> bool:
    if hasattr(dim, "data_sufficient"):
        return dim.data_sufficient
    return dim.get("data_sufficient", True)
