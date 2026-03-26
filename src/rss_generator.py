"""Podcast RSSフィードを生成・更新（Spotify互換XML出力）"""
import os
import logging
from datetime import datetime
from email.utils import formatdate
from pathlib import Path
from xml.sax.saxutils import escape

from config import (
    PODCAST_TITLE, PODCAST_DESCRIPTION, PODCAST_AUTHOR, PODCAST_EMAIL,
    PODCAST_LANGUAGE, PODCAST_CATEGORY, PODCAST_IMAGE,
    GITHUB_PAGES_URL, RSS_FILE, MAX_EPISODES, AUDIO_DIR
)

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    """秒数をMM:SS形式に変換"""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"


def build_feed_xml(episodes: list[dict]) -> str:
    """RSSフィードXMLを文字列で構築（itunes:プレフィックスを正しく出力）"""
    items_xml = ""
    for ep in episodes[:MAX_EPISODES]:
        items_xml += f"""    <item>
      <title>{escape(ep['title'])}</title>
      <description>{escape(ep['description'])}</description>
      <enclosure url="{escape(ep['enclosure_url'])}" length="{ep['length']}" type="audio/mpeg" />
      <guid isPermaLink="false">{escape(ep['guid'])}</guid>
      <pubDate>{ep['pub_date']}</pubDate>
      <itunes:duration>{ep['duration']}</itunes:duration>
      <itunes:summary>{escape(ep['description'])}</itunes:summary>
      <itunes:episode>{ep.get('episode_number', 1)}</itunes:episode>
    </item>
"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{escape(PODCAST_TITLE)}</title>
    <link>{GITHUB_PAGES_URL}</link>
    <language>{PODCAST_LANGUAGE}</language>
    <description>{escape(PODCAST_DESCRIPTION)}</description>
    <itunes:author>{escape(PODCAST_AUTHOR)}</itunes:author>
    <itunes:owner>
      <itunes:name>{escape(PODCAST_AUTHOR)}</itunes:name>
      <itunes:email>{escape(PODCAST_EMAIL)}</itunes:email>
    </itunes:owner>
    <itunes:explicit>false</itunes:explicit>
    <itunes:type>episodic</itunes:type>
    <itunes:category text="{escape(PODCAST_CATEGORY)}" />
    <itunes:image href="{GITHUB_PAGES_URL}/{PODCAST_IMAGE}" />
    <image>
      <url>{GITHUB_PAGES_URL}/{PODCAST_IMAGE}</url>
      <title>{escape(PODCAST_TITLE)}</title>
      <link>{GITHUB_PAGES_URL}</link>
    </image>
{items_xml}  </channel>
</rss>
"""
    return xml


def load_episodes() -> list[dict]:
    """既存のfeed.xmlからエピソードを読み込む"""
    if not RSS_FILE.exists():
        return []
    try:
        from xml.etree.ElementTree import parse as parse_xml
        tree = parse_xml(RSS_FILE)
        root = tree.getroot()
        ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
        episodes = []
        for item in root.findall(".//item"):
            enclosure = item.find("enclosure")
            duration_el = item.find("itunes:duration", ns)
            episode_num_el = item.find("itunes:episode", ns)
            episodes.append({
                "title": item.findtext("title", ""),
                "description": item.findtext("description", ""),
                "enclosure_url": enclosure.get("url", "") if enclosure is not None else "",
                "length": enclosure.get("length", "0") if enclosure is not None else "0",
                "guid": item.findtext("guid", ""),
                "pub_date": item.findtext("pubDate", ""),
                "duration": duration_el.text if duration_el is not None else "00:00",
                "episode_number": int(episode_num_el.text) if episode_num_el is not None else 1,
            })
        return episodes
    except Exception as e:
        logger.warning(f"RSS読み込み失敗、新規作成: {e}")
        return []


def save_feed(xml_str: str):
    """RSSをファイルに保存"""
    RSS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RSS_FILE, "w", encoding="utf-8") as f:
        f.write(xml_str)
    logger.info(f"RSS保存: {RSS_FILE}")


def update_rss(filename: str, articles: list[dict], duration_seconds: float):
    """RSSフィードを更新"""
    today = datetime.now().strftime("%B %d, %Y")
    title = f"AI News - {today}"

    summary_lines = [f"• {a['title']}" for a in articles]
    summary = "Today's topics:\n" + "\n".join(summary_lines)

    file_path = AUDIO_DIR / filename
    file_size = os.path.getsize(file_path) if file_path.exists() else 0

    # 既存エピソードを読み込み
    episodes = load_episodes()

    # エピソード番号を算出
    episode_number = len(episodes) + 1

    # 新しいエピソードを先頭に追加
    new_episode = {
        "title": title,
        "description": summary,
        "enclosure_url": f"{GITHUB_PAGES_URL}/episodes/{filename}",
        "length": str(file_size),
        "guid": filename.replace(".mp3", ""),
        "pub_date": formatdate(datetime.now().timestamp(), localtime=True),
        "duration": format_duration(duration_seconds),
        "episode_number": episode_number,
    }
    episodes.insert(0, new_episode)

    # フィードを生成・保存
    xml_str = build_feed_xml(episodes)
    save_feed(xml_str)
    logger.info(f"エピソード追加: {title}")
