"""策略决策 Agent — human_review + build_prompt + strategy_decider"""

import json
import logging
from datetime import datetime

from langgraph.graph.state import StateGraph
from langgraph.types import interrupt

from src.state import AnalysisState
from src.strategist.schemas import (
    DecisionReport,
    LLMOutput,
    _get_data_sufficient,
    build_data_sources,
    compute_confidence,
    create_llm_client,
    detect_conflict,
    load_llm_config,
    to_score_entry,
)

logger = logging.getLogger(__name__)

# 维度名 → 数据来源映射。Phase 2 加 sentiment 时只需改此处。
DIM_SOURCES = {
    "technical": "Tushare daily",
    "fundamental": "Tushare daily_basic/fina_indicator",
    "capital": "Tushare moneyflow",
}


def human_review_agent(state: AnalysisState) -> dict:
    """Human-in-the-loop 审批节点。

    从 configs/llm.yaml 读取 auto_approve 开关：
    - auto_approve=True：直接返回 human_approved=True，不中断
    - auto_approve=False 且 state 中 human_approved 已为 False：返回拒绝 + error
    - auto_approve=False 且未审批：调用 interrupt()，等待用户在 Streamlit 批准后 resume
    """
    config = load_llm_config()
    auto_approve = config.get("auto_approve", True)

    if auto_approve:
        return {"human_approved": True}

    if state.get("human_approved") is False:
        return {
            "human_approved": False,
            "error": _make_error("human_review", "用户未批准，跳过策略分析"),
        }

    msg = "请确认 technical_report，批准后继续"
    return interrupt(msg)


def _dim_name(key: str) -> str:
    names = {"technical": "技术面评分", "fundamental": "基本面评分", "capital": "资金面评分"}
    return names.get(key, key)


def _fmt_val(val) -> str:
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.4g}"
    return str(val)


def _make_error(error_type: str, message: str, detail: str = "") -> dict:
    return {"error_type": error_type, "message": message, "detail": detail}


def build_prompt(technical_report: dict) -> str:
    """从 TechnicalReport 构造 LLM prompt。LLM 只需输出 5 个推理字段。"""
    scores = technical_report.get("scores", {})
    indicators = technical_report.get("indicators", {})
    symbol = technical_report.get("symbol", "")
    date_str = technical_report.get("date", "")

    score_lines = []
    score_values = []

    for dim_key in scores:
        dim = scores.get(dim_key)
        if dim is None:
            continue

        value = dim.value if hasattr(dim, "value") else dim.get("value", 0)
        reason = dim.reason if hasattr(dim, "reason") else dim.get("reason", "")
        sufficient = _get_data_sufficient(dim)

        conf_label = "确定性数据支撑" if sufficient else "数据不足，仅供参考"
        source = DIM_SOURCES.get(dim_key, "")

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
    indicator_lines = []
    for key, label in key_indicators:
        val = indicators.get(key)
        if val is not None:
            indicator_lines.append(f"  {label}: {_fmt_val(val)}")

    max_diff = max(score_values) - min(score_values) if len(score_values) >= 2 else 0

    prompt = f"""股票代码：{symbol}
分析日期：{date_str}

{chr(10).join(score_lines)}

关键指标：
{chr(10).join(indicator_lines)}

最大分差：{max_diff}

请基于以上评分进行交叉分析，严格按照以下 JSON 格式输出（仅输出这 5 个字段）：
{{
  "conflict_detail": "描述各维度间是否存在矛盾，例如：技术面+基本面偏多，资金面偏空",
  "overall_judgment": "乐观/中性/谨慎/中性偏谨慎/中性偏乐观",
  "key_driver": "哪个维度权重最大及原因",
  "risk_warning": "如果判断偏乐观，必须列出风险因素",
  "bearish_factor": "强制输出一条最不支持当前判断的反向理由"
}}

规则：
1. 仅基于提供的数据进行分析，不要编造未提供的信息
2. 数据不足时标注"该维度数据不足"并说明缺少哪类数据
3. 无论综合判断如何，必须输出 bearish_factor
4. 不得输出 JSON 之外的文字"""

    return prompt


def strategy_decider_agent(state: AnalysisState) -> dict:
    """策略决策节点：LLM 输出 5 个推理字段 → 代码注入 7 个确定性字段 → DecisionReport。

    重试分工：
    - SDK 层（ChatOpenAI max_retries=2）：处理网络超时/HTTP 429，最多 3 次调用
    - 应用层（attempt range(2)）：处理 JSON 解析/LLMOutput schema 校验失败，最多 2 次调用
    两类错误互不交叉。
    """
    technical_report = state.get("technical_report")
    if not technical_report:
        return {"error": _make_error("input", "technical_report 为空，请先执行行情分析 Agent")}

    scores = technical_report.get("scores", {})
    if not scores:
        return {"error": _make_error("input", "technical_report.scores 为空")}

    all_insufficient = all(
        (_get_data_sufficient(s)) is False
        for s in scores.values()
    )
    if all_insufficient:
        return {"error": _make_error("input", "所有维度均数据不足，无法进行策略分析")}

    # 代码计算的 7 个确定性值
    confidence_level = compute_confidence(scores)
    entries = {dim: to_score_entry(s) for dim, s in scores.items()}
    conflict_detected = detect_conflict(scores)
    symbol = technical_report.get("symbol", "")
    date_str = technical_report.get("date", "")
    data_sources = build_data_sources(scores, DIM_SOURCES)
    generated_at = datetime.now().isoformat()

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

        # Validate with LLMOutput (5 fields only)
        try:
            llm_output = LLMOutput.model_validate(data)
        except Exception as e:
            if attempt == 0:
                prompt += f"\n\n【重要】上一次输出不符合 schema: {e}。请严格按 JSON 模板输出。"
                continue
            return {"error": _make_error("llm_parse_error", f"LLM 输出不符合 schema: {e}", detail=raw[:200])}

        # Merge LLM output (5 fields) + code-injected values (7 fields) → DecisionReport
        report_data = {
            "symbol": symbol,
            "date": date_str,
            "scores": {
                dim: e.model_dump() if hasattr(e, "model_dump") else {"value": e.value, "reason": e.reason, "confidence": e.confidence}
                for dim, e in entries.items()
            },
            "conflict_detected": conflict_detected,
            "confidence_level": confidence_level,
            "data_sources": data_sources,
            "generated_at": generated_at,
            # LLM 推理字段
            "conflict_detail": llm_output.conflict_detail,
            "overall_judgment": llm_output.overall_judgment,
            "key_driver": llm_output.key_driver,
            "risk_warning": llm_output.risk_warning,
            "bearish_factor": llm_output.bearish_factor,
        }

        report = DecisionReport.model_validate(report_data)
        return {"decision_report": report.model_dump()}

    return {"error": _make_error("llm_parse_error", "LLM 输出校验失败，重试后仍失败")}


def route_after_review(state: AnalysisState) -> str:
    """human_review 后的条件路由：approved → strategy_decider，否则 END。"""
    if state.get("human_approved"):
        return "strategy_decider"
    return "__end__"


def build_strategist_graph() -> StateGraph:
    """构建策略决策 Agent StateGraph：human_review → strategy_decider。"""
    graph = StateGraph(AnalysisState)
    graph.add_node("human_review", human_review_agent)
    graph.add_node("strategy_decider", strategy_decider_agent)
    graph.set_entry_point("human_review")
    graph.add_conditional_edges("human_review", route_after_review)
    graph.set_finish_point("strategy_decider")
    return graph.compile()
