"""Issue #38 测试：LLM request_timeout 配置"""

import os
from unittest.mock import patch

import yaml


class TestLLMTimeoutConfig:
    def test_config_has_request_timeout(self):
        """configs/llm.yaml 包含 request_timeout 字段"""
        path = __import__("pathlib").Path("configs/llm.yaml")
        with open(path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        assert "request_timeout" in config
        assert config["request_timeout"] == 300

    def test_create_llm_client_passes_timeout(self):
        """create_llm_client 将 request_timeout 传入 ChatOpenAI"""
        with (
            patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}),
            patch("langchain_openai.ChatOpenAI") as mock_chat,
        ):
                from src.strategist.schemas import create_llm_client

                create_llm_client()

        call_kwargs = mock_chat.call_args.kwargs
        assert "request_timeout" in call_kwargs
        assert call_kwargs["request_timeout"] == 300

    def test_create_llm_client_uses_config_value(self):
        """request_timeout 使用配置文件中的值而非硬编码"""
        from src.strategist.schemas import load_llm_config

        config = load_llm_config()
        assert isinstance(config["request_timeout"], (int, float))
        assert config["request_timeout"] > 0
