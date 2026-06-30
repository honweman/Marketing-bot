from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .bot import GroupChatBot, IncomingMessage


CommandHandler = Callable[["GroupChatBot", "IncomingMessage", str, str, str], None]


@dataclass(frozen=True)
class CommandPlugin:
    name: str
    commands: tuple[str, ...]
    handler: CommandHandler
    description: str = ""

    def handle(
        self,
        bot: GroupChatBot,
        message: IncomingMessage,
        command: str,
        arg: str,
        language: str,
    ) -> None:
        self.handler(bot, message, command, arg, language)


def build_default_plugins() -> list[CommandPlugin]:
    return [
        CommandPlugin(
            name="core",
            commands=("start", "help", "id", "reset", "privacy"),
            handler=lambda bot, message, command, arg, language: bot.handle_core_command(
                message, command, arg, language
            ),
            description="Basic help, id, privacy, and context reset commands.",
        ),
        CommandPlugin(
            name="chat",
            commands=("chat", "ask"),
            handler=lambda bot, message, command, arg, language: bot.handle_chat_command(
                message, command, arg, language
            ),
            description="Context-aware AI replies.",
        ),
        CommandPlugin(
            name="search",
            commands=("search",),
            handler=lambda bot, message, command, arg, language: bot.handle_search_command(
                message, command, arg, language
            ),
            description="AI replies with web search.",
        ),
        CommandPlugin(
            name="news",
            commands=("news",),
            handler=lambda bot, message, command, arg, language: bot.handle_news_command(
                message, command, arg, language
            ),
            description="Random RSS/news posts.",
        ),
        CommandPlugin(
            name="poll",
            commands=("poll",),
            handler=lambda bot, message, command, arg, language: bot.handle_poll_command(
                message, command, arg, language
            ),
            description="Manual Telegram polls.",
        ),
        CommandPlugin(
            name="leaderboard",
            commands=("leaderboard",),
            handler=lambda bot, message, command, arg, language: bot.handle_leaderboard_command(
                message, command, arg, language
            ),
            description="Activity leaderboard.",
        ),
        CommandPlugin(
            name="model",
            commands=("model", "models"),
            handler=lambda bot, message, command, arg, language: bot.handle_model_plugin_command(
                message, command, arg, language
            ),
            description="Per-chat GPT model switching.",
        ),
        CommandPlugin(
            name="config",
            commands=("config",),
            handler=lambda bot, message, command, arg, language: bot.handle_config_command(
                message, command, arg, language
            ),
            description="Per-chat settings entry point.",
        ),
    ]


def command_index(plugins: list[CommandPlugin]) -> dict[str, CommandPlugin]:
    index: dict[str, CommandPlugin] = {}
    for plugin in plugins:
        for command in plugin.commands:
            index[command] = plugin
    return index


def plugin_commands(plugins: list[CommandPlugin]) -> tuple[str, ...]:
    return tuple(command_index(plugins).keys())


DEFAULT_PLUGINS = build_default_plugins()
DEFAULT_COMMANDS = plugin_commands(DEFAULT_PLUGINS)
