"""Podcast RSSフィードを生成・更新"""
import os
import logging
from datetime import datetime
from xml.etree.ElementTree import (
    Element, SubElement, ElementTree, parse as parse_xml, indent, tostring
)
from email.utils import formatdate
from pathlib import Path

from config import (
    PODCAST_TITLE, PODCAST_DESCRIPTION, PODCAST_AUTHOR,
    PODCAST_LANGUAGE, PODCAST_CATEGORY, PODCAST_IMAGE,
    GITHUB_PAGES_URL, RSS_FILE, MAX_EPISODES, AUDIO_DIR
)

logger = logging.getLogger(__name__)

ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"


def create_new_feed() -> Element:
    """新しいRSSフィードのルート要素を作成"""
    rss = Element("rss", {
        "version": "2.0",
        "xmlns:itunes": ITUNES_NS,
    })
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = PODCAST_TITLE
    SubElement(channel, "link").text = GITHUB_PAGES_URL
    SubElement(channel, "language").text = PODCAST_LANGUAGE
    SubElement(channel, "description").text = PODCAST_DESCRIPTION
    SubElement(channel, f"{{{ITUNES_NS}}}author").text = PODCAST_AUTHOR
    SubElement(channel, f"{{{ITUNES_NS}}}explicit").text = "false"

    category = SubElement(channel, f"{{{ITUNES_NS}}}category")
    category.set("text", PODCAST_CATEGORY)

    image = SubElement(channel, f"{{{ITUNES_NS}}}image")
    image.set("href", f"{GITHUB_PAGES_URL}/{PODCAST_IMAGE}")

    return rss


def format_duration(seconds: float) -> str:
    """秒数をMM:SS形式に変換"""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"


def add_episode(
    rss: Element,
    filename: str,
    title: str,
    summary: str,
    duration_seconds: float,
    pub_date: datetime = None,
):
    """エピソードをRSSフィードに追加"""
    channel = rss.find("channel")
    if pub_date is None:
        pub_date = datetime.now()

    item = Element("item")
    SubElement(item, "title").text = title
    SubElement(item, "description").text = summary

    file_path = AUDIO_DIR / filename
    file_size = os.path.getsize(file_path) if file_path.exists() else 0

    enclosure = SubElement(item, "enclosure")
    enclosure.set("url", f"{GITHUB_PAGES_URL}/episodes/{filename}")
    enclosure.set("length", str(file_size))
    enclosure.set("type", "audio/mpeg")

    guid = SubElement(item, "guid")
    guid.set("isPermaLink", "false")
    guid.text = filename.replace(".mp3", "")

    SubElement(item, "pubDate").text = formatdate(
        pub_date.timestamp(), localtime=True
    )
    SubElement(item, f"{{{ITUNES_NS}}}duration").text = format_duration(duration_seconds)
    SubElement(item, f"{{{ITUNES_NS}}}summary").text = summary

    # 先頭（最新）に挿入
    items = channel.findall("item")
    if items:
        channel.insert(list(channel).index(items[0]), item)
    else:
        channel.append(item)

    # 古いエピソードを削除
    items = channel.findall("item")
    while len(items) > MAX_EPISODES:
        channel.remove(items[-1])
        items = channel.findall("item")

    logger.info(f"エピソード追加: {title}")


def load_or_create_feed() -> Element:
    """既存のRSSを読み込むか新規作成"""
    if RSS_FILE.exists():
        try:
            tree = parse_xml(RSS_FILE)
            return tree.getroot()
        except Exception as e:
            logger.warning(f"RSS読み込み失敗、新規作成: {e}")
    return create_new_feed()


def save_feed(rss: Element):
    """RSSをファイルに保存"""
    RSS_FILE.parent.mkdir(parents=True, exist_ok=True)
    indent(rss)
    tree = ElementTree(rss)
    tree.write(str(RSS_FILE), encoding="unicode", xml_declaration=True)
    logger.info(f"RSS保存: {RSS_FILE}")


def update_rss(filename: str, articles: list[dict], duration_seconds: float):
    """RSSフィードを更新"""
    today = datetime.now().strftime("%Y年%m月%d日")
    title = f"{today}のAIニュース"

    # サマリーをニュースタイトルから生成
    summary_lines = [f"・{a['title']}" for a in articles]
    summary = f"今日のトピック:\n" + "\n".join(summary_lines)

    rss = load_or_create_feed()
    add_episode(rss, filename, title, summary, duration_seconds)
    save_feed(rss)
