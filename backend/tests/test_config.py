from app.config import Settings


def test_shipped_default_is_detected_as_placeholder():
    assert Settings(database_url="sqlite://").user_agent_is_placeholder is True


def test_placeholder_markers_are_detected():
    for agent in (
        "CyberNews/0.1 (+https://example.invalid/contact)",
        "SignalWatch/0.1 (+http://localhost:3000)",
        "SignalWatch/0.1 (+https://github.com/signalwatch)",
    ):
        settings = Settings(database_url="sqlite://", user_agent=agent)
        assert settings.user_agent_is_placeholder is True


def test_real_contact_url_is_not_a_placeholder():
    settings = Settings(
        database_url="sqlite://",
        user_agent="CyberNews/0.1 (+https://github.com/raiantorbey/cyber-news)",
    )
    assert settings.user_agent_is_placeholder is False
