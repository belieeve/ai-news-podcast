"""Gemini APIによるポッドキャスト配信原稿のファクトチェック監査（監査AI）"""
import re
import logging
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MC_A, MC_B

logger = logging.getLogger(__name__)

AUDIT_PROMPT_TEMPLATE = """あなたはAIニュースポッドキャストのファクトチェック・監査担当の編集者です。
生成されたポッドキャスト配信原稿（タイトル、概要欄、台本、SNS下書き）が、元のニュースの事実と一致しているか、また信頼性を損ねるような過剰な煽りや断定、解釈の混ぜ合わせがないかを厳格にチェックします。
面白くする必要や、誇張する必要はありません。事実に基づいた正確さを最優先にしてください。

【監査の観点】
1. ソースの整合性：それぞれのニュースが、元のニュース（一次情報や大手報道）の事実に正確に基づいているか。出典情報が正しく機能しているか。
2. 事実と解釈の分離：ニュースの事実と、番組側の解説・解釈（「日本の個人や中小企業への示唆」など）が明確に分けられているか。
3. 誇張・煽り・断定の排除：「全面的に安全」「完全に解決」「終焉」「禁止」「確定」「仕事がなくなる」「必ず」「絶対に」「AI三国志」「完全に安全」「ChatGPT一強の終焉」「時代遅れ」などの表現がないか。
4. 海外限定機能の扱い：海外限定の機能を、日本でもすぐ使えるかのように説明していないか。
5. 専門領域の安全な表現：著作権、規制、投資、医療、法律、安全保障に関する話題で、言い切り・断定をしすぎていないか。不確かな部分は「〜と報じられています」「〜の可能性があります」と表現を弱めているか。
6. 数字や固有名詞の正確性：数字、企業名、サービス名、発表日に誤りがないか。

【入力データ】
■ 元のニュース（一次情報）
{articles_text}

■ 監査対象のコンテンツ
【タイトル】
{title}

【概要欄】
{summary}

【台本】
{script_text}

【SNS下書き】
{sns_draft}

【出力フォーマット】
以下の区切り線を使用して監査結果を出力してください。プレースホルダや余計な解説を外側に書かないでください。

=== STATUS ===
（A または B または C の一文字を出力）
A：問題なし。そのまま公開可能。
B：軽微な表現の修正（自動修正）の後に公開可能。
C：事実の誤りや重度の煽り表現があり、公開前に人間の確認・修正が必要。

=== AUDIT_LOG ===
・問題なしの箇所：
・修正が必要な箇所（BまたはC判定の場合）：
・要確認の箇所：
・判定理由：

=== REVISED_TITLE ===
（B判定でタイトルに修正が必要な場合、修正後のタイトルを出力。AまたはCの場合は元のタイトルをそのまま出力）

=== REVISED_SUMMARY ===
（B判定で概要欄に修正が必要な場合、修正後の概要欄を出力。AまたはCの場合は元の概要欄をそのまま出力）

=== REVISED_SCRIPT ===
（B判定で台本に修正が必要な場合、修正後の台本を出力。全行必ず「{mc_a}:」「{mc_b}:」で始めること。AまたはCの場合は元の台本をそのまま出力。最終行に <<END>>）

=== REVISED_SNS_DRAFT ===
（B判定でSNS下書きに修正が必要な場合、修正後のSNS下書きを出力。AまたはCの場合は元のSNS下書きをそのまま出力）
"""


def format_articles_for_audit(articles: list[dict]) -> str:
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(
            f"ニュース{i}: {a['title']}\nソース: {a.get('source', '不明')}\nURL: {a.get('url', 'なし')}\n本文/要約: {a.get('summary', a.get('description', 'なし'))}\n"
        )
    return "\n".join(parts)


def format_script_for_audit(script: list[tuple[str, str]]) -> str:
    return "\n".join(f"{speaker}: {line}" for speaker, line in script)


def parse_script_lines(text: str) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for raw in text.strip().split("\n"):
        line = raw.strip()
        if not line or "<<END>>" in line:
            continue
        match = re.match(rf"^({MC_A}|{MC_B}):(.+)$", line)
        if match:
            lines.append((match.group(1), match.group(2).strip()))
    return lines


def parse_audit_response(text: str) -> dict:
    status = "C"  # デフォルトは安全側に倒してC
    audit_log = ""
    revised_title = ""
    revised_summary = ""
    revised_script_raw = ""
    revised_sns_draft = ""

    sections = re.split(
        r"===\s*(STATUS|AUDIT_LOG|REVISED_TITLE|REVISED_SUMMARY|REVISED_SCRIPT|REVISED_SNS_DRAFT)\s*===",
        text,
    )

    for i in range(1, len(sections), 2):
        sec_name = sections[i]
        if i + 1 < len(sections):
            sec_content = sections[i + 1].strip()
            if sec_name == "STATUS":
                match = re.search(r"\b([A-C])\b", sec_content)
                if match:
                    status = match.group(1)
            elif sec_name == "AUDIT_LOG":
                audit_log = sec_content
            elif sec_name == "REVISED_TITLE":
                revised_title = sec_content
            elif sec_name == "REVISED_SUMMARY":
                revised_summary = sec_content
            elif sec_name == "REVISED_SCRIPT":
                revised_script_raw = sec_content
            elif sec_name == "REVISED_SNS_DRAFT":
                revised_sns_draft = sec_content

    return {
        "status": status,
        "audit_log": audit_log,
        "title": revised_title,
        "summary": revised_summary,
        "script_raw": revised_script_raw,
        "sns_draft": revised_sns_draft,
    }


def audit_content(
    script: list[tuple[str, str]],
    title: str,
    summary: str,
    sns_draft: str,
    articles: list[dict],
) -> dict:
    """コンテンツのファクトチェック監査を行い、公開可否のステータスと修正コンテンツを返す"""
    client = genai.Client(api_key=GEMINI_API_KEY)

    articles_text = format_articles_for_audit(articles)
    script_text = format_script_for_audit(script)

    prompt = AUDIT_PROMPT_TEMPLATE.format(
        articles_text=articles_text,
        title=title,
        summary=summary,
        script_text=script_text,
        sns_draft=sns_draft,
        mc_a=MC_A,
        mc_b=MC_B,
    )

    logger.info("Starting content audit (fact check)...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,  # 決定論的にファクトチェックさせるため温度は低く設定
            max_output_tokens=8192,
        ),
    )

    raw_response = response.text
    logger.info(f"Audit response received ({len(raw_response)} chars)")

    parsed = parse_audit_response(raw_response)

    # 修正版台本のテキストをタプルのリストに戻す
    if parsed["script_raw"]:
        parsed["script"] = parse_script_lines(parsed["script_raw"])
    else:
        parsed["script"] = script

    return parsed
