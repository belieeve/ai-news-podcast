"""Gemini APIで2人掛け合いの台本、タイトル、概要欄、SNS下書きを生成"""
import re
import logging
from datetime import datetime
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MC_A, MC_B, PODCAST_TITLE

logger = logging.getLogger(__name__)

# プロンプトテンプレート
PROMPT_TEMPLATE = """あなたはポッドキャスト番組「{show_name}」の構成作家兼マーケターです。
海外のAIニュースを日本語で紹介し、日本の会社員・副業者・中小企業経営者が「明日からどう使えるか」という実践的な視点でお届けする配信コンテンツを作ります。

【番組コンセプトとルール】
1. 目的：「忙しい日本人が、海外AIニュースを10分で理解し、仕事・副業・日常に活かせるようになること」
2. リスナー像：
   - AIを仕事に使いたい会社員。
   - AIで副業を始めたい個人。
   - AIの流れに遅れたくない中小企業の経営者。
   - 海外ニュースを追う時間はないけれど、重要な変化は知っておきたい人。
3. トーン：わかりやすく、やさしく、少し前向き。専門家ぶりすぎず、軽すぎず。
4. 専門用語：できるだけ避け、使う場合は必ず一言でわかりやすく説明すること。
5. 煽り表現・断定表現の禁止：以下の表現は絶対に使用しないでください。
   「全面的に安全」「完全に解決」「終焉」「禁止」「確定」「仕事がなくなる」「必ず」「絶対に」「AI三国志」「完全に安全」「ChatGPT一強の終焉」「時代遅れ」
   「すごい」「革命的」を乱発せず、リスナーが落ち着いて判断し行動できるように説明してください。
6. 事実と解釈の分離：
   - 「ニュースの事実（報道されていること）」と「日本の個人や中小企業への示唆（解釈）」を明確に分けて説明してください。
   - ニュースには必ず一次情報や信頼できるソース（出典元）を添えてください。
7. 構成：
   ① 冒頭の固定メッセージ（毎回自然に言い換える）
      「この番組は、海外AIニュースを日本語で短く整理し、日本の個人・副業・中小企業がどう使えるかまで解説する番組です。」
   ② 今日のニュース概要（朝刊のみ）
   ③ 各ニュースの解説（何が起きたか、なぜ重要か、日本人にどう関係するか、明日からできる具体的な行動）
   ④ 今日の一歩（リスナーがすぐできる小さく具体的な行動を1つ提案）
   ⑤ ニュースレター登録への案内（「今日紹介したニュースのリンクと、仕事での使い方はニュースレターにもまとめています。概要欄から無料で登録できます」のような自然な誘導）
   ⑥ エンディング挨拶

{slot_instruction}

【MC名（変更禁止）】
- メインMC（落ち着いた知的なトーン）: {mc_a}
- サブMC（好奇心旺盛で前のめり、リスナー目線で短く質問）: {mc_b}

【今日のニュース】
{news_text}

【出力フォーマット】
以下の区切り線を正確に使用し、それぞれの内容を出力してください。プレースホルダや余計な解説、マークダウンの外側にテキストを書かないでください。

=== TITLE ===
（スマホ画面で意味が伝わる30〜45文字程度のエピソードタイトル。固有名詞、何が変わるか、誰に役立つかを明確に）

=== SUMMARY ===
（Spotify概要欄用テキスト。今日扱ったニュース一覧と一言要約、今日の一歩、ニュースレター登録リンクプレースホルダ、Spotifyフォローのお願い、最後の締めを含む）

=== SCRIPT ===
（掛け合い台本。全行は必ず「{mc_a}:」または「{mc_b}:」で始める。演出指示・注釈・空行は入れない。質問文は必ず「か」で終える。最終行に <<END>> とだけ書く）

=== SNS_DRAFT ===
【ニュースレター用文章】（今日のニュースまとめ、日本での使い方、今日試すこと、ニュース/ツールリンクプレースホルダ、次回のポッドキャストを聞く理由を含む、無料版要約・活用メモ形式）
【X投稿文】（番組紹介・ニュース要点・行動提案など3本）
【Threads投稿文】（個人のキャリアや生活に密着した柔らかいトーンで長めのテキスト3本）
【ショート動画用30秒台本】（ハルトとアヤカの短い掛け合いかナレーションで、インパクトと今日の一歩を伝えるもの1本）
"""

FALLBACK_ENDING = [
    ("{mc_a}", "さて、本日もそろそろお別れの時間です。"),
    ("{mc_b}", "明日も気になるAIニュース、お届けしますね。"),
    ("{mc_a}", "それではまた明日、同じ時間にお会いしましょう。"),
    ("{mc_b}", "お相手は {mc_b} と、"),
    ("{mc_a}", "{mc_a} でした。良い一日を！"),
]

_BRIDGE_KEYWORDS = (
    "次のニュース",
    "続いて of ニュース",
    "続いてのニュース",
    "続いて",
    "本日もそろそろお別れ",
    "そろそろお別れ",
    "では最後",
    "最後のニュース",
)

_SENTENCE_ENDS = ("。", "！", "？", ".", "!", "?", "♪", "〜")


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


def parse_script(text: str) -> tuple[list[tuple[str, str]], bool]:
    """台本テキストをパースして((話者, セリフ)のリスト, END到達フラグ)を返す"""
    lines: list[tuple[str, str]] = []
    has_end = False
    for raw in text.strip().split("\n"):
        line = raw.strip()
        if not line:
            continue
        if "<<END>>" in line:
            has_end = True
            continue
        match = re.match(rf"^({MC_A}|{MC_B}):(.+)$", line)
        if match:
            speaker = match.group(1)
            content = match.group(2).strip()
            if content:
                lines.append((speaker, content))
    return lines, has_end


def _looks_truncated(parsed: list[tuple[str, str]], has_end: bool) -> bool:
    """途中切れと推定できるか判定"""
    if has_end:
        return False
    if not parsed:
        return True
    last_text = parsed[-1][1].strip()
    if not last_text.endswith(_SENTENCE_ENDS):
        return True
    tail_blob = "".join(l for _, l in parsed[-4:])
    ending_markers = ("また明日", "お別れ", "お相手は", "良い一日", "良い夜", "おやすみ")
    return not any(m in tail_blob for m in ending_markers)


def _trim_to_last_complete_news(parsed: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """途中切れと判定された台本を、最後に完結したニュース境界まで戻す"""
    if not parsed:
        return []
    bridge_indices = [
        i for i, (_, txt) in enumerate(parsed) if any(k in txt for k in _BRIDGE_KEYWORDS)
    ]
    if bridge_indices:
        cutoff = bridge_indices[-1]
        trimmed = parsed[:cutoff]
    else:
        trimmed = list(parsed)
    while trimmed and not trimmed[-1][1].strip().endswith(_SENTENCE_ENDS):
        trimmed.pop()
    return trimmed


def _append_fallback_ending(
    parsed: list[tuple[str, str]], slot: str = "morning"
) -> list[tuple[str, str]]:
    """エンディング雛形を末尾に追加"""
    out = list(parsed)
    closing = "良い一日を！" if slot == "morning" else "良い夜を！"
    for spk_tmpl, line_tmpl in FALLBACK_ENDING:
        speaker = spk_tmpl.format(mc_a=MC_A, mc_b=MC_B)
        text = line_tmpl.format(mc_a=MC_A, mc_b=MC_B)
        if "良い一日を！" in text:
            text = text.replace("良い一日を！", closing)
        out.append((speaker, text))
    return out


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
- 朝紹介したニュースの中から「今日いちばん使えるAIニュース1本」に絞り、その1本だけを詳しく紹介すること（2本以上の紹介は禁止）。
- 完成音声が3分〜5分に収まる長さにする。
- 台本全体は日本語で約1,500〜2,200文字を目安にし、MCセリフ行だけで15〜25行程度にする。
- エンディング例：
    {MC_A}: それではまた明日、同じ時間にお会いしましょう。
    {MC_B}: お相手は {MC_B} と、
    {MC_A}: {MC_A} でした。良い夜を！
"""
    else:
        slot_instruction = f"""【スロット：朝刊（morning）】
- 朝の放送用です。最初の挨拶は必ず「おはようございます」としてください。
- ニュースは必ず「ちょうど3本」紹介すること（2本以下も4本以上も禁止）。
- 完成音声が9分30秒〜10分30秒に収まる長さにする。
- 台本全体は日本語で約4,800〜5,400文字を目安にし、MCセリフ行だけで45〜55行程度にする。
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
            max_output_tokens=8192,
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

    parsed, has_end = parse_script(script_raw)
    if not parsed:
        # script_rawがうまくパースできなかった場合の保険
        parsed, has_end = parse_script(raw_text)
        if not parsed:
            raise ValueError("Failed to parse script lines")

    if _looks_truncated(parsed, has_end):
        logger.warning("Script appears truncated. Reconstructing ending.")
        parsed = _trim_to_last_complete_news(parsed)
        if not parsed:
            raise ValueError("Truncated script could not be recovered")
        parsed = _append_fallback_ending(parsed, slot=slot)

    logger.info(f"Script lines: {len(parsed)} (has_end={has_end})")
    return parsed, title, summary, sns_draft
