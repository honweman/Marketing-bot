from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class TelegramAPIError(RuntimeError):
    pass


@dataclass
class TelegramClient:
    token: str
    base_url: str = "https://api.telegram.org"

    def request(self, method: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
        url = f"{self.base_url}/bot{self.token}/{method}"
        data = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
        except Exception as exc:
            raise TelegramAPIError(f"Telegram request failed: {method}: {exc}") from exc

        parsed = json.loads(body)
        if not parsed.get("ok"):
            raise TelegramAPIError(f"Telegram API error in {method}: {parsed}")
        return parsed["result"]

    def get_me(self) -> dict[str, Any]:
        return self.request("getMe")

    def get_updates(self, offset: int | None, timeout_seconds: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout_seconds,
            "allowed_updates": ["message", "channel_post"],
        }
        if offset is not None:
            payload["offset"] = offset
        return self.request("getUpdates", payload=payload, timeout=timeout_seconds + 10)

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:4096],
            "disable_web_page_preview": True,
        }
        if reply_to_message_id is not None:
            payload["reply_parameters"] = {"message_id": reply_to_message_id, "allow_sending_without_reply": True}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self.request("sendMessage", payload=payload)

    def send_chat_action(self, chat_id: int, action: str = "typing") -> None:
        try:
            self.request("sendChatAction", payload={"chat_id": chat_id, "action": action}, timeout=10)
        except TelegramAPIError:
            # Chat action is best-effort only.
            return

    def send_poll(
        self,
        chat_id: int,
        question: str,
        options: list[str],
        is_anonymous: bool = True,
        allows_multiple_answers: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "question": question[:300],
            "options": [{"text": option[:100]} for option in options[:12]],
            "is_anonymous": is_anonymous,
            "allows_multiple_answers": allows_multiple_answers,
        }
        return self.request("sendPoll", payload=payload)


def retry_sleep(attempt: int) -> None:
    time.sleep(min(30, 2**min(attempt, 5)))
