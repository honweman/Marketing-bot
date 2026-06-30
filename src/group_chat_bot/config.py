from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .language import normalize_language


def load_dotenv(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_int_set(value: str) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        result.add(int(item))
    return result


def parse_int_map(value: str) -> dict[int, int]:
    result: dict[int, int] = {}
    for part in value.split(","):
        item = part.strip()
        if not item or ":" not in item:
            continue
        key, mapped = item.split(":", 1)
        result[int(key.strip())] = int(mapped.strip())
    return result


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str | None
    openai_model: str
    openai_allowed_models: list[str]
    bot_username: str | None
    allowed_chat_ids: set[int]
    trigger_mode: str
    database_path: Path
    system_prompt: str
    max_context_messages: int
    post_mode: str
    target_channel_id: int | None
    discussion_group_id: int | None
    copilot_admin_chat_id: int | None
    poll_timeout_seconds: int
    mock_ai: bool
    store_passive_messages: bool
    autonomous_reply: bool
    autonomous_reply_min_seconds: int
    autonomous_reply_max_per_hour: int
    openai_web_search: bool
    openai_web_search_tool: str
    ai_chat_hourly_limit: int
    ai_chat_daily_limit: int
    ai_global_hourly_limit: int
    ai_global_daily_limit: int
    admin_user_ids: set[int]
    admin_only_commands: set[str]
    news_enabled: bool
    news_chat_ids: set[int]
    news_interval_minutes: int
    news_count: int
    news_keywords: list[str]
    news_rss_feeds: list[str]
    news_card_mode: str
    news_ai_summary: bool
    news_with_poll: bool
    news_discussion_map: dict[int, int]
    leaderboard_enabled: bool
    leaderboard_chat_ids: set[int]
    leaderboard_interval_hours: int
    leaderboard_days: int
    default_language: str
    chat_language_mode: str
    chat_language_overrides: dict[int, str]

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

        trigger_mode = os.getenv("TRIGGER_MODE", "mention_or_reply").strip()
        valid_modes = {"mention_or_reply", "always", "command_only"}
        if trigger_mode not in valid_modes:
            raise RuntimeError(f"TRIGGER_MODE must be one of {sorted(valid_modes)}")
        chat_language_mode = os.getenv("CHAT_LANGUAGE_MODE", "auto").strip().lower()
        if chat_language_mode not in {"auto", "fixed"}:
            raise RuntimeError("CHAT_LANGUAGE_MODE must be auto or fixed")
        news_card_mode = os.getenv("NEWS_CARD_MODE", "card").strip().lower()
        if news_card_mode not in {"links", "card"}:
            raise RuntimeError("NEWS_CARD_MODE must be links or card")
        post_mode = os.getenv("POST_MODE", "bot").strip().lower()
        if post_mode not in {"bot", "channel", "copilot"}:
            raise RuntimeError("POST_MODE must be one of bot, channel, copilot")
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
        openai_allowed_models = parse_csv(os.getenv("OPENAI_ALLOWED_MODELS", ""))
        if not openai_allowed_models:
            openai_allowed_models = [openai_model]
        elif openai_model not in openai_allowed_models:
            openai_allowed_models.insert(0, openai_model)

        return cls(
            telegram_bot_token=token,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=openai_model,
            openai_allowed_models=openai_allowed_models,
            bot_username=(os.getenv("BOT_USERNAME") or "").strip().lstrip("@") or None,
            allowed_chat_ids=parse_int_set(os.getenv("ALLOWED_CHAT_IDS", "")),
            trigger_mode=trigger_mode,
            database_path=Path(os.getenv("DATABASE_PATH", "data/bot.sqlite3")),
            system_prompt=os.getenv(
                "SYSTEM_PROMPT",
                "你是一个在 Telegram 群里工作的中文 AI 助手。回答要简洁、直接、可执行；不知道就说不知道。",
            ),
            max_context_messages=int(os.getenv("MAX_CONTEXT_MESSAGES", "12")),
            post_mode=post_mode,
            target_channel_id=parse_optional_int(os.getenv("TARGET_CHANNEL_ID", "")),
            discussion_group_id=parse_optional_int(os.getenv("DISCUSSION_GROUP_ID", "")),
            copilot_admin_chat_id=parse_optional_int(os.getenv("COPILOT_ADMIN_CHAT_ID", "")),
            poll_timeout_seconds=int(os.getenv("POLL_TIMEOUT_SECONDS", "30")),
            mock_ai=os.getenv("MOCK_AI", "0").strip() == "1",
            store_passive_messages=os.getenv("STORE_PASSIVE_MESSAGES", "1").strip() == "1",
            autonomous_reply=os.getenv("AUTONOMOUS_REPLY", "0").strip() == "1",
            autonomous_reply_min_seconds=int(os.getenv("AUTONOMOUS_REPLY_MIN_SECONDS", "300")),
            autonomous_reply_max_per_hour=int(os.getenv("AUTONOMOUS_REPLY_MAX_PER_HOUR", "3")),
            openai_web_search=os.getenv("OPENAI_WEB_SEARCH", "1").strip() == "1",
            openai_web_search_tool=os.getenv("OPENAI_WEB_SEARCH_TOOL", "web_search").strip(),
            ai_chat_hourly_limit=int(os.getenv("AI_CHAT_HOURLY_LIMIT", "60")),
            ai_chat_daily_limit=int(os.getenv("AI_CHAT_DAILY_LIMIT", "300")),
            ai_global_hourly_limit=int(os.getenv("AI_GLOBAL_HOURLY_LIMIT", "0")),
            ai_global_daily_limit=int(os.getenv("AI_GLOBAL_DAILY_LIMIT", "0")),
            admin_user_ids=parse_int_set(os.getenv("ADMIN_USER_IDS", "")),
            admin_only_commands={
                command.lower() for command in parse_csv(os.getenv("ADMIN_ONLY_COMMANDS", "config,model,news,poll,copilot"))
            },
            news_enabled=os.getenv("NEWS_ENABLED", "0").strip() == "1",
            news_chat_ids=parse_int_set(os.getenv("NEWS_CHAT_IDS", "")),
            news_interval_minutes=int(os.getenv("NEWS_INTERVAL_MINUTES", "360")),
            news_count=int(os.getenv("NEWS_COUNT", "3")),
            news_keywords=parse_csv(os.getenv("NEWS_KEYWORDS", "")),
            news_rss_feeds=[
                item.strip()
                for item in os.getenv(
                    "NEWS_RSS_FEEDS",
                    "https://feeds.bbci.co.uk/news/world/rss.xml,https://www.theguardian.com/world/rss,https://rss.nytimes.com/services/xml/rss/nyt/World.xml,https://hnrss.org/frontpage",
                ).split(",")
                if item.strip()
            ],
            news_card_mode=news_card_mode,
            news_ai_summary=os.getenv("NEWS_AI_SUMMARY", "0").strip() == "1",
            news_with_poll=os.getenv("NEWS_WITH_POLL", "0").strip() == "1",
            news_discussion_map=parse_int_map(os.getenv("NEWS_DISCUSSION_MAP", "")),
            leaderboard_enabled=os.getenv("LEADERBOARD_ENABLED", "0").strip() == "1",
            leaderboard_chat_ids=parse_int_set(os.getenv("LEADERBOARD_CHAT_IDS", "")),
            leaderboard_interval_hours=int(os.getenv("LEADERBOARD_INTERVAL_HOURS", "168")),
            leaderboard_days=int(os.getenv("LEADERBOARD_DAYS", "7")),
            default_language=normalize_language(os.getenv("DEFAULT_LANGUAGE", "auto")),
            chat_language_mode=chat_language_mode,
            chat_language_overrides=parse_language_overrides(os.getenv("CHAT_LANGUAGE_OVERRIDES", "")),
        )


def parse_language_overrides(value: str) -> dict[int, str]:
    overrides: dict[int, str] = {}
    for part in value.split(","):
        item = part.strip()
        if not item or ":" not in item:
            continue
        chat_id, language = item.split(":", 1)
        overrides[int(chat_id.strip())] = normalize_language(language)
    return overrides
