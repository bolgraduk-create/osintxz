from app.osint.capabilities import DiscoveryGoal, capabilities_for_goal


def test_user_scanner_is_default_account_discovery():
    capabilities = capabilities_for_goal(
        DiscoveryGoal.ACCOUNT_DISCOVERY,
        default_only=True,
    )

    assert any(
        item.connector_class == "UserScannerConnector"
        for item in capabilities
    )
