"""Google News RSSからAIニュースを収集"""
import feedparser
import requests
import time
import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import quote

try:
    import trafilatura
except ImportError:
    trafilatura = None

from config import NEWS_QUERIES, MAX_ARTICLES

logger = logging.getLogger(__name__)


def build_rss_url(query: str) -> str:
    """Google News RSS URLを構築"""
    encoded = quote(query)
    return f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"


def is_similar(title1: str, title2: str, threshold: float = 0.6) -> bool:
    """タイトルの類似度で重複判定"""
    return SequenceMatcher(None, title1, title2).ratio() > threshold


def extract_article_text(url: str) -> str:
    """記事本文を抽出（先頭500文字）"""
    try:
        resp = requests.get(url, timeout=10, allow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0"})
        if trafilatura:
            text = trafilatura.extract(resp.text)
            if text:
                return text[:500]
        return ""
    except Exception as e:
        logger.warning(f"記事取得失敗: {url} - {e}")
        return ""


def collect_news() -> list[dict]:
    """AIニュースを収集して返す"""
    all_entries = []
    cutoff = datetime.now() - timedelta(hours=36)

    for query in NEWS_QUERIES:
        url = build_rss_url(query)
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                pub_date = datetime(*entry.published_parsed[:6]) if hasattr(entry, 'published_parsed') and entry.published_parsed else None
                if pub_date and pub_date < cutoff:
                    continue
                all_entries.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "source": entry.get("source", {}).get("title", "不明") if hasattr(entry, "source") else "不明",
                    "published": pub_date,
                    "description": entry.get("description", ""),
                })
        except Exception as e:
            logger.warning(f"RSS取得失敗 [{query}]: {e}")
        time.sleep(1)

    # 重複排除
    unique = []
    for entry in all_entries:
        if not any(is_similar(entry["title"], u["title"]) for u in unique):
            unique.append(entry)

    # 新しい順にソート
    unique.sort(key=lambda x: x.get("published") or datetime.min, reverse=True)

    # 上位N件の本文を取得
    results = []
    for entry in unique[:MAX_ARTICLES]:
        summary = extract_article_text(entry["link"])
        if not summary:
            # フォールバック: descriptionを使用
            summary = entry.get("description", "")[:300]
        results.append({
            "title": entry["title"],
            "source": entry["source"],
            "url": entry["link"],
            "summary": summary,
            "date": entry.get("published", datetime.now()).strftime("%Y-%m-%d") if entry.get("published") else datetime.now().strftime("%Y-%m-%d"),
        })
        time.sleep(1)

    logger.info(f"ニュース {len(results)} 件を収集")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    articles = collect_news()
    for a in articles:
        print(f"[{a['source']}] {a['title']}")
        print(f"  {a['summary'][:100]}...")
        print()
