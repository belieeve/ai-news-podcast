"""Gemini APIで2人掛け合いの台本を生成"""
import re
import logging
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MC_A, MC_B, PODCAST_TITLE

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """あなたはポッドキャスト番組「{show_name}」の構成作家です。
以下のニュースをもとに、2人のMC「{mc_a}」と「{mc_b}」の掛け合い台本を書いてください。

【最重要：ニュース本数の制約】
- ニュースは必ず「ちょうど3本」紹介すること（2本以下も4本以上も禁止）
- 1本あたり、MC2人で2〜4往復ほどしっかり掘り下げて解説する
- 番組は必ず「3本目のニュースを最後まで紹介し終えて」「エンディング挨拶を言い切ってから」終わること
- 1つのニュースを途中で切るのは絶対に禁止
- 文字数の上限は設けない。3本を最後まで紹介し、エンディングまで完結させることを最優先する

【MC名（変更禁止）】
- メインMC: {mc_a}
- サブMC: {mc_b}

【出力ルール】
- 全行は必ず「{mc_a}:」または「{mc_b}:」で始める（コロンの前にスペース不可）
- 演出指示・注釈・空行は入れない
- 構成: ① 番組名コール（1行） ② 短い挨拶（1行） ③ ニュース解説（各2〜4往復・必ず3本） ④ エンディング ⑤ 最終行に <<END>>
- ニュースとニュースの間は「{mc_a}: それでは次のニュースです。」のような短い1行ブリッジを必ず入れる
- 3本目のニュースが終わった直後に、専用のブリッジ「{mc_a}: さて、本日もそろそろお別れの時間です。」を入れてエンディングへ移る
- エンディングは番組らしく2〜4行で締める。例:
    {mc_a}: それではまた明日、同じ時間にお会いしましょう。
    {mc_b}: お相手は {mc_b} と、
    {mc_a}: {mc_a} でした。良い一日を！
- エンディング行のあと、最終行にちょうど1行 <<END>> とだけ書く（「{mc_a}:」「{mc_b}:」は付けない）
- 専門用語はやさしい言葉に言い換える
- AIツールの新機能は「何が新しい・どう便利・誰が得する」を簡潔に
- 業界の動き（資金調達・提携・規制）はリスナーへの影響まで触れる
- 親しみやすく明るいラジオ番組のトーン

【MCのキャラクター】
- {mc_a}: メインMC。落ち着いた知的なトーン。進行とニュース紹介
- {mc_b}: サブMC。好奇心旺盛で前のめり。リスナー目線で短く質問

【今日のニュース】
{{news_text}}

出力は「{mc_a}:」または「{mc_b}:」で始まる行と、最終行の <<END>> のみにしてください。
"""

# 末尾セーフティ用：ニュース途中切れを検知した場合に挿入するエンディング雛形
FALLBACK_ENDING = [
    ("{mc_a}", "さて、本日もそろそろお別れの時間です。"),
    ("{mc_b}", "明日も気になるAIニュース、お届けしますね。"),
    ("{mc_a}", "それではまた明日、同じ時間にお会いしましょう。"),
    ("{mc_b}", "お相手は {mc_b} と、"),
    ("{mc_a}", "{mc_a} でした。良い一日を！"),
]

# ニュース間ブリッジを示すキーワード（境界検出に使う）
_BRIDGE_KEYWORDS = (
    "次のニュース",
    "続いてのニュース",
    "続いて",
    "本日もそろそろお別れ",
    "そろそろお別れ",
    "では最後",
    "最後のニュース",
)

# 文末として認められる終止記号
_SENTENCE_ENDS = ("。", "！", "？", "."  , "!", "?", "♪", "〜")


def format_news(articles: list[dict]) -> str:
    """ニュースリストを台本生成用テキストに整形"""
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(f"ニュース{i}: {a['title']}\nソース: {a['source']}\n要約: {a['summary']}\n")
    return "\n".join(parts)


def parse_script(text: str) -> tuple[list[tuple[str, str]], bool]:
    """台本テキストをパースして((話者, セリフ)のリスト, END到達フラグ)を返す。

    END到達フラグ: 出力末尾に <<END>> センチネルが含まれていたか。
    含まれていなければGeminiの出力が途中で切れた可能性が高い。
    """
    lines: list[tuple[str, str]] = []
    has_end = False
    for raw in text.strip().split("\n"):
        line = raw.strip()
        if not line:
            continue
        if "<<END>>" in line:
            has_end = True
            # END行自体は台本に含めない
            continue
        match = re.match(rf'^({MC_A}|{MC_B}):(.+)$', line)
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
    # 文末記号で終わっていなければほぼ確実に切れている
    if not last_text.endswith(_SENTENCE_ENDS):
        return True
    # 文末記号で終わっていても、エンディング定型句が出ていなければ切れている扱い
    tail_blob = "".join(l for _, l in parsed[-4:])
    ending_markers = ("また明日", "お別れ", "お相手は", "良い一日")
    return not any(m in tail_blob for m in ending_markers)


def _trim_to_last_complete_news(parsed: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """途中切れと判定された台本を、最後に「完結した」ニュース境界まで戻す。

    境界 = 「次のニュース/続いて/最後のニュース」等のブリッジ行の「直前」。
    そのブリッジ行が無ければ、安全のためできるだけ多くの行を残しつつ、
    最後の文末記号で終わる行までを採用する。
    """
    if not parsed:
        return []

    bridge_indices = [
        i for i, (_, txt) in enumerate(parsed)
        if any(k in txt for k in _BRIDGE_KEYWORDS)
    ]

    if bridge_indices:
        # 最後のブリッジ行の「直前」までを完結ぶんとして採用
        cutoff = bridge_indices[-1]
        trimmed = parsed[:cutoff]
    else:
        trimmed = list(parsed)

    # 末尾を文末記号で終わる行まで巻き戻す
    while trimmed and not trimmed[-1][1].strip().endswith(_SENTENCE_ENDS):
        trimmed.pop()

    return trimmed


def _append_fallback_ending(parsed: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """エンディング雛形を末尾に追加（MC名のプレースホルダを置換）"""
    out = list(parsed)
    for spk_tmpl, line_tmpl in FALLBACK_ENDING:
        speaker = spk_tmpl.format(mc_a=MC_A, mc_b=MC_B)
        text = line_tmpl.format(mc_a=MC_A, mc_b=MC_B)
        out.append((speaker, text))
    return out


def generate_script(articles: list[dict]) -> list[tuple[str, str]]:
    """ニュースから台本を生成"""
    client = genai.Client(api_key=GEMINI_API_KEY)

    news_text = format_news(articles)
    # MC名と番組名を先に埋め込み、news_textは後から
    prompt = PROMPT_TEMPLATE.format(
        show_name=PODCAST_TITLE,
        mc_a=MC_A,
        mc_b=MC_B,
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

    parsed, has_end = parse_script(raw_text)
    if not parsed:
        raise ValueError("Failed to parse script")

    if _looks_truncated(parsed, has_end):
        logger.warning(
            "Script appears truncated (has_end=%s). Trimming to last complete news and appending fallback ending.",
            has_end,
        )
        parsed = _trim_to_last_complete_news(parsed)
        if not parsed:
            raise ValueError("Truncated script could not be recovered")
        parsed = _append_fallback_ending(parsed)

    logger.info(f"Lines: {len(parsed)} (has_end={has_end})")
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
