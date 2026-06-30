from __future__ import annotations

import logging
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Collection

from .ai import AIResponder
from .config import Settings
from .language import detect_language, detect_language_from_messages, localize
from .news import NewsItem, fetch_random_news, format_news, format_news_card
from .plugins import DEFAULT_COMMANDS, CommandPlugin, build_default_plugins, command_index
from .storage import ConversationStore
from .telegram_api import TelegramAPIError, TelegramClient, retry_sleep


logger = logging.getLogger(__name__)


@dataclass
class IncomingMessage:
    chat_id: int
    chat_type: str
    message_id: int
    text: str
    user_name: str
    reply_to_bot: bool
    user_id: int | None = None

    @property
    def is_group(self) -> bool:
        return self.chat_type in {"group", "supergroup"}

    @property
    def is_shared_chat(self) -> bool:
        return self.chat_type in {"group", "supergroup", "channel"}


class GroupChatBot:
    def __init__(
        self,
        settings: Settings,
        telegram: TelegramClient,
        ai: AIResponder,
        store: ConversationStore,
        plugins: list[CommandPlugin] | None = None,
    ):
        self.settings = settings
        self.telegram = telegram
        self.ai = ai
        self.store = store
        self.plugins = plugins if plugins is not None else build_default_plugins()
        self.command_handlers = command_index(self.plugins)
        self.bot_username = settings.bot_username
        self.last_autonomous_reply_at: dict[int, float] = {}
        self.autonomous_reply_times: dict[int, deque[float]] = defaultdict(deque)

    def initialize(self) -> None:
        me = self.telegram.get_me()
        self.bot_username = self.bot_username or me.get("username")
        if not self.bot_username:
            raise RuntimeError("Could not resolve bot username")
        logger.info("Bot started as @%s", self.bot_username)
        self.start_news_scheduler()
        self.start_leaderboard_scheduler()

    def run_forever(self) -> None:
        self.initialize()
        offset: int | None = None
        attempt = 0

        while True:
            try:
                updates = self.telegram.get_updates(offset=offset, timeout_seconds=self.settings.poll_timeout_seconds)
                attempt = 0
                for update in updates:
                    offset = update["update_id"] + 1
                    self.handle_update(update)
            except KeyboardInterrupt:
                logger.info("Stopping")
                raise
            except Exception:
                logger.exception("Polling failed")
                retry_sleep(attempt)
                attempt += 1

    def handle_update(self, update: dict[str, Any]) -> None:
        message = parse_message(update, self.bot_username or "")
        if message is None:
            return

        if self.settings.allowed_chat_ids and message.chat_id not in self.settings.allowed_chat_ids:
            logger.warning("Ignoring chat_id=%s because it is not in ALLOWED_CHAT_IDS", message.chat_id)
            return
        if message.is_group:
            self.store.record_activity(message.chat_id, message.user_id, message.user_name)

        command, command_arg = parse_command(message.text, self.bot_username or "", self.command_handlers.keys())
        if command:
            self.handle_command(message, command, command_arg)
            return

        prompt = self.extract_prompt(message)
        if prompt:
            self.answer(message, prompt)
            return

        if self.settings.store_passive_messages:
            self.store.add_message(message.chat_id, "user", message.text, user_name=message.user_name)

        if self.should_autonomously_reply(message):
            self.answer(message, message.text, store_user=False)

    def handle_command(self, message: IncomingMessage, command: str, arg: str) -> None:
        language = self.language_for_chat(message.chat_id, latest_text=arg)
        plugin = self.command_handlers.get(command)
        if plugin is None:
            return
        plugin.handle(self, message, command, arg, language)

    def handle_core_command(self, message: IncomingMessage, command: str, arg: str, language: str) -> None:
        if command in {"start", "help"}:
            self.telegram.send_message(message.chat_id, localize("help", language), reply_to_message_id=message.message_id)
            return
        if command == "id":
            self.telegram.send_message(message.chat_id, f"chat_id: `{message.chat_id}`", reply_to_message_id=message.message_id, parse_mode="Markdown")
            return
        if command == "reset":
            self.store.clear_chat(message.chat_id)
            self.telegram.send_message(message.chat_id, localize("reset_done", language), reply_to_message_id=message.message_id)
            return
        if command == "privacy":
            self.telegram.send_message(message.chat_id, localize("privacy", language), reply_to_message_id=message.message_id)
            return

    def handle_chat_command(self, message: IncomingMessage, command: str, arg: str, language: str) -> None:
        if not arg:
            self.telegram.send_message(message.chat_id, localize("ask_after_command", language), reply_to_message_id=message.message_id)
            return
        self.answer(message, arg)

    def handle_search_command(self, message: IncomingMessage, command: str, arg: str, language: str) -> None:
        if not arg:
            self.telegram.send_message(message.chat_id, localize("search_after_command", language), reply_to_message_id=message.message_id)
            return
        self.answer(message, arg, use_web_search=True)

    def handle_news_command(self, message: IncomingMessage, command: str, arg: str, language: str) -> None:
        self.send_news(message.chat_id, reply_to_message_id=message.message_id, keywords=split_keywords(arg))

    def handle_poll_command(self, message: IncomingMessage, command: str, arg: str, language: str) -> None:
        self.send_manual_poll(message, arg, language)

    def handle_leaderboard_command(self, message: IncomingMessage, command: str, arg: str, language: str) -> None:
        self.send_leaderboard(message.chat_id, reply_to_message_id=message.message_id)

    def handle_model_plugin_command(self, message: IncomingMessage, command: str, arg: str, language: str) -> None:
        if command == "models":
            self.send_model_list(message.chat_id, language, reply_to_message_id=message.message_id)
            return
        self.handle_model_command(message, arg, language)

    def extract_prompt(self, message: IncomingMessage) -> str | None:
        text = message.text.strip()
        if self.settings.trigger_mode == "always":
            return text
        if self.settings.trigger_mode == "command_only":
            return None

        if message.reply_to_bot:
            return text

        mention_pattern = re.compile(rf"@{re.escape(self.bot_username or '')}\b", re.IGNORECASE)
        if mention_pattern.search(text):
            return mention_pattern.sub("", text).strip(" \n\t:：,，")

        if not message.is_shared_chat:
            return text

        return None

    def should_autonomously_reply(self, message: IncomingMessage) -> bool:
        if not self.settings.autonomous_reply:
            return False
        if not message.is_shared_chat:
            return False
        if not self.can_autonomously_reply(message.chat_id):
            return False
        context = self.store.recent_messages(message.chat_id, self.settings.max_context_messages)
        language = self.language_for_chat(message.chat_id, latest_text=message.text, context=context)
        model = self.model_for_chat(message.chat_id)
        try:
            should_reply = self.ai.should_autonomously_reply(message.text, context, language=language, model=model)
        except Exception:
            logger.exception("Autonomous reply decision failed")
            return False
        if should_reply:
            now = time.time()
            self.last_autonomous_reply_at[message.chat_id] = now
            self.autonomous_reply_times[message.chat_id].append(now)
        return should_reply

    def can_autonomously_reply(self, chat_id: int) -> bool:
        now = time.time()
        last = self.last_autonomous_reply_at.get(chat_id, 0)
        if now - last < self.settings.autonomous_reply_min_seconds:
            return False
        window = self.autonomous_reply_times[chat_id]
        while window and now - window[0] > 3600:
            window.popleft()
        return len(window) < self.settings.autonomous_reply_max_per_hour

    def answer(self, message: IncomingMessage, prompt: str, use_web_search: bool = False, store_user: bool = True) -> None:
        language = self.language_for_chat(message.chat_id, latest_text=prompt)
        if not prompt.strip():
            self.telegram.send_message(message.chat_id, localize("empty_prompt", language), reply_to_message_id=message.message_id)
            return

        self.telegram.send_chat_action(message.chat_id)
        context = self.store.recent_messages(message.chat_id, self.settings.max_context_messages)
        language = self.language_for_chat(message.chat_id, latest_text=prompt, context=context)
        model = self.model_for_chat(message.chat_id)
        try:
            reply = self.ai.reply(prompt, context, use_web_search=use_web_search, language=language, model=model)
        except Exception:
            logger.exception("AI response failed")
            self.telegram.send_message(message.chat_id, localize("ai_failed", language), reply_to_message_id=message.message_id)
            return

        if store_user:
            self.store.add_message(message.chat_id, "user", prompt, user_name=message.user_name)
        self.store.add_message(message.chat_id, "assistant", reply)
        self.telegram.send_message(message.chat_id, reply, reply_to_message_id=message.message_id)

    def send_news(self, chat_id: int, reply_to_message_id: int | None = None, keywords: list[str] | None = None) -> None:
        keywords = keywords if keywords is not None else self.settings.news_keywords
        items = fetch_random_news(self.settings.news_rss_feeds, keywords, self.settings.news_count)
        language = self.language_for_chat(chat_id)
        if not items:
            self.telegram.send_message(chat_id, format_news(items, language=language), reply_to_message_id=reply_to_message_id)
            return

        if self.settings.news_card_mode == "links":
            self.telegram.send_message(chat_id, format_news(items, language=language), reply_to_message_id=reply_to_message_id)
        else:
            model = self.model_for_chat(chat_id)
            for index, item in enumerate(items):
                card = self.build_news_card(item, language, model)
                self.telegram.send_message(
                    chat_id,
                    card,
                    reply_to_message_id=reply_to_message_id if index == 0 else None,
                )

        if self.settings.news_with_poll:
            self.send_default_poll(chat_id, language)

        discussion_chat_id = self.settings.news_discussion_map.get(chat_id)
        if discussion_chat_id is not None:
            first = items[0]
            prompt = f"{localize('discussion_prompt', language)}\n\n{first.title}\n{first.link}"
            self.telegram.send_message(discussion_chat_id, prompt)

    def build_news_card(self, item: NewsItem, language: str, model: str) -> str:
        if not self.settings.news_ai_summary:
            return format_news_card(item, language=language)
        try:
            return self.ai.news_card(item, language=language, model=model)
        except Exception:
            logger.exception("AI news card failed")
            return format_news_card(item, language=language)

    def send_default_poll(self, chat_id: int, language: str) -> None:
        question = localize("poll_question", language)
        options = localize("poll_options", language).split("|")
        self.telegram.send_poll(chat_id, question=question, options=options)

    def send_manual_poll(self, message: IncomingMessage, arg: str, language: str) -> None:
        question, options = parse_poll_args(arg)
        if not question or len(options) < 2:
            self.telegram.send_message(message.chat_id, localize("poll_usage", language), reply_to_message_id=message.message_id)
            return
        self.telegram.send_poll(message.chat_id, question=question, options=options)

    def send_leaderboard(self, chat_id: int, reply_to_message_id: int | None = None) -> None:
        language = self.language_for_chat(chat_id)
        rows = self.store.leaderboard(chat_id, days=self.settings.leaderboard_days, limit=10)
        if not rows:
            self.telegram.send_message(chat_id, localize("leaderboard_empty", language), reply_to_message_id=reply_to_message_id)
            return
        header = localize("leaderboard_header", language).format(days=self.settings.leaderboard_days)
        lines = [header]
        for index, row in enumerate(rows, start=1):
            lines.append(f"{index}. {row['user_name']} · {row['score']}")
        self.telegram.send_message(chat_id, "\n".join(lines), reply_to_message_id=reply_to_message_id)

    def send_model_list(self, chat_id: int, language: str, reply_to_message_id: int | None = None) -> None:
        current = self.model_for_chat(chat_id)
        models = "\n".join(f"- {model}" for model in self.settings.openai_allowed_models)
        text = localize("model_list", language).format(models=models, current=current)
        self.telegram.send_message(chat_id, text, reply_to_message_id=reply_to_message_id)

    def handle_model_command(self, message: IncomingMessage, arg: str, language: str) -> None:
        requested = arg.strip()
        if not requested:
            current = self.model_for_chat(message.chat_id)
            text = localize("model_current", language).format(model=current)
            self.telegram.send_message(message.chat_id, text, reply_to_message_id=message.message_id)
            return

        if requested.lower() == "reset":
            self.store.delete_chat_setting(message.chat_id, "model")
            model = self.settings.openai_model
            text = localize("model_reset", language).format(model=model)
            self.telegram.send_message(message.chat_id, text, reply_to_message_id=message.message_id)
            return

        model = self.normalize_model(requested)
        if model is None:
            models = ", ".join(self.settings.openai_allowed_models)
            text = localize("model_not_allowed", language).format(model=requested, models=models)
            self.telegram.send_message(message.chat_id, text, reply_to_message_id=message.message_id)
            return

        self.store.set_chat_setting(message.chat_id, "model", model)
        text = localize("model_set", language).format(model=model)
        self.telegram.send_message(message.chat_id, text, reply_to_message_id=message.message_id)

    def model_for_chat(self, chat_id: int) -> str:
        stored = self.store.get_chat_setting(chat_id, "model")
        if stored and stored in self.settings.openai_allowed_models:
            return stored
        return self.settings.openai_model

    def normalize_model(self, value: str) -> str | None:
        lowered = value.strip().lower()
        for model in self.settings.openai_allowed_models:
            if model.lower() == lowered:
                return model
        return None

    def language_for_chat(
        self,
        chat_id: int,
        latest_text: str = "",
        context: list[dict[str, str]] | None = None,
    ) -> str:
        override = self.settings.chat_language_overrides.get(chat_id)
        if override and override != "auto":
            return override

        default = self.settings.default_language
        if self.settings.chat_language_mode == "fixed" and default != "auto":
            return default

        fallback = default if default != "auto" else "zh"
        if latest_text:
            return detect_language(latest_text, default=fallback)

        if context is None:
            context = self.store.recent_messages(chat_id, self.settings.max_context_messages)
        return detect_language_from_messages(context, default=fallback)

    def start_news_scheduler(self) -> None:
        if not self.settings.news_enabled:
            return
        target_chat_ids = self.settings.news_chat_ids or self.settings.allowed_chat_ids
        if not target_chat_ids:
            logger.warning("NEWS_ENABLED=1 but NEWS_CHAT_IDS and ALLOWED_CHAT_IDS are empty; scheduler disabled")
            return

        thread = threading.Thread(target=self.news_loop, args=(sorted(target_chat_ids),), daemon=True)
        thread.start()
        logger.info("News scheduler enabled for %s", sorted(target_chat_ids))

    def news_loop(self, chat_ids: list[int]) -> None:
        interval = max(5, self.settings.news_interval_minutes) * 60
        while True:
            time.sleep(interval)
            for chat_id in chat_ids:
                try:
                    self.send_news(chat_id)
                except Exception:
                    logger.exception("Scheduled news failed for chat_id=%s", chat_id)

    def start_leaderboard_scheduler(self) -> None:
        if not self.settings.leaderboard_enabled:
            return
        target_chat_ids = self.settings.leaderboard_chat_ids or self.settings.allowed_chat_ids
        if not target_chat_ids:
            logger.warning("LEADERBOARD_ENABLED=1 but LEADERBOARD_CHAT_IDS and ALLOWED_CHAT_IDS are empty; scheduler disabled")
            return
        thread = threading.Thread(target=self.leaderboard_loop, args=(sorted(target_chat_ids),), daemon=True)
        thread.start()
        logger.info("Leaderboard scheduler enabled for %s", sorted(target_chat_ids))

    def leaderboard_loop(self, chat_ids: list[int]) -> None:
        interval = max(1, self.settings.leaderboard_interval_hours) * 3600
        while True:
            time.sleep(interval)
            for chat_id in chat_ids:
                try:
                    self.send_leaderboard(chat_id)
                except Exception:
                    logger.exception("Scheduled leaderboard failed for chat_id=%s", chat_id)


def parse_message(update: dict[str, Any], bot_username: str) -> IncomingMessage | None:
    raw = update.get("message") or update.get("channel_post")
    if not raw:
        return None

    text = raw.get("text") or raw.get("caption")
    if not text:
        return None

    chat = raw.get("chat") or {}
    sender = raw.get("from") or raw.get("sender_chat") or {}
    reply = raw.get("reply_to_message") or {}
    reply_from = reply.get("from") or {}
    reply_to_bot = bool(reply_from.get("is_bot") and reply_from.get("username", "").lower() == bot_username.lower())

    user_name = sender.get("username") or sender.get("title") or " ".join(
        part for part in [sender.get("first_name"), sender.get("last_name")] if part
    ) or str(sender.get("id", "unknown"))

    return IncomingMessage(
        chat_id=int(chat["id"]),
        chat_type=chat.get("type", "private"),
        message_id=int(raw["message_id"]),
        text=text,
        user_name=user_name,
        reply_to_bot=reply_to_bot,
        user_id=sender.get("id"),
    )


def parse_command(
    text: str,
    bot_username: str,
    known_commands: Collection[str] | None = DEFAULT_COMMANDS,
) -> tuple[str | None, str]:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None, ""

    first, _, rest = stripped.partition(" ")
    command = first[1:]
    if "@" in command:
        name, username = command.split("@", 1)
        if username.lower() != bot_username.lower():
            return None, ""
        command = name

    command = command.lower()
    if known_commands is not None and command not in known_commands:
        return None, ""
    return command, rest.strip()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = Settings.from_env()
    telegram = TelegramClient(settings.telegram_bot_token)
    ai = AIResponder(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        system_prompt=settings.system_prompt,
        mock=settings.mock_ai,
        web_search_enabled=settings.openai_web_search,
        web_search_tool=settings.openai_web_search_tool,
    )
    store = ConversationStore(settings.database_path)
    GroupChatBot(settings, telegram, ai, store).run_forever()


def split_keywords(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，\s]+", value) if item.strip()]


def parse_poll_args(value: str) -> tuple[str, list[str]]:
    parts = [part.strip() for part in value.split("|") if part.strip()]
    if len(parts) < 3:
        return "", []
    question = parts[0]
    options = parts[1:13]
    return question, options
