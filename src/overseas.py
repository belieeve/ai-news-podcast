"""海外Podcast朝刊の「今日の1本」を読み込んで台本プロンプト用のテキストにする。

朝刊（Mac mini側で毎朝生成）が overseas/YYYY-MM-DD.json を置いてくれる前提。
ファイルが無い日はNoneを返し、番組は従来どおりの構成で作られる（コーナーが消えるだけ）。
"""

import json
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# src/ の1つ上（リポジトリ直下）の overseas/
OVERSEAS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "overseas")


def load_overseas(date_str: str | None = None) -> dict | None:
    """当日分の海外Podcast要約を読む。無ければNone。"""
    if date_str is None:
        date_str = datetime.now(JST).strftime("%Y-%m-%d")
    path = os.path.join(OVERSEAS_DIR, f"{date_str}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    # 最低限の項目が揃っていなければ使わない（欠けたまま台本に入れると事故るため）
    if not data.get("title") or not data.get("summary"):
        return None
    return data


def format_overseas(data: dict) -> str:
    """プロンプトに差し込む素材テキストを作る"""
    def bullets(key: str) -> str:
        items = data.get(key) or []
        return "\n".join(f"  ・{s}" for s in items) if items else "  ・（なし）"

    return f"""【海外ポッドキャストの深掘り素材（今日のコーナー用）】
タイトル: {data['title']}
番組名: {data.get('show', '（不明）')}
元動画URL: {data.get('url', '（なし）')}

3行まとめ:
{bullets('summary')}

要点:
{bullets('points')}

今日からできること:
{bullets('actions')}
"""


# 台本の構成に差し込むコーナーの指示
CORNER_INSTRUCTION = """  5.5 海外ポッドキャストのコーナー: 【海外ポッドキャストの深掘り素材】として渡した1本だけを、2人が3〜4分ぶんしゃべる。
      「うちら毎朝、海外のポッドキャストも聴いてるんだけどさ」のように日常会話の振りから入り、番組名と誰の話かを必ず言う。
      素材の「3行まとめ」「要点」から2〜4個を選んで会話でかみ砕き、最後に「今日からできること」を1つだけ、リスナーが今日試せる形で渡す。
      ★渡された素材に書かれていないことは足さない（推測で内容を補わない）。原文の朗読ではなく、2人の言葉での紹介にする。"""

CORNER_CHECK = """- 海外ポッドキャストのコーナーで、番組名と誰の話かを言っているか。素材に無いことを足していないか。"""
