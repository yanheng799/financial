"""Issue #37 测试：代码清理 — 合并 _extract_data_sufficient, 验证动态维度"""


class TestCodeCleanup:
    def test_node_no_duplicate_extract_data_sufficient(self):
        """node.py 中不应存在 _extract_data_sufficient 函数"""
        import src.strategist.node as node_mod

        assert not hasattr(node_mod, "_extract_data_sufficient"), (
            "_extract_data_sufficient 应已删除，改为使用 schemas._get_data_sufficient"
        )

    def test_schemas_has_get_data_sufficient(self):
        """schemas._get_data_sufficient 存在且可导入"""
        from src.strategist.schemas import _get_data_sufficient

        assert callable(_get_data_sufficient)

    def test_node_build_prompt_uses_dynamic_dims(self):
        """build_prompt 使用 scores.keys() 而非硬编码维度列表"""
        import inspect
        import textwrap

        from src.strategist.node import build_prompt

        source = textwrap.dedent(inspect.getsource(build_prompt))
        # 不应出现硬编码的维度列表
        assert '["technical", "fundamental", "capital"]' not in source

    def test_dim_sources_externalized(self):
        """DIM_SOURCES 是模块级常量"""
        from src.strategist.node import DIM_SOURCES

        assert isinstance(DIM_SOURCES, dict)
        assert "technical" in DIM_SOURCES
        assert "fundamental" in DIM_SOURCES
        assert "capital" in DIM_SOURCES

    def test_strategy_decider_has_retry_docs(self):
        """strategy_decider_agent 的 docstring 包含重试分工说明"""
        from src.strategist.node import strategy_decider_agent

        doc = strategy_decider_agent.__doc__ or ""
        assert "SDK" in doc or "max_retries" in doc
        assert "应用层" in doc or "attempt" in doc
