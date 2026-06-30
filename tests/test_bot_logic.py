from group_chat_bot.bot import parse_command, parse_message, parse_poll_args, split_keywords
from group_chat_bot.telegram_api import TelegramClient


def test_parse_command_with_username():
    assert parse_command("/chat@my_bot hello", "my_bot") == ("chat", "hello")
    assert parse_command("/chat@other_bot hello", "my_bot") == (None, "")
    assert parse_command("/search latest AI news", "my_bot") == ("search", "latest AI news")
    assert parse_command("/news AI, crypto", "my_bot") == ("news", "AI, crypto")
    assert parse_command("/poll A? | Yes | No", "my_bot") == ("poll", "A? | Yes | No")
    assert parse_command("/leaderboard", "my_bot") == ("leaderboard", "")


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
