# Telegram Group Chat Bot

一个可运行的 Telegram 群聊 AI 机器人。默认只在群里 `@机器人`、回复机器人消息，或使用 `/chat`、`/ask` 命令时响应，避免打扰群聊。

## 功能

- Telegram Bot API 长轮询，无需公网服务器即可先跑起来。
- OpenAI AI 回复。
- 群聊触发规则：`mention_or_reply`、`always`、`command_only`。
- SQLite 保存最近上下文。
- 群白名单，避免机器人被拉到陌生群后被滥用。
- 可选自主回复：根据群聊上下文判断是否应该主动插话。
- 自动按群聊/频道语言回复：支持中文、韩语、英语、土耳其语。
- `/search` 使用 OpenAI Responses API 的 web search 工具回答最新外网问题。
- `/news` 从外媒/RSS 源随机发几条新闻。
- 可选定时新闻推送。
- 新闻卡片：把链接变成摘要、价值点和互动问题。
- 自动投票：新闻后自动发投票，或手动 `/poll`。
- 讨论群联动：频道发新闻后，在绑定讨论群抛问题。
- 活跃榜：记录群成员发言活跃度，手动或定时发榜。
- `/help`、`/id`、`/reset`、`/privacy`、`/chat`、`/ask` 命令。
- Dockerfile 和本地运行脚本。

## 创建 Telegram Bot

1. 在 Telegram 找到 `@BotFather`。
2. 发送 `/newbot`，按提示创建 bot。
3. 保存 BotFather 返回的 token。
4. 发送 `/setprivacy`，选择你的 bot：
   - 推荐保持 `Enable`，这样群里只有命令、回复和部分服务消息会发给 bot。
   - 如果你想让 bot 读取群里所有消息，改成 `Disable`，并把 `.env` 的 `TRIGGER_MODE=always`。
5. 把 bot 加进群。
6. 在群里发送 `/id`，拿到群 ID 后填入 `ALLOWED_CHAT_IDS`。

## 本地运行

```bash
cd telegram-group-bot
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```bash
TELEGRAM_BOT_TOKEN=123456:telegram-token
OPENAI_API_KEY=sk-...
ALLOWED_CHAT_IDS=-1001234567890
```

启动：

```bash
PYTHONPATH=src python -m group_chat_bot
```

## 群里怎么用

```text
@你的机器人 总结一下刚才讨论的上线风险
/chat 给我一个发公告的文案
/ask 解释一下 Apple 内购审核要注意什么
/search 今天 AI 行业有什么新闻
/news AI crypto
/poll 你更看好哪个市场？ | 韩国 | 土耳其 | 美国
/leaderboard
```

也可以直接回复机器人的消息继续对话。

## 配置

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | 必填 | BotFather 给的 token |
| `OPENAI_API_KEY` | 可选 | AI 回复需要；不填且 `MOCK_AI=1` 时走本地假回复 |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI 模型 |
| `BOT_USERNAME` | 自动读取 | 可手填，不带 `@` |
| `ALLOWED_CHAT_IDS` | 空 | 逗号分隔；空代表不限制，不推荐生产使用 |
| `TRIGGER_MODE` | `mention_or_reply` | `mention_or_reply`、`always`、`command_only` |
| `DATABASE_PATH` | `data/bot.sqlite3` | SQLite 文件 |
| `SYSTEM_PROMPT` | 内置中文助手提示 | 机器人角色 |
| `MAX_CONTEXT_MESSAGES` | `12` | 每个 chat 带入模型的上下文条数 |
| `POLL_TIMEOUT_SECONDS` | `30` | Telegram 长轮询超时 |
| `MOCK_AI` | `0` | `1` 时不用 OpenAI，方便测试 Telegram 通路 |
| `STORE_PASSIVE_MESSAGES` | `1` | 是否把非触发群消息存入上下文 |
| `AUTONOMOUS_REPLY` | `0` | 是否允许机器人根据上下文主动回复 |
| `AUTONOMOUS_REPLY_MIN_SECONDS` | `300` | 同一群两次主动回复最少间隔 |
| `AUTONOMOUS_REPLY_MAX_PER_HOUR` | `3` | 同一群每小时最多主动回复次数 |
| `DEFAULT_LANGUAGE` | `auto` | 默认语言：`auto`、`zh`、`en`、`ko`、`tr` |
| `CHAT_LANGUAGE_MODE` | `auto` | `auto` 自动检测，`fixed` 固定用默认语言 |
| `CHAT_LANGUAGE_OVERRIDES` | 空 | 指定群/频道语言，例如 `-1001:ko,-1002:tr` |
| `OPENAI_WEB_SEARCH` | `1` | `/search` 是否启用 OpenAI web search |
| `OPENAI_WEB_SEARCH_TOOL` | `web_search` | OpenAI web search 工具类型 |
| `NEWS_ENABLED` | `0` | 是否启用定时新闻 |
| `NEWS_CHAT_IDS` | 空 | 定时新闻发送群；空时使用 `ALLOWED_CHAT_IDS` |
| `NEWS_INTERVAL_MINUTES` | `360` | 新闻推送间隔 |
| `NEWS_COUNT` | `3` | 每次新闻条数 |
| `NEWS_KEYWORDS` | 空 | 新闻关键词过滤 |
| `NEWS_RSS_FEEDS` | 内置外媒 RSS | 逗号分隔 RSS 源 |
| `NEWS_CARD_MODE` | `card` | `card` 新闻卡片，`links` 只发链接 |
| `NEWS_AI_SUMMARY` | `0` | 是否用 AI 改写新闻卡片 |
| `NEWS_WITH_POLL` | `0` | 新闻后是否自动发投票 |
| `NEWS_DISCUSSION_MAP` | 空 | 频道到讨论群映射，如 `-100channel:-100group` |
| `LEADERBOARD_ENABLED` | `0` | 是否定时发活跃榜 |
| `LEADERBOARD_CHAT_IDS` | 空 | 定时发榜的群；空时用 `ALLOWED_CHAT_IDS` |
| `LEADERBOARD_INTERVAL_HOURS` | `168` | 发榜间隔，默认 7 天 |
| `LEADERBOARD_DAYS` | `7` | 统计最近几天活跃 |

## 自主回复和新闻

开启自主回复：

```bash
AUTONOMOUS_REPLY=1
STORE_PASSIVE_MESSAGES=1
AUTONOMOUS_REPLY_MIN_SECONDS=300
AUTONOMOUS_REPLY_MAX_PER_HOUR=3
```

Telegram 群隐私模式会影响自主回复。如果 BotFather 的 privacy mode 开启，机器人通常收不到普通群消息；要让它基于上下文主动回复，需要用 `/setprivacy` 关闭隐私模式。

开启定时新闻：

```bash
NEWS_ENABLED=1
NEWS_CHAT_IDS=-1001234567890
NEWS_INTERVAL_MINUTES=360
NEWS_COUNT=3
NEWS_KEYWORDS=AI,crypto
NEWS_CARD_MODE=card
NEWS_AI_SUMMARY=1
NEWS_WITH_POLL=1
```

`/news` 命令不依赖定时开关，随时可用。

频道和讨论群联动：

```bash
NEWS_DISCUSSION_MAP=-1001111111111:-1002222222222
```

左边是频道 ID，右边是讨论群 ID。机器人需要同时在频道和讨论群里有发消息权限。

定时活跃榜：

```bash
LEADERBOARD_ENABLED=1
LEADERBOARD_CHAT_IDS=-1002222222222
LEADERBOARD_INTERVAL_HOURS=168
LEADERBOARD_DAYS=7
```

## 多语言

机器人会根据最新消息和最近上下文自动判断回复语言，支持：

- `zh` 中文
- `en` English
- `ko` 한국어
- `tr` Türkçe

固定某个群或频道的语言：

```bash
CHAT_LANGUAGE_OVERRIDES=-1001234567890:ko,-1009876543210:tr
```

全部固定英文：

```bash
DEFAULT_LANGUAGE=en
CHAT_LANGUAGE_MODE=fixed
```

如果你把机器人加到 Telegram 频道里，需要把机器人设为频道管理员，它才能收到 `channel_post` 并发消息。

## Docker

```bash
docker build -t telegram-group-bot .
docker run --env-file .env -v "$PWD/data:/app/data" telegram-group-bot
```

## 部署建议

先用长轮询跑通。稳定后再考虑 webhook：

- 长轮询：部署简单，适合 VPS、家用 Mac、开发测试。
- Webhook：需要公网 HTTPS 域名，适合生产规模化。

## 注意

- 群白名单很重要。把 `ALLOWED_CHAT_IDS` 配好，避免被陌生群使用。
- 如果 BotFather 隐私模式开启，bot 不会收到群里所有普通消息，这是 Telegram 的设计。
- 不要把 `.env` 提交到 Git。
