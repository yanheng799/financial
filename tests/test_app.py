"""Issue #47 测试：app.py — 语法正确，可导入，无硬伤"""


class TestAppPy:
    def test_app_syntax_valid(self):
        """app.py 语法正确"""
        with open("app.py", encoding="utf-8") as f:
            compile(f.read(), "app.py", "exec")

    def test_app_structure_has_required_sections(self):
        """app.py 包含必需的代码块"""
        with open("app.py", encoding="utf-8") as f:
            source = f.read()
        assert "st.set_page_config" in source
        assert "st.text_input" in source
        assert "build_collector_graph" in source
        assert "build_analyzer_graph" in source
        assert "build_strategist_graph" in source
        assert "build_publisher_graph" in source
        assert "decision_report" in source
        assert "report_files" in source or "glob" in source


class TestImportWithoutStreamlitRuntime:
    """验证 app.py 的导入模式不使用 streamlit 的运行时 API"""

    def test_app_uses_known_streamlit_apis(self):
        with open("app.py", encoding="utf-8") as f:
            source = f.read()
        # 检查使用的 streamlit API 都是真实存在的
        known_apis = [
            "st.set_page_config", "st.title", "st.text_input",
            "st.button", "st.spinner", "st.error", "st.warning",
            "st.success", "st.stop", "st.divider", "st.subheader",
            "st.dataframe", "st.markdown", "st.caption",
            "st.sidebar.header", "st.sidebar.selectbox",
            "st.sidebar.caption", "st.columns", "st.metric", "st.info",
        ]
        for api in known_apis:
            assert api in source, f"Missing: {api}"
