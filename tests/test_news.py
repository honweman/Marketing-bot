from group_chat_bot.news import format_news, format_news_card, parse_rss


def test_parse_rss():
    items = parse_rss(
        """
        <rss><channel>
          <title>Example News</title>
          <item>
            <title>Breaking &amp; Useful</title>
            <link>https://example.com/a</link>
            <pubDate>Tue, 30 Jun 2026 10:00:00 GMT</pubDate>
            <description><![CDATA[<p>Summary</p>]]></description>
          </item>
        </channel></rss>
        """
    )
    assert len(items) == 1
    assert items[0].title == "Breaking & Useful"
    assert items[0].source == "Example News"
    assert items[0].link == "https://example.com/a"
    assert "Why it matters" in format_news_card(items[0], language="en")


def test_format_news_empty():
    assert "暂时" in format_news([])
    assert "No news" in format_news([], language="en")
    assert "뉴스" in format_news([], language="ko")
    assert "haber" in format_news([], language="tr").lower()
