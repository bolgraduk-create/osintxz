from __future__ import annotations

from app.interface.desktop.bridges.desktop_bridge import DesktopBridge


def test_dashboard_summary_keeps_attributes_out_of_graph_nodes():
    summary = DesktopBridge._dashboard_person_summary(
        {
            "relatedEntities": [
                {"rawType": "username", "type": "Username", "value": "janex"},
                {"rawType": "account", "type": "Account", "value": "tg:123"},
                {"rawType": "phone", "type": "Phone", "value": "+380000000000"},
                {"rawType": "email", "type": "Email", "value": "jane@example.test"},
                {"rawType": "organization", "type": "Organization", "value": "Example LLC"},
            ],
            "links": [{"value": "https://example.test/jane", "url": "https://example.test/jane"}],
            "metadataRows": [{"label": "Telegram ID", "value": "123"}],
        }
    )
    pairs = {(row["label"], row["value"]) for row in summary}
    assert ("Phone", "+380000000000") in pairs
    assert ("Email", "jane@example.test") in pairs
    assert ("Organization", "Example LLC") in pairs
    assert ("Profile page", "https://example.test/jane") in pairs
    assert ("Telegram ID", "123") in pairs
    assert all(value not in {"janex", "tg:123"} for _, value in pairs)
