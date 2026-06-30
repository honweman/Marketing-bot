from __future__ import annotations

from openai import OpenAI

from .language import language_instruction, localize
from .news import NewsItem, format_news_card


class AIResponder:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        system_prompt: str,
        mock: bool = False,
        web_search_enabled: bool = False,
        web_search_tool: str = "web_search",
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.mock = mock
        self.web_search_enabled = web_search_enabled
        self.web_search_tool = web_search_tool
        self.client = None if mock else OpenAI(api_key=api_key)

    def reply(
        self,
        prompt: str,
        context: list[dict[str, str]],
        use_web_search: bool = False,
        language: str = "zh",
        model: str | None = None,
    ) -> str:
        if self.mock:
            mock_text = {
                "zh": f"收到：{prompt}\n\n这是 MOCK_AI=1 的本地测试回复。",
                "en": f"Received: {prompt}\n\nThis is a local MOCK_AI=1 test reply.",
                "ko": f"받았습니다: {prompt}\n\n이것은 MOCK_AI=1 로컬 테스트 응답입니다.",
                "tr": f"Aldım: {prompt}\n\nBu, MOCK_AI=1 yerel test yanıtıdır.",
            }
            return mock_text.get(language, mock_text["zh"])

        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is required unless MOCK_AI=1")

        input_messages: list[dict[str, str]] = [
            {"role": "system", "content": f"{self.system_prompt}\n\n{language_instruction(language)}"},
            *context,
            {"role": "user", "content": prompt},
        ]
        kwargs = {
            "model": model or self.model,
            "input": input_messages,
        }
        if use_web_search and self.web_search_enabled:
            kwargs["tools"] = [{"type": self.web_search_tool}]
        response = self.client.responses.create(**kwargs)
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
        return localize("ai_failed", language)

    def should_autonomously_reply(
        self,
        latest_message: str,
        context: list[dict[str, str]],
        language: str = "zh",
        model: str | None = None,
    ) -> bool:
        if self.mock:
            markers = ("?", "？", "怎么", "如何", "为什么", "帮我", "谁知道", "有办法")
            return any(marker in latest_message for marker in markers)

        if self.client is None:
            return False

        prompt = (
            "你是 Telegram 群聊机器人，需要判断是否应该主动插话。"
            "只有当最新消息明显在求助、提出问题、需要事实核查、需要总结、或机器人回复能推进讨论时才回答。"
            "普通闲聊、情绪表达、无明确问题、或你不确定时不要回答。"
            "只输出 YES 或 NO。\n\n"
            f"最新消息：{latest_message}"
        )
        response = self.client.responses.create(
            model=model or self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a binary classifier. Output only YES or NO. "
                        f"The chat language is {language}; understand that language when judging."
                    ),
                },
                *context[-8:],
                {"role": "user", "content": prompt},
            ],
            max_output_tokens=8,
        )
        text = (getattr(response, "output_text", "") or "").strip().upper()
        return text.startswith("YES")

    def news_card(self, item: NewsItem, language: str = "zh", model: str | None = None) -> str:
        if self.mock:
            return format_news_card(item, language=language)

        if self.client is None:
            raise RuntimeError("OPENAI_API_KEY is required unless MOCK_AI=1")

        prompt = (
            "Turn this news item into a Telegram channel card. "
            "Keep it concise and engagement-oriented. Include: title, 2-3 bullet summary, why it matters, one discussion question, and source link. "
            f"{language_instruction(language)}\n\n"
            f"Title: {item.title}\n"
            f"Source: {item.source}\n"
            f"Published: {item.published}\n"
            f"Summary: {item.summary}\n"
            f"Link: {item.link}"
        )
        response = self.client.responses.create(
            model=model or self.model,
            input=[
                {"role": "system", "content": "You write concise, high-engagement Telegram channel posts."},
                {"role": "user", "content": prompt},
            ],
        )
        text = getattr(response, "output_text", None)
        return text.strip() if text else format_news_card(item, language=language)
