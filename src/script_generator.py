"""Gemini APIで2人掛け合いの台本、タイトル、概要欄、SNS下書きを生成"""
import re
import logging
from datetime import datetime
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MC_A, MC_B, PODCAST_TITLE

logger = logging.getLogger(__name__)

# プロンプトテンプレート
PROMPT_TEMPLATE = """あなたはポッドキャスト番組「{show_name}」の構成作家兼パーソナリティです。
海外のAIニュースを親しみやすい雑談形式で紹介し、リスナーが「AIって面白い！自分も使ってみたい」とワクワクできるような、エンタメ感のある掛け合いラジオ番組を作ります。

【番組コンセプトとルール】
1. 目的：「難しそうな海外AIニュースを、リスナーが楽しみながら自然とキャッチアップし、仕事や日常でのAI活用に興味を持てるようになること」
2. リスナー像：
   - AIを仕事に使いたい会社員。
   - AIで副業を始めたい個人。
   - AIの流れに遅れたくない中小企業の経営者。
   - 海外ニュースを追う時間はないけれど、重要な変化は知っておきたい人。
3. トーン：真面目なニュース番組ではなく、親しみやすいラジオの雰囲気。テンポが良く、フランクで明るい対話。2人が楽しそうに会話している様子が伝わり、リスナーが横で一緒におしゃべりを聞いているような空気感を重視してください。
4. 専門用語：できるだけ避け、使う場合は必ず一言でわかりやすく説明すること。
5. 煽り表現・断定表現の禁止：以下の表現は絶対に使用しないでください。
   「全面的に安全」「完全に解決」「終焉」「禁止」「確定」「仕事がなくなる」「必ず」「絶対に」「AI三国志」「完全に安全」「ChatGPT一強の終焉」「時代遅れ」
   「すごい」「革命的」を乱発せず、リスナーが落ち着いて判断できるように説明してください。
6. 事実と解釈の分離：
   - ニュースの事実に加え、「これを使って何ができそう？」「もし自分が使ったらどうなる？」といった、2人の主観的で楽しい妄想やユーモアのあるリアクションを多く交えて掛け合いをさせてください。
   - 台本の中でニュースの出典元（ソース）をわざわざ紹介する必要はありません。
7. 構成：
   ① 冒頭の固定メッセージ（毎回自然に言い換える）
      「この番組は、海外AIニュースを日本語で短く整理し、日本の個人・副業・中小企業がどう使えるかまで解説する番組です。」
   ② 今日のニュース概要（5本）
   ③ 各ニュースの解説（何が起きたか、なぜ重要か、日本人にどう関係するか）
   ④ エンディング挨拶

{slot_instruction}

【MC名（変更禁止）】
- メインMC（明るく話し上手、知的好奇心を刺激する進行役）: {mc_a}
- サブMC（ノリが良くリアクション豊富、素朴な疑問や楽しいツッコミを入れる相棒）: {mc_b}

【今日のニュース】
{news_text}

【出力フォーマット】
以下の区切り線を正確に使用し、それぞれの内容を出力してください。プレースホルダや余計な解説、マークダウンの外側にテキストを書かないでください。

=== TITLE ===
（スマホ画面で意味が伝わる30〜45文字程度のエピソードタイトル。固有名詞、何が変わるか、誰に役立つかを明確に）

=== SUMMARY ===
（Spotify概要欄用テキスト。今日扱ったニュース一覧と一言要約、Spotifyフォローのお願い、最後の締めを含む）

=== SCRIPT ===
（掛け合い台本。全行は必ず「{mc_a}:」または「{mc_b}:」で始める。演出指示・注釈・空行は入れない。質問文は必ず「か」で終える。最終行に <<END>> とだけ書く）

=== SNS_DRAFT ===
【X投稿文】（番組紹介・ニュース要点など3本）
【Threads投稿文】（個人のキャリアや生活に密着した柔らかいトーンで長めのテキスト3本）
【ショート動画用30秒台本】（ハルトとアヤカの短い掛け合いかナレーションで、インパクトを伝えるもの1本）
"""


def format_news(articles: list[dict]) -> str:
    """ニュースリストを台本生成用テキストに整形"""
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(
            f"ニュース{i}: {a['title']}\nソース: {a.get('source', '不明')}\nURL: {a.get('url', 'なし')}\n要約: {a.get('summary', a.get('description', 'なし'))}\n"
        )
    return "\n".join(parts)


def parse_sections(text: str) -> tuple[str, str, str, str]:
    """Geminiの出力からTITLE, SUMMARY, SCRIPT, SNS_DRAFTセクションを抽出"""
    title = ""
    summary = ""
    script_raw = ""
    sns_draft = ""

    sections = re.split(r"===\s*(TITLE|SUMMARY|SCRIPT|SNS_DRAFT)\s*===", text)

    for i in range(1, len(sections), 2):
        sec_name = sections[i]
        if i + 1 < len(sections):
            sec_content = sections[i + 1].strip()
            if sec_name == "TITLE":
                title = sec_content
            elif sec_name == "SUMMARY":
                summary = sec_content
            elif sec_name == "SCRIPT":
                script_raw = sec_content
            elif sec_name == "SNS_DRAFT":
                sns_draft = sec_content

    return title, summary, script_raw, sns_draft


def parse_script(text: str) -> list[tuple[str, str]]:
    """台本テキストをパースして(話者, セリフ)のリストを返す"""
    lines: list[tuple[str, str]] = []
    for raw in text.strip().split("\n"):
        line = raw.strip()
        if not line:
            continue
        if "<<END>>" in line:
            continue
        match = re.match(rf"^({MC_A}|{MC_B}):(.+)$", line)
        if match:
            speaker = match.group(1)
            content = match.group(2).strip()
            if content:
                lines.append((speaker, content))
    return lines





def generate_script(
    articles: list[dict],
    show_name: str = PODCAST_TITLE,
    slot: str = "morning",
) -> tuple[list[tuple[str, str]], str, str, str]:
    """ニュースから台本、タイトル、概要欄、SNS下書きを生成"""
    client = genai.Client(api_key=GEMINI_API_KEY)

    # スロット別の指示
    if slot == "evening":
        slot_instruction = f"""【スロット：夕刊（evening）】
- 夕方の放送用です。最初の挨拶は必ず「こんばんは」としてください。
- ニュースは必ず「ちょうど5本」紹介すること（4本以下も6本以上も禁止）。
- 5本すべてについて、何が起きたか、なぜ重要か、日本の個人・副業・中小企業にどう関係するかを短く触れること。
- 完成音声が6分〜8分に収まる長さにする。
- 台本全体は日本語で約3,600〜4,600文字を目安にし、MCセリフ行だけで35〜45行程度にする。
- エンディング例：
    {MC_A}: それではまた明日、同じ時間にお会いしましょう。
    {MC_B}: お相手は {MC_B} と、
    {MC_A}: {MC_A} でした。良い夜を！
"""
    else:
        slot_instruction = f"""【スロット：朝刊（morning）】
- 朝の放送用です。最初の挨拶は必ず「おはようございます」としてください。
- ニュースは必ず「ちょうど5本」紹介すること（4本以下も6本以上も禁止）。
- 完成音声が9分30秒〜10分30秒に収まる長さにする。
- 台本全体は日本語で約5,600〜6,400文字を目安にし、MCセリフ行だけで55〜70行程度にする。
- エンディング例：
    {MC_A}: それではまた明日、同じ時間にお会いしましょう。
    {MC_B}: お相手は {MC_B} と、
    {MC_A}: {MC_A} でした。良い一日を！
"""

    news_text = format_news(articles)
    prompt = PROMPT_TEMPLATE.format(
        show_name=show_name,
        mc_a=MC_A,
        mc_b=MC_B,
        slot_instruction=slot_instruction,
        news_text=news_text,
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=12000,
        ),
    )

    raw_text = response.text
    logger.info(f"Generated text length: {len(raw_text)}")

    title, summary, script_raw, sns_draft = parse_sections(raw_text)

    # パースに失敗した部分のフォールバック
    if not title:
        today_str = datetime.now().strftime("%Y%m%d")
        title = f"AIニュース {today_str} {slot}"
        logger.warning("Failed to parse TITLE. Use fallback.")
    if not summary:
        summary_lines = [f"• {a['title']}" for a in articles]
        summary = "【今日の話題】\n" + "\n".join(summary_lines)
        logger.warning("Failed to parse SUMMARY. Use fallback.")

    parsed = parse_script(script_raw)
    if not parsed:
        # script_rawがうまくパースできなかった場合の保険
        parsed = parse_script(raw_text)
        if not parsed:
            raise ValueError("Failed to parse script lines")

    logger.info(f"Script lines: {len(parsed)}")
    return parsed, title, summary, sns_draft
