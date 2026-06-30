from group_chat_bot.config import Settings


def test_allowed_models_include_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setenv("OPENAI_ALLOWED_MODELS", "gpt-4.1,gpt-4o-mini")

    settings = Settings.from_env()

    assert settings.openai_model == "gpt-4.1-mini"
    assert settings.openai_allowed_models == ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"]
