from types import SimpleNamespace

from group_chat_bot.bot import (
    GroupChatBot,
    IncomingMessage,
    normalize_config_language,
    parse_command,
    parse_message,
    parse_poll_args,
    split_keywords,
)
from group_chat_bot.plugins import DEFAULT_COMMANDS, CommandPlugin
from group_chat_bot.storage import ConversationStore
from group_chat_bot.telegram_api import TelegramClient


def test_parse_command_with_username():
    assert parse_command("/chat@my_bot hello", "my_bot") == ("chat", "hello")
    assert parse_command("/chat@other_bot hello", "my_bot") == (None, "")
    assert parse_command("/search latest AI news", "my_bot") == ("search", "latest AI news")
    assert parse_command("/news AI, crypto", "my_bot") == ("news", "AI, crypto")
    assert parse_command("/poll A? | Yes | No", "my_bot") == ("poll", "A? | Yes | No")
    assert parse_command("/leaderboard", "my_bot") == ("leaderboard", "")
    assert parse_command("/models", "my_bot") == ("models", "")
    assert parse_command("/model gpt-4.1", "my_bot") == ("model", "gpt-4.1")
    assert parse_command("/config language ko", "my_bot") == ("config", "language ko")
    assert "news" in DEFAULT_COMMANDS
    assert "config" in DEFAULT_COMMANDS
    assert parse_command("/custom run", "my_bot") == (None, "")
    assert parse_command("/custom run", "my_bot", {"custom"}) == ("custom", "run")


def test_parse_message_reply_to_bot():
    update = {
        "message": {
            "message_id": 5,
            "text": "继续解释",
            "chat": {"id": -1001, "type": "supergroup"},
            "from": {"id": 7, "username": "alice"},
            "reply_to_message": {"from": {"is_bot": True, "username": "my_bot"}},
        }
    }
    message = parse_message(update, "my_bot")
    assert message is not None
    assert message.chat_id == -1001
    assert message.reply_to_bot is True


def test_parse_channel_post():
    update = {
        "channel_post": {
            "message_id": 9,
            "text": "Bugün haber var mı?",
            "chat": {"id": -1009, "type": "channel", "title": "News Channel"},
            "sender_chat": {"id": -1009, "title": "News Channel"},
        }
    }
    message = parse_message(update, "my_bot")
    assert message is not None
    assert message.chat_type == "channel"
    assert message.user_name == "News Channel"


def test_split_keywords():
    assert split_keywords("AI, crypto Web3") == ["AI", "crypto", "Web3"]


def test_parse_poll_args():
    question, options = parse_poll_args("Best market? | Korea | Turkey | US")
    assert question == "Best market?"
    assert options == ["Korea", "Turkey", "US"]
    assert parse_poll_args("missing options") == ("", [])
    _, many_options = parse_poll_args("Q? | " + " | ".join(str(index) for index in range(20)))
    assert many_options == [str(index) for index in range(12)]


def test_send_poll_payload_uses_input_poll_options():
    class FakeTelegram(TelegramClient):
        def __init__(self):
            super().__init__("token")
            self.last_method = ""
            self.last_payload = {}

        def request(self, method, payload=None, timeout=60):
            self.last_method = method
            self.last_payload = payload or {}
            return {"message_id": 1}

    client = FakeTelegram()
    client.send_poll(-1001, "Q?", ["Yes", "No"])

    assert client.last_method == "sendPoll"
    assert client.last_payload["options"] == [{"text": "Yes"}, {"text": "No"}]


def test_model_command_persists_chat_model(tmp_path):
    class FakeTelegram:
        def __init__(self):
            self.messages = []

        def send_message(self, chat_id, text, reply_to_message_id=None, parse_mode=None):
            self.messages.append(
                {
                    "chat_id": chat_id,
                    "text": text,
                    "reply_to_message_id": reply_to_message_id,
                    "parse_mode": parse_mode,
                }
            )

    settings = SimpleNamespace(
        openai_model="gpt-4.1-mini",
        openai_allowed_models=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
        bot_username="my_bot",
    )
    telegram = FakeTelegram()
    store = ConversationStore(tmp_path / "bot.sqlite3")
    bot = GroupChatBot(settings=settings, telegram=telegram, ai=object(), store=store)
    message = IncomingMessage(
        chat_id=-1001,
        chat_type="supergroup",
        message_id=10,
        text="/model gpt-4.1",
        user_name="alice",
        reply_to_bot=False,
        user_id=7,
    )

    assert bot.model_for_chat(-1001) == "gpt-4.1-mini"
    bot.handle_model_command(message, "GPT-4.1", "en")
    assert bot.model_for_chat(-1001) == "gpt-4.1"
    assert "gpt-4.1" in telegram.messages[-1]["text"]

    bot.handle_model_command(message, "unknown-model", "en")
    assert bot.model_for_chat(-1001) == "gpt-4.1"
    assert "unknown-model" in telegram.messages[-1]["text"]

    bot.handle_model_command(message, "reset", "en")
    assert bot.model_for_chat(-1001) == "gpt-4.1-mini"


def test_custom_plugin_command_routes_from_update(tmp_path):
    class FakeTelegram:
        def __init__(self):
            self.messages = []

        def send_message(self, chat_id, text, reply_to_message_id=None, parse_mode=None):
            self.messages.append({"chat_id": chat_id, "text": text})

    def handle_custom(bot, message, command, arg, language):
        bot.telegram.send_message(message.chat_id, f"{command}:{arg}:{language}")

    settings = SimpleNamespace(
        bot_username="my_bot",
        allowed_chat_ids=set(),
        store_passive_messages=False,
        autonomous_reply=False,
        trigger_mode="mention_or_reply",
        default_language="en",
        chat_language_mode="fixed",
        chat_language_overrides={},
        max_context_messages=12,
    )
    plugin = CommandPlugin(name="custom", commands=("custom",), handler=handle_custom)
    bot = GroupChatBot(
        settings=settings,
        telegram=FakeTelegram(),
        ai=object(),
        store=ConversationStore(tmp_path / "bot.sqlite3"),
        plugins=[plugin],
    )

    bot.handle_update(
        {
            "message": {
                "message_id": 1,
                "text": "/custom hello",
                "chat": {"id": -1001, "type": "supergroup"},
                "from": {"id": 7, "username": "alice"},
            }
        }
    )

    assert bot.telegram.messages == [{"chat_id": -1001, "text": "custom:hello:en"}]


def test_config_command_updates_chat_settings(tmp_path):
    class FakeTelegram:
        def __init__(self):
            self.messages = []

        def send_message(self, chat_id, text, reply_to_message_id=None, parse_mode=None):
            self.messages.append({"chat_id": chat_id, "text": text})

    settings = SimpleNamespace(
        openai_model="gpt-4.1-mini",
        openai_allowed_models=["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
        bot_username="my_bot",
        default_language="auto",
        chat_language_mode="auto",
        chat_language_overrides={},
        max_context_messages=12,
        trigger_mode="mention_or_reply",
        autonomous_reply=False,
        news_enabled=False,
    )
    telegram = FakeTelegram()
    bot = GroupChatBot(
        settings=settings,
        telegram=telegram,
        ai=object(),
        store=ConversationStore(tmp_path / "bot.sqlite3"),
    )
    message = IncomingMessage(
        chat_id=-1001,
        chat_type="supergroup",
        message_id=11,
        text="/config",
        user_name="alice",
        reply_to_bot=False,
        user_id=7,
    )

    bot.handle_config_command(message, "config", "", "en")
    assert "Current settings" in telegram.messages[-1]["text"]

    bot.handle_config_command(message, "config", "language ko", "en")
    assert bot.language_for_chat(-1001) == "ko"
    assert bot.configured_language_label(-1001) == "ko"

    bot.handle_config_command(message, "config", "language invalid", "en")
    assert bot.language_for_chat(-1001) == "ko"
    assert "Unsupported language" in telegram.messages[-1]["text"]

    bot.handle_config_command(message, "config", "model gpt-4o-mini", "en")
    assert bot.model_for_chat(-1001) == "gpt-4o-mini"

    bot.handle_config_command(message, "config", "language reset", "en")
    assert bot.configured_language_label(-1001) == "auto"


def test_normalize_config_language_rejects_unknown():
    assert normalize_config_language("ko") == "ko"
    assert normalize_config_language("turkish") == "tr"
    assert normalize_config_language("auto") == "auto"
    assert normalize_config_language("not-a-language") is None


def test_admin_only_command_blocks_regular_member(tmp_path):
    class FakeTelegram:
        def __init__(self):
            self.messages = []

        def send_message(self, chat_id, text, reply_to_message_id=None, parse_mode=None):
            self.messages.append({"chat_id": chat_id, "text": text})

        def get_chat_member(self, chat_id, user_id):
            return {"status": "member"}

    settings = SimpleNamespace(
        bot_username="my_bot",
        allowed_chat_ids=set(),
        store_passive_messages=False,
        autonomous_reply=False,
        trigger_mode="mention_or_reply",
        default_language="en",
        chat_language_mode="fixed",
        chat_language_overrides={},
        max_context_messages=12,
        admin_only_commands={"config"},
        admin_user_ids=set(),
    )
    bot = GroupChatBot(
        settings=settings,
        telegram=FakeTelegram(),
        ai=object(),
        store=ConversationStore(tmp_path / "bot.sqlite3"),
    )

    bot.handle_update(
        {
            "message": {
                "message_id": 1,
                "text": "/config",
                "chat": {"id": -1001, "type": "supergroup"},
                "from": {"id": 7, "username": "alice"},
            }
        }
    )

    assert bot.telegram.messages[-1]["text"] == "Only chat administrators can use this command."


def test_admin_only_command_allows_admin_user_id(tmp_path):
    class FakeTelegram:
        def __init__(self):
            self.messages = []

        def send_message(self, chat_id, text, reply_to_message_id=None, parse_mode=None):
            self.messages.append({"chat_id": chat_id, "text": text})

    settings = SimpleNamespace(
        openai_model="gpt-4.1-mini",
        openai_allowed_models=["gpt-4.1-mini"],
        bot_username="my_bot",
        allowed_chat_ids=set(),
        store_passive_messages=False,
        autonomous_reply=False,
        trigger_mode="mention_or_reply",
        default_language="en",
        chat_language_mode="fixed",
        chat_language_overrides={},
        max_context_messages=12,
        admin_only_commands={"config"},
        admin_user_ids={7},
        news_enabled=False,
        ai_chat_hourly_limit=60,
        ai_chat_daily_limit=300,
        ai_global_hourly_limit=0,
        ai_global_daily_limit=0,
    )
    bot = GroupChatBot(
        settings=settings,
        telegram=FakeTelegram(),
        ai=object(),
        store=ConversationStore(tmp_path / "bot.sqlite3"),
    )

    bot.handle_update(
        {
            "message": {
                "message_id": 1,
                "text": "/config",
                "chat": {"id": -1001, "type": "supergroup"},
                "from": {"id": 7, "username": "alice"},
            }
        }
    )

    assert "Current settings" in bot.telegram.messages[-1]["text"]


def test_ai_chat_quota_blocks_after_limit(tmp_path):
    class FakeTelegram:
        def __init__(self):
            self.messages = []

        def send_message(self, chat_id, text, reply_to_message_id=None, parse_mode=None):
            self.messages.append({"chat_id": chat_id, "text": text})

        def send_chat_action(self, chat_id, action="typing"):
            return None

    class FakeAI:
        def reply(self, prompt, context, use_web_search=False, language="en", model=None):
            return f"reply:{prompt}:{model}"

    settings = SimpleNamespace(
        openai_model="gpt-4.1-mini",
        openai_allowed_models=["gpt-4.1-mini"],
        bot_username="my_bot",
        allowed_chat_ids=set(),
        store_passive_messages=False,
        autonomous_reply=False,
        trigger_mode="mention_or_reply",
        default_language="en",
        chat_language_mode="fixed",
        chat_language_overrides={},
        max_context_messages=12,
        admin_only_commands=set(),
        admin_user_ids=set(),
        mock_ai=False,
        ai_chat_hourly_limit=1,
        ai_chat_daily_limit=0,
        ai_global_hourly_limit=0,
        ai_global_daily_limit=0,
    )
    bot = GroupChatBot(
        settings=settings,
        telegram=FakeTelegram(),
        ai=FakeAI(),
        store=ConversationStore(tmp_path / "bot.sqlite3"),
    )

    for message_id, text in [(1, "/chat first"), (2, "/chat second")]:
        bot.handle_update(
            {
                "message": {
                    "message_id": message_id,
                    "text": text,
                    "chat": {"id": -1001, "type": "supergroup"},
                    "from": {"id": 7, "username": "alice"},
                }
            }
        )

    assert bot.telegram.messages[0]["text"] == "reply:first:gpt-4.1-mini"
    assert "AI request quota is exhausted" in bot.telegram.messages[-1]["text"]
