"""Gemini APIで2人掛け合いの台本を生成"""
import re
import logging
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MAX_SCRIPT_CHARS, MC_A, MC_B, PODCAST_TITLE

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """あなたはPodcast番組「{show_name}」の台本作家です。
以下のニュースを元に、2人のパーソナリティ（{mc_a}と{mc_b}）による掛け合い形式の台本を作成してください。

【重要：MC名は必ず以下の名前を使うこと】
- メインMC: {mc_a}（毎回この名前を使うこと。変更禁止）
- サブMC: {mc_b}（毎回この名前を使うこと。変更禁止）

【ルール】
- 各発言は必ず「{mc_a}:」または「{mc_b}:」で始めること（スペースなし）
- 「{mc_a}:」「{mc_b}:」以外の行（ト書き・注釈・空行）は書かないこと
- 冒頭は必ず番組名コールから始める（例: 「{show_name}、スタートです！」）
- 構成: 番組名コール → オープニング挨拶 → 各ニュース紹介・感想 → まとめ → エンディング（「また明日の{show_name}でお会いしましょう！」）
- 全体で3000〜{max_chars}文字（短すぎないこと。各ニュースについてしっかり会話する）
- 専門用語はわかりやすく説明を加える
- 相槌や感想を自然に入れて会話らしくする
- ラジオ番組のような明るく親しみやすいトーンで
- リスナーが「自分も使ってみたい！」と思えるような実用的な話題を優先する
- AIツールの新機能・アップデート情報は特に詳しく紹介する（何ができるようになったか、どう便利かを具体的に）
- 業界の大きな動き（資金調達、提携、規制）も取り上げるが、リスナーへの影響を必ず添える

【パーソナリティ】
- {mc_a}: メインMC。落ち着いた口調でニュースを紹介する。番組の進行役
- {mc_b}: サブMC。好奇心旺盛で質問やリアクションを入れる。リスナー目線で疑問を投げかける

【今日のニュース】
{{news_text}}

台本を出力してください。「{mc_a}:」「{mc_b}:」で始まる行のみで構成してください。
"""


def format_news(articles: list[dict]) -> str:
    """ニュースリストを台本生成用テキストに整形"""
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(f"ニュース{i}: {a['title']}\n出典: {a['source']}\n概要: {a['summary']}\n")
    return "\n".join(parts)


def parse_script(text: str) -> list[tuple[str, str]]:
    """台本テキストをパースして(話者, セリフ)のリストを返す"""
    lines = []
    for line in text.strip().split("\n"):
        line = line.strip()
        match = re.match(rf'^({MC_A}|{MC_B}):(.+)$', line)
        if match:
            speaker = match.group(1)
            content = match.group(2).strip()
            if content:
                lines.append((speaker, content))
    return lines


def generate_script(articles: list[dict]) -> list[tuple[str, str]]:
    """ニュースから台本を生成"""
    client = genai.Client(api_key=GEMINI_API_KEY)

    news_text = format_news(articles)
    # MC名と番組名を先に埋め込み、news_textは後から
    prompt = PROMPT_TEMPLATE.format(
        show_name=PODCAST_TITLE,
        mc_a=MC_A,
        mc_b=MC_B,
        max_chars=MAX_SCRIPT_CHARS,
    ).replace("{news_text}", news_text)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.8,
            max_output_tokens=8192,
        ),
    )

    raw_text = response.text
    logger.info(f"台本生成完了（{len(raw_text)}文字）")

    parsed = parse_script(raw_text)
    if not parsed:
        raise ValueError("台本のパースに失敗しました")

    logger.info(f"セリフ数: {len(parsed)}")
    return parsed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # テスト用
    test_articles = [
        {"title": "OpenAIが新モデルを発表", "source": "TechCrunch", "summary": "OpenAIは新しいGPTモデルを発表した。"},
        {"title": "Google DeepMindがAlphaFold 4を公開", "source": "Nature", "summary": "タンパク質構造予測の精度が大幅に向上。"},
    ]
    script = generate_script(test_articles)
    for speaker, line in script:
        print(f"{speaker}: {line}")
