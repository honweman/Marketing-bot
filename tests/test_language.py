from group_chat_bot.language import detect_language, localize, normalize_language


def test_detect_language_supported_chats():
    assert detect_language("오늘 AI 뉴스 알려줘") == "ko"
    assert detect_language("What is the latest AI news today?") == "en"
    assert detect_language("Bugün yapay zeka haberleri var mı?") == "tr"
    assert detect_language("今天 AI 有什么新闻？") == "zh"


def test_localize():
    assert "Available commands" in localize("help", "en")
    assert "사용 가능한 명령" in localize("help", "ko")
    assert "Kullanılabilir" in localize("help", "tr")
    assert normalize_language("turkish") == "tr"
