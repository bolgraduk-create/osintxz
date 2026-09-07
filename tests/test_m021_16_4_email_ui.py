from pathlib import Path


def test_email_result_presentation_and_status_table_exist():
    text = Path(
        "app/interface/desktop/views/workspace/investigation_search_view.py"
    ).read_text(encoding="utf-8")
    assert "M021.16.4 EMAIL result presentation" in text
    assert 'payload.get("osint")' in text
    assert "def _show_osint_result(" in text
    assert "def _fill_osint_sources(" in text
    assert '"Коннектор"' in text
    assert '"Ошибка / детали"' in text


def test_open_web_summary_labels_live_and_archive_separately():
    text = Path(
        "app/interface/desktop/views/workspace/investigation_search_view.py"
    ).read_text(encoding="utf-8")
    assert "Найдено документов:" in text
    assert "Live Web:" in text
    assert "Common Crawl:" in text
