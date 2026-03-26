"""AI News Podcast - メインスクリプト

毎日自動でAIニュースを収集し、Podcast音声を生成してRSS配信する。
"""
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent))

from config import AUDIO_DIR, SCRIPTS_DIR, LOG_DIR
from news_collector import collect_news
from script_generator import generate_script
from tts_generator import generate_audio
from rss_generator import update_rss


def setup_logging():
    """ロギング設定"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    log_file = LOG_DIR / f"podcast_{today}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def save_script(script: list[tuple[str, str]], date_str: str):
    """台本をテキストファイルとして保存"""
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = SCRIPTS_DIR / f"script_{date_str}.txt"
    with open(path, "w", encoding="utf-8") as f:
        for speaker, line in script:
            f.write(f"{speaker}: {line}\n")
    logging.getLogger(__name__).info(f"台本保存: {path}")


def main():
    no_deploy = "--no-deploy" in sys.argv

    setup_logging()
    logger = logging.getLogger(__name__)

    today = datetime.now().strftime("%Y%m%d")
    episode_filename = f"episode_{today}.mp3"

    # 重複実行防止
    if (AUDIO_DIR / episode_filename).exists():
        logger.info("今日のエピソードは既に生成済みです")
        return

    # Step 1: ニュース収集
    logger.info("=" * 50)
    logger.info("Step 1: ニュース収集")
    articles = collect_news()
    if not articles:
        logger.warning("ニュースが見つかりませんでした。終了します。")
        return
    logger.info(f"{len(articles)}件のニュースを取得")

    # Step 2: 台本生成
    logger.info("=" * 50)
    logger.info("Step 2: 台本生成")
    script = generate_script(articles)
    save_script(script, today)
    logger.info(f"台本: {len(script)}セリフ")

    # Step 3: 音声生成
    logger.info("=" * 50)
    logger.info("Step 3: 音声生成")
    audio_path, duration = generate_audio(script, episode_filename)
    logger.info(f"音声: {duration:.1f}秒")

    # Step 4: RSS更新
    logger.info("=" * 50)
    logger.info("Step 4: RSS更新")
    update_rss(episode_filename, articles, duration)

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
