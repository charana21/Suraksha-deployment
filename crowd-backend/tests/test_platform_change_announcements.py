from train_announcement import _build_platform_change_messages_i18n

def test_build_platform_change_messages_i18n_contains_change_message():
    messages = _build_platform_change_messages_i18n(
        train_number="12345",
        source="Secunderabad",
        destination="Mumbai",
        station_name="Secunderabad",
        platform="2",
    )

    assert "changed" in messages["english"].lower()
    assert "platform" in messages["english"].lower()
    assert "two" in messages["english"].lower()
    assert messages["hin"]
    assert messages["tel"]
