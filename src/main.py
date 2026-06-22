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
from rss_generator import update_rss
from tts_generator import generate_audio
from auditor import audit_content

JST = ZoneInfo("Asia/Tokyo")

EPISODE_SLOTS = {
    "morning": {
        "label": "朝刊",
        "show_name": "AIニュースデイリー 朝刊",
        "filename_suffix": "morning",
    },
    "evening": {
        "label": "夕刊",
        "show_name": "AIニュースデイリー 夕刊",
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
        f.write(f"AIニュースデイリー {episode_label} 台本パッケージ  {date_str}\n")
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

    # Step 2: 台本・タイトル・概要・SNS下書き生成
    logger.info("=" * 50)
    logger.info("Step 2: 台本・タイトル・概要欄・SNS下書き生成")
    script, title, summary, sns_draft = generate_script(articles, show_name=slot_config["show_name"], slot=slot)

    # Step 2.5: 監査（ファクトチェック）
    logger.info("=" * 50)
    logger.info("Step 2.5: 監査AIによるファクトチェック")
    audit_result = audit_content(script, title, summary, sns_draft, articles)

    status = audit_result["status"]
    audit_log = audit_result["audit_log"]
    logger.info(f"監査ステータス: {status}")

    if status == "C":
        # 人間確認が必要な場合：下書き等は保存するが、公開処理に進まずにエラー終了
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
        # GAS経由で警告メール送信
        send_email_via_gas(title, status, script, summary, sns_draft, audit_log)
        logger.error("監査AIが『C：公開前に人間確認が必要』と判定しました。自動公開（デプロイ）を中断します。")
        logger.error(f"監査ログ:\n{audit_log}")
        sys.exit(1)

    elif status == "B":
        # 軽微な修正あり：監査AIが修正したテキストを採用（空チェック・サボり防止の安全弁付き）
        logger.info("監査AIによる自動修正（ステータスB）を適用します。")
        if audit_result["title"] and len(audit_result["title"].strip()) > 5:
            title = audit_result["title"].strip()
        if audit_result["summary"] and len(audit_result["summary"].strip()) > 10:
            summary = audit_result["summary"].strip()

        # 修正された台本が正常（5行以上）な場合のみ適用。不完全なら元の台本を維持
        if audit_result["script"] and len(audit_result["script"]) > 5:
            script = audit_result["script"]
        else:
            logger.warning("監査AIによる修正台本が不完全なため、元の台本を維持します。")

        # 修正されたSNS下書きが正常（50文字以上）な場合のみ適用。不完全なら元のSNS下書きを維持
        if audit_result["sns_draft"] and len(audit_result["sns_draft"].strip()) > 50:
            sns_draft = audit_result["sns_draft"].strip()
        else:
            logger.warning("監査AIによる修正SNS下書きが不完全なため、元のSNS下書きを維持します。")

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

    # Step 4: RSS更新
    logger.info("=" * 50)
    logger.info("Step 4: RSS更新")
    update_rss(episode_filename, title, summary, duration, published_at=now)

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
