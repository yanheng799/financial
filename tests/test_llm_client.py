"""Issue #24 测试：LangChain LLM client 封装"""

import os
from unittest.mock import patch


class TestLLMClientCreation:
    """create_llm_client 工厂函数"""

    def test_creates_client_with_config_values(self):
        from src.strategist.schemas import create_llm_client, load_llm_config

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            config = load_llm_config()
            client = create_llm_client()

        assert client.model_name == config["model"]
        assert client.temperature == config["temperature"]
        assert client.max_retries == 2

    def test_missing_api_key_raises(self):
        """api_key 缺失时抛 ValueError"""
        from src.strategist.schemas import create_llm_client

        try:
            with patch.dict(os.environ, {}, clear=True):
                create_llm_client()
            raise AssertionError("Should have raised")
        except ValueError as e:
            assert "DEEPSEEK_API_KEY" in str(e)


class TestStructuredOutput:
    """with_structured_output 使用"""

    def test_structured_output_with_decision_report(self):
        from src.strategist.schemas import DecisionReport, create_llm_client

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            client = create_llm_client()

        structured = client.with_structured_output(DecisionReport, method="json_mode")
        assert structured is not None


class TestLLMClientRetry:
    """重试和错误处理"""

    def test_max_retries_set(self):
        from src.strategist.schemas import create_llm_client

        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            client = create_llm_client()

        assert client.max_retries == 2
