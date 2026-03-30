"""Gemini APIで2人掛け合いの台本を生成"""
import re
import logging
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MAX_SCRIPT_CHARS, MC_A, MC_B, PODCAST_TITLE

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """You are a scriptwriter for the podcast show "{show_name}".
Based on the news below, write a conversational script between two hosts: {mc_a} and {mc_b}.

【IMPORTANT: Always use these exact host names】
- Main host: {mc_a} (use this name every time. Never change it.)
- Co-host: {mc_b} (use this name every time. Never change it.)

【Rules】
- Every line MUST start with "{mc_a}:" or "{mc_b}:" (no space before the colon)
- Do NOT include any stage directions, annotations, or blank lines
- Start with a show name call (e.g. "Welcome to {show_name}!")
- Structure: Show intro → Opening greeting → News discussion → Wrap-up → Closing ("See you tomorrow on {show_name}!")
- Total length: 3000-{max_chars} characters (discuss each news item thoroughly)
- Explain technical terms in simple language
- Include natural reactions, follow-up questions, and opinions
- Friendly, energetic radio show tone
- Prioritize practical topics that make listeners think "I want to try this!"
- Cover AI tool updates in detail (what's new, how it's useful, who benefits)
- For industry moves (funding, partnerships, regulations), always mention impact on listeners

【Hosts】
- {mc_a}: Main host. Calm, knowledgeable tone. Leads the show and introduces news
- {mc_b}: Co-host. Curious and enthusiastic. Asks questions from the listener's perspective

【Today's News】
{{news_text}}

Output ONLY lines starting with "{mc_a}:" or "{mc_b}:".
"""


def format_news(articles: list[dict]) -> str:
    """ニュースリストを台本生成用テキストに整形"""
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(f"News {i}: {a['title']}\nSource: {a['source']}\nSummary: {a['summary']}\n")
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
        {"title": "OpenAI launches new model", "source": "TechCrunch", "summary": "OpenAI announced a new GPT model."},
        {"title": "Google DeepMind releases AlphaFold 4", "source": "Nature", "summary": "Protein structure prediction accuracy improved significantly."},
    ]
    script = generate_script(test_articles)
    for speaker, line in script:
        print(f"{speaker}: {line}")
