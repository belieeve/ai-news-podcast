"""Gemini APIで2人掛け合いの台本を生成"""
import re
import logging
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MAX_SCRIPT_CHARS, MC_A, MC_B, PODCAST_TITLE

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """あなたはポッドキャスト番組「{show_name}」の構成作家です。
以下の5本のニュースをもとに、2人のMC「{mc_a}」と「{mc_b}」の掛け合い台本を書いてください。

【最重要：放送時間は10分以内に必ず収める】
- 全体の文字数: 2200〜{max_chars}文字以内（厳守。超過したら短くする）
- 各ニュースの解説: 1本あたり300〜400文字以内
- オープニング: 番組名コール+短い挨拶のみ（合計2行まで）。天気・近況・世間話・前置きは絶対に入れない
- エンディング: 締めの一言のみ（2行まで）
- リスナーは雑談で離脱するため、本題（ニュース解説）に最速で入ること

【MC名（変更禁止）】
- メインMC: {mc_a}
- サブMC: {mc_b}

【出力ルール】
- 全行は必ず「{mc_a}:」または「{mc_b}:」で始める（コロンの前にスペース不可）
- 演出指示・注釈・空行は入れない
- 構成: ① 番組名コール（1行） ② 短い挨拶（1行） ③ ニュース5本の解説（各2〜4往復） ④ エンディング（1〜2行）
- 専門用語はやさしい言葉に言い換える
- AIツールの新機能は「何が新しい・どう便利・誰が得する」を簡潔に
- 業界の動き（資金調達・提携・規制）はリスナーへの影響まで触れる
- 親しみやすく明るいラジオ番組のトーン

【MCのキャラクター】
- {mc_a}: メインMC。落ち着いた知的なトーン。進行とニュース紹介
- {mc_b}: サブMC。好奇心旺盛で前のめり。リスナー目線で短く質問

【今日のニュース】
{{news_text}}

出力は「{mc_a}:」または「{mc_b}:」で始まる行のみにしてください。
"""


def format_news(articles: list[dict]) -> str:
    """ニュースリストを台本生成用テキストに整形"""
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(f"ニュース{i}: {a['title']}\nソース: {a['source']}\n要約: {a['summary']}\n")
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
    logger.info(f"Script generated ({len(raw_text)} chars)")

    parsed = parse_script(raw_text)
    if not parsed:
        raise ValueError("Failed to parse script")

    logger.info(f"Lines: {len(parsed)}")
    return parsed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_articles = [
        {"title": "OpenAIが新モデルを発表", "source": "TechCrunch Japan", "summary": "OpenAIが新しいGPTモデルを発表しました。"},
        {"title": "Google DeepMindがAlphaFold 4を公開", "source": "Nature", "summary": "タンパク質構造予測の精度が大幅に向上しました。"},
    ]
    script = generate_script(test_articles)
    for speaker, line in script:
        print(f"{speaker}: {line}")
