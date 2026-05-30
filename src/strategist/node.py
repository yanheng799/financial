"""策略决策 Agent LangGraph 节点函数"""

from langgraph.types import interrupt

from src.state import AnalysisState
from src.strategist.schemas import load_llm_config


def human_review_agent(state: AnalysisState) -> dict:
    """Human-in-the-loop 审批节点。

    从 configs/llm.yaml 读取 auto_approve 开关：
    - auto_approve=True：直接返回 human_approved=True，不中断
    - auto_approve=False：调用 interrupt()，等待用户在 Streamlit 批准后 resume
    """
    config = load_llm_config()
    auto_approve = config.get("auto_approve", True)

    if auto_approve:
        return {"human_approved": True}

    msg = "请确认 technical_report，批准后继续"
    return interrupt(msg)
