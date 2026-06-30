from __future__ import annotations

import html
import random
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from email.utils import parsedate_to_datetime

from .language import localize


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str
    source: str
    published: str
    summary: str = ""


def fetch_random_news(feeds: list[str], keywords: list[str], count: int) -> list[NewsItem]:
    items: list[NewsItem] = []
    for feed_url in feeds:
        try:
            items.extend(fetch_feed(feed_url))
        except Exception:
            continue

    if keywords:
        lowered = [keyword.lower() for keyword in keywords]
        items = [
            item
            for item in items
            if any(keyword in f"{item.title} {item.summary}".lower() for keyword in lowered)
        ]

    deduped: dict[str, NewsItem] = {}
    for item in items:
        key = item.link or item.title
        deduped[key] = item

    pool = list(deduped.values())
    random.shuffle(pool)
    return pool[: max(1, count)]


def fetch_feed(feed_url: str) -> list[NewsItem]:
    req = urllib.request.Request(feed_url, headers={"User-Agent": "telegram-group-bot/0.1"})
    with urllib.request.urlopen(req, timeout=20) as response:
        xml_text = response.read().decode("utf-8", errors="replace")
    return parse_rss(xml_text, fallback_source=source_from_url(feed_url))


def parse_rss(xml_text: str, fallback_source: str = "News") -> list[NewsItem]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    source = text_of(channel, "title") if channel is not None else fallback_source
    source = source or fallback_source

    items: list[NewsItem] = []
    rss_items = root.findall(".//item")
    atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")

    for item in rss_items:
        title = clean_text(text_of(item, "title"))
        link = clean_text(text_of(item, "link"))
        published = clean_date(text_of(item, "pubDate") or text_of(item, "published"))
        summary = clean_text(text_of(item, "description"))
        if title and link:
            items.append(NewsItem(title=title, link=link, source=source, published=published, summary=summary))

    for entry in atom_entries:
        title = clean_text(text_of(entry, "{http://www.w3.org/2005/Atom}title"))
        link_node = entry.find("{http://www.w3.org/2005/Atom}link")
        link = link_node.attrib.get("href", "") if link_node is not None else ""
        published = clean_date(text_of(entry, "{http://www.w3.org/2005/Atom}updated"))
        summary = clean_text(text_of(entry, "{http://www.w3.org/2005/Atom}summary"))
        if title and link:
            items.append(NewsItem(title=title, link=link, source=source, published=published, summary=summary))

    return items


def format_news(items: list[NewsItem], language: str = "zh") -> str:
    if not items:
        return localize("news_empty", language)

    lines = [localize("news_header", language)]
    for index, item in enumerate(items, start=1):
        meta = item.source
        if item.published:
            meta = f"{meta} · {item.published}"
        lines.append(f"{index}. {item.title}\n{meta}\n{item.link}")
    return "\n\n".join(lines)


def format_news_card(item: NewsItem, language: str = "zh") -> str:
    labels = {
        "zh": ("为什么值得看", "互动问题", "原文"),
        "en": ("Why it matters", "Question", "Source"),
        "ko": ("왜 중요한가", "질문", "원문"),
        "tr": ("Neden önemli", "Soru", "Kaynak"),
    }
    why, question, source = labels.get(language, labels["zh"])
    summary = item.summary[:220] if item.summary else item.title
    prompts = {
        "zh": "你怎么看这件事？",
        "en": "What do you think about this?",
        "ko": "이 이슈에 대해 어떻게 생각하나요?",
        "tr": "Bu konu hakkında ne düşünüyorsunuz?",
    }
    meta = item.source
    if item.published:
        meta = f"{meta} · {item.published}"
    return f"{item.title}\n{meta}\n\n{why}: {summary}\n\n{question}: {prompts.get(language, prompts['zh'])}\n\n{source}: {item.link}"


def text_of(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    found = node.find(tag)
    return found.text or "" if found is not None else ""


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def clean_date(value: str) -> str:
    value = clean_text(value)
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value[:32]


def source_from_url(url: str) -> str:
    host = re.sub(r"^https?://", "", url).split("/", 1)[0]
    return host.removeprefix("www.")
