"""Issue #22 测试：human_review 节点函数"""


class TestHumanReviewAgent:
    def test_auto_approve_true_passes(self):
        """auto_approve=True → 返回 human_approved=True，不中断"""
        from unittest.mock import patch

        from src.strategist.node import human_review_agent

        state = {"symbol": "600519.SH", "human_approved": False}
        with patch("src.strategist.node.load_llm_config") as mock_cfg:
            mock_cfg.return_value = {"auto_approve": True}
            result = human_review_agent(state)

        assert result == {"human_approved": True}

    def test_auto_approve_false_calls_interrupt(self):
        """auto_approve=False 且 human_approved 未设置 → 调用 interrupt()"""
        from unittest.mock import patch

        from src.strategist.node import human_review_agent

        state = {"symbol": "600519.SH"}
        with (
            patch("src.strategist.node.load_llm_config") as mock_cfg,
            patch("src.strategist.node.interrupt") as mock_interrupt,
        ):
            mock_cfg.return_value = {"auto_approve": False}
            human_review_agent(state)

        mock_interrupt.assert_called_once()

    def test_auto_approve_false_rejection_returns_error(self):
        """auto_approve=False 且 human_approved=False → 返回拒绝 + error"""
        from unittest.mock import patch

        from src.strategist.node import human_review_agent

        state = {"symbol": "600519.SH", "human_approved": False}
        with patch("src.strategist.node.load_llm_config") as mock_cfg:
            mock_cfg.return_value = {"auto_approve": False}
            result = human_review_agent(state)

        assert result["human_approved"] is False
        assert "error" in result
        assert "未批准" in result["error"]["message"]

    def test_preserves_existing_approved(self):
        """state 中 human_approved 已为 True 时保持不变"""
        from unittest.mock import patch

        from src.strategist.node import human_review_agent

        state = {"symbol": "600519.SH", "human_approved": True}
        with patch("src.strategist.node.load_llm_config") as mock_cfg:
            mock_cfg.return_value = {"auto_approve": True}
            result = human_review_agent(state)

        assert result == {"human_approved": True}
