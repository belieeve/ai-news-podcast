"""AI News Podcast - メインスクリプト

毎週日曜日朝にAIニュースを収集し、Podcast音声を生成してRSS配信する。
"""
from __future__ import annotations

import os
import re
import sys
import logging
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from zoneinfo import ZoneInfo

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from config import AUDIO_DIR, SCRIPTS_DIR, LOG_DIR, PODCAST_TITLE
from news_collector import collect_news
from script_generator import generate_script
from rss_generator import update_rss
from tts_generator import generate_audio

JST = ZoneInfo("Asia/Tokyo")

EPISODE_SLOTS = {
    "weekly": {
        "label": "週刊",
        "show_name": "週刊AI仕事術｜仕事と副業に効くAIニュース",
        "filename_suffix": "weekly",
    }
}


def setup_logging():
    """ロギング設定"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(JST).strftime("%Y%m%d")
    log_file = LOG_DIR / f"podcast_{today}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def send_email_via_gas(
    title: str,
    status: str,
    script: list[tuple[str, str]],
    summary: str,
    sns_draft: str,
    audit_log: str,
):
    """GASのWebHookを経由してメールを送信する"""
    gas_url = os.getenv("GAS_WEBHOOK_URL")
    if not gas_url:
        logging.getLogger(__name__).info("GAS_WEBHOOK_URL が設定されていないため、メール送信はスキップします。")
        return

    # 台本テキストの整形
    script_text = "\n".join(f"{speaker}: {line}" for speaker, line in script)

    payload = {
        "title": title,
        "status": status,
        "body": f"【エピソードタイトル】\n{title}\n\n"
                f"【Spotify概要欄】\n{summary}\n\n"
                f"【掛け合い台本】\n{script_text}\n\n"
                f"【SNS・ニュースレター用下書き】\n{sns_draft}",
        "audit_log": audit_log,
    }

    try:
        import requests
        response = requests.post(gas_url, json=payload, timeout=15)
        if response.status_code == 200 and "Success" in response.text:
            logging.getLogger(__name__).info("GAS経由でメールを正常に送信しました。")
        else:
            logging.getLogger(__name__).error(f"GASメール送信エラー: {response.text} (ステータス: {response.status_code})")
    except Exception as e:
        logging.getLogger(__name__).error(f"GASメール送信中に通信エラーが発生しました: {e}")


def save_script(
    script: list[tuple[str, str]],
    date_str: str,
    episode_label: str,
    filename_suffix: str,
    articles: list[dict] | None = None,
    title: str = "",
    summary: str = "",
    sns_draft: str = "",
    audit_log: str = "",
):
    """台本、タイトル、概要欄、SNS下書き、監査ログを保存。"""
    day_dir = SCRIPTS_DIR / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"script_{date_str}_{filename_suffix}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{PODCAST_TITLE} {episode_label} 台本パッケージ  {date_str}\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"【エピソードタイトル】\n{title}\n\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"【Spotify概要欄】\n{summary}\n\n")
        f.write("=" * 40 + "\n\n")
        if articles:
            f.write("【元になったニュース】\n")
            for i, a in enumerate(articles, 1):
                url_str = f" - {a.get('url', '')}" if a.get('url') else ""
                f.write(f"{i}. {a.get('title', '')}（{a.get('source', '')}）{url_str}\n")
            f.write("\n" + "=" * 40 + "\n\n")
        f.write("【掛け合い台本】\n")
        for speaker, line in script:
            f.write(f"{speaker}: {line}\n")
        f.write("\n" + "=" * 40 + "\n\n")
        if sns_draft:
            f.write("【SNS・ニュースレター用下書き】\n")
            f.write(sns_draft)
            f.write("\n\n" + "=" * 40 + "\n\n")
        if audit_log:
            f.write("【監査AIによるファクトチェックログ】\n")
            f.write(audit_log)
            f.write("\n")
    logging.getLogger(__name__).info(f"台本パッケージ保存: {path}")


def parse_slot(argv: list[str]) -> str:
    """--slot weekly を読み取る。未指定時は週刊扱い。"""
    if "--slot" not in argv:
        return "weekly"
    idx = argv.index("--slot")
    if idx + 1 >= len(argv):
        raise ValueError("--slot requires weekly")
    slot = argv[idx + 1]
    if slot not in EPISODE_SLOTS:
        raise ValueError(f"Unknown slot: {slot}. Use weekly.")
    return slot


def load_used_article_titles(date_str: str, filename_suffix: str) -> list[str]:
    """保存済み台本から、その回で扱ったニュースタイトルを読む。"""
    script_path = SCRIPTS_DIR / date_str / f"script_{date_str}_{filename_suffix}.txt"
    if not script_path.exists():
        return []

    titles: list[str] = []
    in_news_section = False
    for line in script_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "【元になったニュース】":
            in_news_section = True
            continue
        if in_news_section and stripped.startswith("===="):
            break
        if not in_news_section:
            continue
        # URL等がついている場合があるため、末尾のアンカーを外し前方一致でマッチ
        match = re.match(r"^\d+\.\s*(.+?)（.+?）", stripped)
        if match:
            titles.append(match.group(1))
    return titles


def script_text_length(script: list[tuple[str, str]]) -> int:
    """台本文字数を数える。話者名は除外し、実際に読まれる本文だけを見る。"""
    return sum(len(line.strip()) for _, line in script)


def is_script_plausible(script: list[tuple[str, str]], slot: str) -> bool:
    """放送として成立しない短すぎる台本を弾く。"""
    min_lines = 40
    min_chars = 3800
    return len(script) >= min_lines and script_text_length(script) >= min_chars


def is_audio_duration_plausible(duration_sec: float, slot: str) -> bool:
    """公開してよい最低限の音声尺かを見る。短すぎる音声はRSSに載せない。"""
    min_duration = 720  # 最低12分
    return duration_sec >= min_duration


def is_audio_duration_consistent(script: list[tuple[str, str]], duration_sec: float) -> bool:
    """台本文量に対して音声が短すぎる場合は本文欠落として扱う。"""
    expected_min = script_text_length(script) / 10
    if duration_sec < expected_min:
        logging.getLogger(__name__).error(
            "音声尺が台本文量に対して短すぎます: %.1f秒 / 最低目安 %.1f秒",
            duration_sec,
            expected_min,
        )
        return False
    return True


def _clean_fragment(text: str) -> str:
    """記事タイトル比較用に記号や空白をならす。"""
    return re.sub(r"[\s　・「」『』（）()【】\[\]、。,:：!！?？….\-〜～]+", "", text)


def _title_fragments(title: str) -> list[str]:
    """台本本文内で照合しやすい記事タイトル断片を作る。"""
    parts = re.split(r"[、。,:：|｜／/「」『』（）()【】\[\]\-〜～…\s　]+", title)
    fragments: list[str] = []
    for part in parts:
        cleaned = _clean_fragment(part)
        if len(cleaned) >= 5 and cleaned not in fragments:
            fragments.append(cleaned)
    cleaned_title = _clean_fragment(title)
    if len(cleaned_title) >= 8:
        fragments.append(cleaned_title[:18])
    return fragments


def _article_is_covered(article: dict, body_text: str) -> bool:
    """1本の記事が本文解説側で扱われているかをゆるく判定する。"""
    normalized_body = _clean_fragment(body_text)
    for fragment in _title_fragments(article.get("title", "")):
        if fragment in normalized_body:
            return True
        if SequenceMatcher(None, fragment, normalized_body).quick_ratio() > 0.92:
            return True
    return False


def _news_body_lines(script: list[tuple[str, str]]) -> list[str]:
    """ラインナップではなく、各ニュースの解説に当たる本文部分を抜き出す。"""
    texts = [line for _, line in script]
    start_markers = (
        "まず一つ目のニュース",
        "一つ目のニュース",
        "最初のニュース",
        "まず一つ目",
        "1つ目のニュース",
    )
    end_markers = (
        "さて、今週のニュース",
        "今週のニュースを振り返",
        "今週の判断",
        "今週やること",
        "それではまた",
        "本日もそろそろ",
        "クロージング",
    )

    start = next((i for i, line in enumerate(texts) if any(m in line for m in start_markers)), None)
    if start is None:
        return []

    end = len(texts)
    for i in range(len(texts) - 1, start, -1):
        if any(m in texts[i] for m in end_markers):
            end = i
    return texts[start:end]


def has_substantial_news_body(script: list[tuple[str, str]], articles: list[dict], slot: str) -> bool:
    """オープニング・エンディングだけの放送をRSS掲載前に止める。"""
    body_lines = _news_body_lines(script)
    body_text = "\n".join(body_lines)
    min_body_lines = 30
    min_body_chars = 3000

    if len(body_lines) < min_body_lines or len(body_text) < min_body_chars:
        logging.getLogger(__name__).error(
            "ニュース本文が不足: %d行 / %d文字",
            len(body_lines),
            len(body_text),
        )
        return False

    covered = sum(1 for article in articles if _article_is_covered(article, body_text))
    required = min(3, len(articles))
    if covered < required:
        logging.getLogger(__name__).error(
            "ニュース本文で扱われた記事数が不足: %d/%d",
            covered,
            required,
        )
        return False

    return True


def main():
    no_deploy = "--no-deploy" in sys.argv
    publish_now = "--publish-now" in sys.argv
    slot = parse_slot(sys.argv)
    slot_config = EPISODE_SLOTS[slot]

    setup_logging()
    logger = logging.getLogger(__name__)

    now = datetime.now(JST)
    today = now.strftime("%Y%m%d")
    episode_filename = f"episode_{today}_{slot_config['filename_suffix']}.mp3"
    exclude_titles: list[str] = []

    if slot == "evening":
        exclude_titles = load_used_article_titles(today, EPISODE_SLOTS["morning"]["filename_suffix"])
        if exclude_titles:
            logger.info("朝刊で扱ったニュースを夕刊から除外: %d件", len(exclude_titles))
        else:
            logger.info("朝刊のニュース一覧が見つからないため、夕刊の既出除外はスキップ")

    # 重複実行防止
    if (AUDIO_DIR / episode_filename).exists():
        logger.info("今日の%sエピソードは既に生成済みです", slot_config["label"])
        return

    # Step 1: ニュース収集
    logger.info("=" * 50)
    logger.info("Step 1: ニュース収集")
    articles = collect_news(exclude_titles=exclude_titles)
    if not articles:
        logger.warning("ニュースが見つかりませんでした。終了します。")
        return
    logger.info(f"{len(articles)}件のニュースを取得")

    # Step 2: 台本・タイトル・概要・SNS下書き生成
    logger.info("=" * 50)
    logger.info("Step 2: 台本・タイトル・概要欄・SNS下書き生成")
    script, title, summary, sns_draft = generate_script(articles, show_name=slot_config["show_name"], slot=slot)

    # 監査AIは修正出力で台本本文を欠落させることがあるため、本線から外す。
    # 公開前の自動安全弁として、短すぎる台本だけを停止する。
    status = "A"
    audit_log = ""

    if not is_script_plausible(script, slot):
        logger.error(
            "台本が短すぎるため音声生成を中断します: %dセリフ / %d文字",
            len(script),
            script_text_length(script),
        )
        save_script(
            script,
            today,
            slot_config["label"],
            slot_config["filename_suffix"],
            articles,
            title,
            summary,
            sns_draft,
            audit_log,
        )
        sys.exit(1)

    if not has_substantial_news_body(script, articles, slot):
        logger.error("ニュース本文が不足しているため音声生成を中断します")
        save_script(
            script,
            today,
            slot_config["label"],
            slot_config["filename_suffix"],
            articles,
            title,
            summary,
            sns_draft,
            audit_log,
        )
        sys.exit(1)

    # 台本パッケージを保存（AまたはB判定）
    save_script(
        script,
        today,
        slot_config["label"],
        slot_config["filename_suffix"],
        articles,
        title,
        summary,
        sns_draft,
        audit_log,
    )
    logger.info(f"台本: {len(script)}セリフ")

    # Step 3: 音声生成
    logger.info("=" * 50)
    logger.info("Step 3: 音声生成")
    audio_path, duration = generate_audio(script, episode_filename)
    logger.info(f"音声: {duration:.1f}秒")
    if not is_audio_duration_plausible(duration, slot):
        logger.error(
            "音声が短すぎるためRSS更新を中断します: %.1f秒 (%s)",
            duration,
            audio_path,
        )
        sys.exit(1)
    if not is_audio_duration_consistent(script, duration):
        logger.error("音声本文が欠落している可能性があるためRSS更新を中断します")
        sys.exit(1)

    # Step 4: RSS更新
    logger.info("=" * 50)
    logger.info("Step 4: RSS更新")
    update_rss(
        episode_filename,
        title,
        summary,
        duration,
        published_at=now,
        allow_early_evening=publish_now,
    )

    # Step 5: デプロイ（--no-deployの場合はスキップ）
    if no_deploy:
        logger.info("デプロイはスキップ（--no-deploy）")
    else:
        logger.info("=" * 50)
        logger.info("Step 5: GitHub Pagesへデプロイ")
        try:
            from deploy import deploy
            deploy()
        except Exception as e:
            logger.error(f"デプロイ失敗（音声生成は成功）: {e}")
            logger.info("手動でデプロイしてください")

    # 正常完了（AまたはB判定）時にメールを送信
    send_email_via_gas(title, status, script, summary, sns_draft, audit_log)
    logger.info("=" * 50)
    logging.getLogger(__name__).info("完了！")


if __name__ == "__main__":
    main()
