"""AI News Podcast - メインスクリプト

毎日自動でAIニュースを収集し、Podcast音声を生成してRSS配信する。
"""
import os
import re
import sys
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from config import AUDIO_DIR, SCRIPTS_DIR, LOG_DIR
from news_collector import collect_news
from script_generator import generate_script
from tts_generator import generate_audio
from rss_generator import update_rss

JST = ZoneInfo("Asia/Tokyo")

EPISODE_SLOTS = {
    "morning": {
        "label": "朝刊",
        "show_name": "AI朝刊",
        "filename_suffix": "morning",
    },
    "evening": {
        "label": "夕刊",
        "show_name": "AI夕刊",
        "filename_suffix": "evening",
    },
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


def save_script(
    script: list[tuple[str, str]],
    date_str: str,
    episode_label: str,
    filename_suffix: str,
    articles: list[dict] | None = None,
):
    """台本をテキストファイルとして保存。

    あとから「何が読み上げられたか」を確認しやすいよう、日付フォルダ
    （scripts/<YYYYMMDD>/）の中にテキストファイルとして残す。
    冒頭に、その日のニュース一覧（タイトル・ソース）も記録する。
    """
    day_dir = SCRIPTS_DIR / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"script_{date_str}_{filename_suffix}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"AI{episode_label} 台本  {date_str}\n")
        f.write("=" * 40 + "\n\n")
        if articles:
            f.write("【今日のニュース】\n")
            for i, a in enumerate(articles, 1):
                f.write(f"{i}. {a.get('title', '')}（{a.get('source', '')}）\n")
            f.write("\n" + "=" * 40 + "\n\n")
        f.write("【台本】\n")
        for speaker, line in script:
            f.write(f"{speaker}: {line}\n")
    logging.getLogger(__name__).info(f"台本保存: {path}")


def parse_slot(argv: list[str]) -> str:
    """--slot morning/evening を読み取る。未指定時は朝刊扱い。"""
    if "--slot" not in argv:
        return "morning"
    idx = argv.index("--slot")
    if idx + 1 >= len(argv):
        raise ValueError("--slot requires morning or evening")
    slot = argv[idx + 1]
    if slot not in EPISODE_SLOTS:
        raise ValueError(f"Unknown slot: {slot}. Use morning or evening.")
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
        if stripped == "【今日のニュース】":
            in_news_section = True
            continue
        if in_news_section and stripped.startswith("===="):
            break
        if not in_news_section:
            continue
        match = re.match(r"^\d+\.\s*(.+?)（.+?）$", stripped)
        if match:
            titles.append(match.group(1))
    return titles


def main():
    no_deploy = "--no-deploy" in sys.argv
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

    # Step 2: 台本生成
    logger.info("=" * 50)
    logger.info("Step 2: 台本生成")
    script = generate_script(articles, show_name=slot_config["show_name"])
    save_script(script, today, slot_config["label"], slot_config["filename_suffix"], articles)
    logger.info(f"台本: {len(script)}セリフ")

    # Step 3: 音声生成
    logger.info("=" * 50)
    logger.info("Step 3: 音声生成")
    audio_path, duration = generate_audio(script, episode_filename)
    logger.info(f"音声: {duration:.1f}秒")

    # Step 4: RSS更新
    logger.info("=" * 50)
    logger.info("Step 4: RSS更新")
    update_rss(episode_filename, articles, duration, slot_config["label"], published_at=now)

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

    logger.info("=" * 50)
    logger.info("完了！")


if __name__ == "__main__":
    main()
