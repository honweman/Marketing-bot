from group_chat_bot.config import Settings


def test_allowed_models_include_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_ALLOWED_MODELS", "gpt-4.1,gpt-4o-mini")
    monkeypatch.setenv("ADMIN_USER_IDS", "7,8")
    monkeypatch.setenv("ADMIN_ONLY_COMMANDS", "config,MODEL")
    monkeypatch.setenv("AI_CHAT_HOURLY_LIMIT", "10")
    monkeypatch.setenv("AI_CHAT_DAILY_LIMIT", "20")
    monkeypatch.setenv("POST_MODE", "channel")
    monkeypatch.setenv("TARGET_CHANNEL_ID", "-100111")
    monkeypatch.setenv("DISCUSSION_GROUP_ID", "-100222")
    monkeypatch.setenv("COPILOT_ADMIN_CHAT_ID", "777")

    settings = Settings.from_env()

    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.openai_allowed_models == ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"]
    assert settings.admin_user_ids == {7, 8}
    assert settings.admin_only_commands == {"config", "model"}
    assert settings.ai_chat_hourly_limit == 10
    assert settings.ai_chat_daily_limit == 20
    assert settings.post_mode == "channel"
    assert settings.target_channel_id == -100111
    assert settings.discussion_group_id == -100222
    assert settings.copilot_admin_chat_id == 777
