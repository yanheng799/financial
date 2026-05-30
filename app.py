"""A 股分析 Agent 系统 — Streamlit 仪表盘"""

import glob
from pathlib import Path

import pandas as pd
import streamlit as st

from src.analyzer.node import build_analyzer_graph
from src.collector.node import build_graph as build_collector_graph
from src.publisher.node import build_publisher_graph
from src.strategist.node import build_strategist_graph

st.set_page_config(page_title="A 股分析 Agent", page_icon="📈", layout="wide")
st.title("📈 A 股分析 Agent")

# ── Input ──────────────────────────────────────────────

col1, col2 = st.columns([3, 1])
with col1:
    symbol_input = st.text_input("股票代码", placeholder="例如 600519", max_chars=6)
with col2:
    analyze_btn = st.button("🔍 开始分析", use_container_width=True, type="primary")

# ── Analysis flow ───────────────────────────────────────

if analyze_btn and symbol_input:
    symbol = symbol_input.strip()
    state: dict = {"symbol": symbol}

    with st.spinner(f"正在分析 {symbol}，请稍候..."):
        try:
            # Step 1: Data collector
            collector_graph = build_collector_graph()
            state = collector_graph.invoke(state)

            if "error" in state:
                st.error(f"数据采集失败: {state['error'].get('message', '未知错误')}")
                st.stop()

            # Step 2: Market analyzer
            analyzer_graph = build_analyzer_graph()
            state = analyzer_graph.invoke(state)

            if "error" in state:
                st.error(f"行情分析失败: {state['error'].get('message', '未知错误')}")
                st.stop()

            # Step 3: Strategy decider
            strategist_graph = build_strategist_graph()
            state = strategist_graph.invoke(state)

            # Check if human_review was rejected
            if state.get("human_approved") is False:
                err = state.get("error", {})
                st.warning(err.get("message", "用户未批准，跳过策略分析"))
                st.stop()

            if "error" in state:
                st.error(f"策略决策失败: {state['error'].get('message', '未知错误')}")
            else:
                # Step 4: Report publisher (only if decision_report exists)
                if state.get("decision_report"):
                    publisher_graph = build_publisher_graph()
                    state = publisher_graph.invoke(state)

                    if "error" in state:
                        st.error(f"报告存档失败: {state['error'].get('message', '未知错误')}")
                    else:
                        st.success("分析完成！")

        except Exception as e:
            st.error(f"流水线执行异常: {e}")
            st.stop()

# ── Display results ──────────────────────────────────────

decision_report = state.get("decision_report") if "state" in dir() else None
if decision_report:
    st.divider()

    # 三维评分表
    st.subheader("📊 三维评分")
    scores = decision_report.get("scores", {})
    if scores:
        score_data = []
        for dim, entry in scores.items():
            dim_labels = {"technical": "技术面", "fundamental": "基本面", "capital": "资金面"}
            score_data.append({
                "维度": dim_labels.get(dim, dim),
                "评分": entry.get("value", 0),
                "原因": entry.get("reason", ""),
                "置信度": entry.get("confidence", "N/A"),
            })
        st.dataframe(pd.DataFrame(score_data), use_container_width=True, hide_index=True)

    # 冲突 + 综合判断
    col_a, col_b = st.columns(2)
    with col_a:
        conflict = decision_report.get("conflict_detected", False)
        conflict_detail = decision_report.get("conflict_detail", "")
        if conflict:
            st.warning(f"⚠️ 维度冲突: {conflict_detail}")
        else:
            st.info("✅ 维度方向一致")
    with col_b:
        judgment = decision_report.get("overall_judgment", "N/A")
        confidence = decision_report.get("confidence_level", "N/A")
        st.metric("综合判断", judgment)

    # 关键指标
    technical_report = state.get("technical_report", {})
    indicators = technical_report.get("indicators", {})
    if indicators:
        st.subheader("📋 关键指标")
        indicator_data = [
            {"指标": "MA5", "值": indicators.get("ma5", "N/A")},
            {"指标": "MA20", "值": indicators.get("ma20", "N/A")},
            {"指标": "MA60", "值": indicators.get("ma60", "N/A")},
            {"指标": "MACD柱", "值": indicators.get("macd_hist", "N/A")},
            {"指标": "成交量比", "值": indicators.get("vol_ratio", "N/A")},
            {"指标": "PE_TTM", "值": indicators.get("pe_ttm", "N/A")},
            {"指标": "PE分位数(%)", "值": indicators.get("pe_percentile_1y", "N/A")},
            {"指标": "年化ROE", "值": indicators.get("roe_yearly", "N/A")},
            {"指标": "营收YoY(%)", "值": indicators.get("tr_yoy", "N/A")},
            {"指标": "净利润YoY(%)", "值": indicators.get("netprofit_yoy", "N/A")},
            {"指标": "近5日主力净流入", "值": indicators.get("net_mf_amount_5d", "N/A")},
            {"指标": "大单买卖比", "值": indicators.get("lg_buy_sell_ratio", "N/A")},
        ]
        st.dataframe(pd.DataFrame(indicator_data), use_container_width=True, hide_index=True)

    # LLM 研判
    st.subheader("🧠 LLM 综合研判")
    st.markdown(f"**关键驱动**: {decision_report.get('key_driver', 'N/A')}")
    st.markdown(f"**风险提示**: {decision_report.get('risk_warning', 'N/A')}")
    st.markdown(f"**反向因素**: {decision_report.get('bearish_factor', 'N/A')}")
    st.caption(f"数据来源: {', '.join(decision_report.get('data_sources', []))}")

# ── History ──────────────────────────────────────────────

st.sidebar.header("📂 历史分析")
if symbol_input:
    pattern = f"data/reports/{symbol_input.strip()}_*.parquet"
    report_files = sorted(glob.glob(pattern), reverse=True)
    if report_files:
        selected = st.sidebar.selectbox(
            "选择历史记录",
            report_files,
            format_func=lambda f: Path(f).stem,
        )
        if selected:
            try:
                df = pd.read_parquet(selected)
                st.sidebar.caption(f"分析时间: {df.iloc[0].get('generated_at', 'N/A')}")
            except Exception:
                st.sidebar.caption("无法读取该记录")
    else:
        st.sidebar.caption("暂无历史记录")
