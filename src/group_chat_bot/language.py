from __future__ import annotations

import re
from collections import Counter


SUPPORTED_LANGUAGES = {"auto", "zh", "en", "ko", "tr"}

LANGUAGE_NAMES = {
    "zh": "Chinese",
    "en": "English",
    "ko": "Korean",
    "tr": "Turkish",
}

LOCALIZED = {
    "help": {
        "zh": """可用命令：
/help - 查看帮助
/id - 查看当前 chat_id
/reset - 清空本群机器人上下文
/privacy - 查看群聊隐私模式说明
/chat 你的问题 - 让机器人回答
/ask 你的问题 - 同 /chat
/search 你的问题 - 带外网搜索回答
/news [关键词] - 随机发几条外媒/RSS 新闻
/poll 问题 | 选项1 | 选项2 - 发起投票
/leaderboard - 查看活跃榜
/model [模型名|reset] - 查看或切换本群 GPT 模型
/models - 查看可用 GPT 模型

群聊默认触发方式：
1. @机器人 你的问题
2. 回复机器人的消息
3. /chat 或 /ask 命令
""",
        "en": """Available commands:
/help - Show help
/id - Show this chat_id
/reset - Clear this chat context
/privacy - Explain Telegram group privacy mode
/chat your question - Ask the bot
/ask your question - Same as /chat
/search your question - Answer with web search
/news [keywords] - Send a few random news links
/poll question | option 1 | option 2 - Create a poll
/leaderboard - Show active members
/model [model|reset] - Show or switch this chat's GPT model
/models - Show available GPT models

Default group triggers:
1. @mention the bot
2. Reply to the bot
3. Use /chat or /ask
""",
        "ko": """사용 가능한 명령:
/help - 도움말 보기
/id - 현재 chat_id 보기
/reset - 이 그룹의 대화 맥락 초기화
/privacy - Telegram 그룹 개인정보 모드 설명
/chat 질문 - 봇에게 질문
/ask 질문 - /chat과 동일
/search 질문 - 웹 검색으로 답변
/news [키워드] - 무작위 뉴스 몇 개 전송
/poll 질문 | 선택지 1 | 선택지 2 - 투표 만들기
/leaderboard - 활발한 멤버 보기
/model [모델|reset] - 이 채팅의 GPT 모델 보기 또는 변경
/models - 사용 가능한 GPT 모델 보기

기본 그룹 호출 방식:
1. 봇을 @멘션
2. 봇 메시지에 답장
3. /chat 또는 /ask 사용
""",
        "tr": """Kullanılabilir komutlar:
/help - Yardımı göster
/id - Bu chat_id değerini göster
/reset - Bu sohbet bağlamını temizle
/privacy - Telegram grup gizlilik modunu açıkla
/chat sorun - Bota soru sor
/ask sorun - /chat ile aynı
/search sorun - Web aramasıyla yanıtla
/news [anahtar kelimeler] - Rastgele birkaç haber gönder
/poll soru | seçenek 1 | seçenek 2 - Anket oluştur
/leaderboard - Aktif üyeleri göster
/model [model|reset] - Bu sohbetin GPT modelini göster veya değiştir
/models - Kullanılabilir GPT modellerini göster

Varsayılan grup tetikleyicileri:
1. Botu @etiketle
2. Bot mesajını yanıtla
3. /chat veya /ask kullan
""",
    },
    "privacy": {
        "zh": "Telegram 机器人默认有群隐私模式。如果 BotFather 的 privacy mode 开启，机器人通常只会收到命令、回复机器人自己的消息和部分服务消息。要让它基于上下文主动回复，需要用 /setprivacy 关闭隐私模式。",
        "en": "Telegram bots have a group privacy mode. If privacy mode is enabled in BotFather, the bot usually only receives commands, replies to its own messages, and some service messages. To let it proactively respond from group context, disable privacy mode with /setprivacy.",
        "ko": "Telegram 봇에는 그룹 개인정보 모드가 있습니다. BotFather에서 privacy mode가 켜져 있으면 봇은 보통 명령, 봇 메시지에 대한 답장, 일부 서비스 메시지만 받습니다. 그룹 맥락을 보고 능동적으로 답하게 하려면 /setprivacy로 privacy mode를 꺼야 합니다.",
        "tr": "Telegram botlarında grup gizlilik modu vardır. BotFather'da privacy mode açıksa bot genelde yalnızca komutları, kendi mesajlarına verilen yanıtları ve bazı servis mesajlarını alır. Grup bağlamına göre proaktif yanıt vermesi için /setprivacy ile privacy mode'u kapatın.",
    },
    "ask_after_command": {
        "zh": "请在命令后面加问题，例如：/chat 帮我写一段群公告",
        "en": "Add your question after the command, for example: /chat write a group announcement",
        "ko": "명령 뒤에 질문을 붙여 주세요. 예: /chat 그룹 공지 문구를 써줘",
        "tr": "Komuttan sonra sorunuzu yazın. Örnek: /chat grup duyurusu yaz",
    },
    "search_after_command": {
        "zh": "请在命令后面加搜索问题，例如：/search 今天 AI 行业有什么新闻",
        "en": "Add a search question after the command, for example: /search latest AI industry news today",
        "ko": "명령 뒤에 검색 질문을 붙여 주세요. 예: /search 오늘 AI 업계 뉴스",
        "tr": "Komuttan sonra arama sorunuzu yazın. Örnek: /search bugün yapay zeka haberleri",
    },
    "empty_prompt": {
        "zh": "你想问什么？",
        "en": "What would you like to ask?",
        "ko": "무엇을 물어보고 싶나요?",
        "tr": "Ne sormak istersiniz?",
    },
    "ai_failed": {
        "zh": "AI 回复失败，请稍后再试。",
        "en": "AI reply failed. Please try again later.",
        "ko": "AI 답변에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        "tr": "AI yanıtı başarısız oldu. Lütfen daha sonra tekrar deneyin.",
    },
    "reset_done": {
        "zh": "已清空本群上下文。",
        "en": "This chat context has been cleared.",
        "ko": "이 채팅의 맥락을 초기화했습니다.",
        "tr": "Bu sohbet bağlamı temizlendi.",
    },
    "news_header": {
        "zh": "随机新闻：",
        "en": "Random news:",
        "ko": "무작위 뉴스:",
        "tr": "Rastgele haberler:",
    },
    "news_empty": {
        "zh": "暂时没有抓到新闻。",
        "en": "No news found for now.",
        "ko": "현재 가져온 뉴스가 없습니다.",
        "tr": "Şimdilik haber bulunamadı.",
    },
    "poll_usage": {
        "zh": "用法：/poll 问题 | 选项1 | 选项2",
        "en": "Usage: /poll question | option 1 | option 2",
        "ko": "사용법: /poll 질문 | 선택지 1 | 선택지 2",
        "tr": "Kullanım: /poll soru | seçenek 1 | seçenek 2",
    },
    "poll_question": {
        "zh": "你怎么看？",
        "en": "What do you think?",
        "ko": "어떻게 생각하나요?",
        "tr": "Ne düşünüyorsunuz?",
    },
    "poll_options": {
        "zh": "值得关注|一般|不重要",
        "en": "Worth watching|Neutral|Not important",
        "ko": "주목할 만함|보통|중요하지 않음",
        "tr": "Takip edilmeli|Kararsızım|Önemli değil",
    },
    "discussion_prompt": {
        "zh": "讨论一下：这条新闻最值得关注的点是什么？",
        "en": "Discussion: what is the most important point in this story?",
        "ko": "토론: 이 뉴스에서 가장 주목할 점은 무엇인가요?",
        "tr": "Tartışma: Bu haberde en önemli nokta nedir?",
    },
    "leaderboard_header": {
        "zh": "近 {days} 天活跃榜：",
        "en": "Active members in the last {days} days:",
        "ko": "최근 {days}일 활발한 멤버:",
        "tr": "Son {days} günün aktif üyeleri:",
    },
    "leaderboard_empty": {
        "zh": "还没有足够的活跃数据。",
        "en": "Not enough activity data yet.",
        "ko": "아직 충분한 활동 데이터가 없습니다.",
        "tr": "Henüz yeterli etkinlik verisi yok.",
    },
    "model_current": {
        "zh": "当前模型：{model}",
        "en": "Current model: {model}",
        "ko": "현재 모델: {model}",
        "tr": "Mevcut model: {model}",
    },
    "model_list": {
        "zh": "可用模型：\n{models}\n\n当前模型：{current}",
        "en": "Available models:\n{models}\n\nCurrent model: {current}",
        "ko": "사용 가능한 모델:\n{models}\n\n현재 모델: {current}",
        "tr": "Kullanılabilir modeller:\n{models}\n\nMevcut model: {current}",
    },
    "model_set": {
        "zh": "已切换本群模型：{model}",
        "en": "This chat now uses: {model}",
        "ko": "이 채팅의 모델을 변경했습니다: {model}",
        "tr": "Bu sohbetin modeli değiştirildi: {model}",
    },
    "model_reset": {
        "zh": "已恢复默认模型：{model}",
        "en": "Default model restored: {model}",
        "ko": "기본 모델로 복원했습니다: {model}",
        "tr": "Varsayılan model geri yüklendi: {model}",
    },
    "model_not_allowed": {
        "zh": "不允许使用这个模型：{model}\n可用模型：{models}",
        "en": "This model is not allowed: {model}\nAvailable models: {models}",
        "ko": "이 모델은 허용되지 않습니다: {model}\n사용 가능한 모델: {models}",
        "tr": "Bu modele izin verilmiyor: {model}\nKullanılabilir modeller: {models}",
    },
}


def normalize_language(value: str | None) -> str:
    value = (value or "auto").strip().lower()
    aliases = {
        "chinese": "zh",
        "zh-cn": "zh",
        "zh_hans": "zh",
        "english": "en",
        "korean": "ko",
        "kr": "ko",
        "turkish": "tr",
    }
    value = aliases.get(value, value)
    return value if value in SUPPORTED_LANGUAGES else "auto"


def localize(key: str, language: str) -> str:
    language = normalize_language(language)
    if language == "auto":
        language = "zh"
    table = LOCALIZED[key]
    return table.get(language) or table["zh"]


def language_instruction(language: str) -> str:
    language = normalize_language(language)
    if language == "auto":
        language = "zh"
    name = LANGUAGE_NAMES.get(language, "Chinese")
    return (
        f"Reply in {name}. Match the chat's tone. "
        "If the user asks for translation or a different language, follow the user's explicit request."
    )


def detect_language(text: str, default: str = "zh") -> str:
    scores = Counter()
    if re.search(r"[\uac00-\ud7a3]", text):
        scores["ko"] += 5
    if re.search(r"[\u4e00-\u9fff]", text):
        scores["zh"] += 4
    if re.search(r"[çğıöşüÇĞİÖŞÜ]", text):
        scores["tr"] += 4

    words = re.findall(r"[A-Za-zçğıöşüÇĞİÖŞÜ']+", text.lower())
    if words:
        tr_words = {
            "ve", "bir", "bu", "şu", "için", "ile", "nasıl", "neden", "haber",
            "bugün", "lütfen", "bana", "var", "yok", "mi", "mı", "mu", "mü",
        }
        en_words = {
            "the", "and", "is", "are", "what", "how", "why", "news", "today",
            "please", "can", "could", "help", "explain", "summarize",
        }
        scores["tr"] += sum(1 for word in words if word in tr_words)
        scores["en"] += sum(1 for word in words if word in en_words)
        if not scores["tr"]:
            scores["en"] += 1

    if not scores:
        return normalize_language(default)
    language, score = scores.most_common(1)[0]
    return language if score > 0 else normalize_language(default)


def detect_language_from_messages(messages: list[dict[str, str]], default: str = "zh") -> str:
    combined = "\n".join(message.get("content", "") for message in messages[-8:])
    return detect_language(combined, default=default)
