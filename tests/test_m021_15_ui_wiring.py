from pathlib import Path

PAGE = Path("app/interface/desktop/pages/case_workspace_page.py")
VIEW = Path("app/interface/desktop/views/workspace/case_workspace_view.py")


def test_page_wiring():
    text = PAGE.read_text(encoding="utf-8")
    assert text.count("investigation_search_requested.connect(") == 1
    assert text.count("def _start_investigation_search(") == 1
    assert "ServiceContainer(" not in text
    assert "container=self.container" in text


def test_view_wiring():
    text = VIEW.read_text(encoding="utf-8")
    assert text.count("self._create_investigation_search_tab()") == 1
    assert text.count("def _create_investigation_search_tab(") == 1
