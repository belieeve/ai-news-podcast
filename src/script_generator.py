"""Gemini APIで2人掛け合いの台本、タイトル、概要欄、SNS下書きを生成"""
import re
import logging
from datetime import datetime
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MC_A, MC_B, PODCAST_TITLE

logger = logging.getLogger(__name__)

# プロンプトテンプレート
PROMPT_TEMPLATE = """あなたは、AIニュースを「仕事と副業に使える形」に翻訳するPodcast編集者です。
毎週1回、1週間分のAIニュースを整理し、Podcast台本と各種パッケージ情報を作成してください。
番組の目的は、AIニュースをただ紹介することではありません。リスナーが「今週、何を理解し、何を試せばいいか」がわかる状態にすることです。
あなたは「AIニュースの読み上げ係」ではありません。ニュースを集めるだけならAIでもできます。だからこそ、あなたの役割は「何が重要で、何は無視してよくて、今週何を試すべきか」を判断することです。

【番組コンセプト】
- 番組名: {show_name}
- サブタイトル: 「1週間のAIニュースから、仕事と副業に効く話だけをわかりやすく解説します」
- 役割: AIニュースの羅列ではなく、AIニュースの意味づけを行う。
- 必須項目: 各ニュースについて「何が起きたか」「誰に関係あるのか」「なぜ重要なのか」「今すぐ試すべきか、まだ様子見でいいのか」「仕事や副業にどう使えるのか」を必ず入れること。

【リスナー対象】
- AIを仕事や副業に活かしたい会社員、個人事業主、クリエイター。
- AIに関心はあるけれど、毎日ニュースを追う時間がない人。
- 難しい話は、仕事・副業・日常にどう関係するかまで落とし込んで説明する。

{slot_instruction}

【MC名（変更禁止）】
- メインMC（明るく話し上手、知的好奇心を刺激する進行役）: {mc_a}
- サブMC（ノリが良くリアクション豊富、素朴な疑問や楽しいツッコミを入れる相棒）: {mc_b}

【話し方とトーン】
- 難しすぎず、親しみやすく、エンタメ寄りのフランクなラジオの雰囲気。
- テンポが良く、フランクで明るい対話。2人が楽しそうに会話している様子が伝わり、リスナーが横で一緒におしゃべりを聞いているような空気感を重視する。
- 専門用語を使う場合は、必ず簡単に説明する。
- ニュースを読むだけではなく、会話しているように自然に進める（ただし軽すぎる雑談は不要）。

【禁止事項】
- 曜日順にニュースをただ並べるだけの構成（「月曜日はこれ、火曜日はこれ...」）は避ける。
- ニュースの羅列で終わらせない。「すごいですね」「便利ですね」だけで終わらせず、「誰に関係あるか」「何に使えるか」「今やるべきか」を必ず入れる。
- 煽りすぎない。「AIを使わない人は終わりです」「これで誰でも簡単に稼げます」のような表現は絶対に使用しない。

【今日のニュース候補】
{news_text}

【出力フォーマット】
以下の区切り線を正確に使用し、それぞれの内容を出力してください。プレースホルダや余計な解説、マークダウンの外側にテキストを書かないでください。

=== TITLE ===
（番組タイトル案。スマホ画面で意味が伝わる30〜45文字程度）

=== SUMMARY ===
（ポッドキャスト概要欄文。今週のひと言まとめ、採用したニュース一覧、各ニュースを採用した理由、ニュース/ツールリンクプレースホルダ、Spotifyフォローのお願い、最後の締めを含む）

=== SCRIPT ===
（掛け合い台本。全行は必ず「{mc_a}:」または「{mc_b}:」で始める。演出指示・注釈・空行は入れない。質問文は必ず「か」で終える。構成通りに作成し、最終行に <<END>> とだけ書く）

=== SNS_DRAFT ===
【ニュースレター導入文】（今週のAIニュース全体の導入文。AI副業ログや今週の学びのまとめ、無料版要約・活用メモ形式）
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
    slot: str = "weekly",
) -> tuple[list[tuple[str, str]], str, str, str]:
    """ニュースから台本、タイトル、概要欄、SNS下書きを生成"""
    client = genai.Client(api_key=GEMINI_API_KEY)

    # スロット別の指示
    slot_instruction = f"""【スロット：週刊（weekly）】
- 週刊の放送用です。最初の挨拶は必ず「おはようございます」または「こんにちは」としてください。
- 過去1週間のニュース候補から、重要なものを【3〜5本だけ】選んで台本を作成してください（話題性だけや専門的すぎるニュースは除外）。
- 完成音声が15分〜20分に収まる長さにする。
- 台本全体は日本語で約4,000〜6,000文字を目安にし、テンポよく聴きやすい文章にしてください。
- 構成ルール（厳守）:
  1. オープニング: 今週のAI業界をひ言でまとめ、今日聴くメリットを伝える。
  2. 今週の最重要ニュース: 1つ選び、「何が起きたか」「なぜ重要か」「誰に関係あるか」「今すぐ使うべきか、様子見か」「仕事や副業への影響」を説明。
  3. 仕事に効くAIニュース: 業務効率化、ビジネスに関するニュースを紹介（明日から何が変わるか）。
  4. 副業・個人ビジネスに効くAIニュース: 副業、ブログ、SNS等に関連する話（煽らず、現実的なメリットや準備）。
  5. クリエイター・発信者向けAIニュース: 動画/画像生成、音声配信、マルチチャネル展開に関するニュース。
  6. 今週の判断: 編集者としての今週の総括（本当に重要な変化、焦らなくていい話、個人が今から準備すること）。
  7. 今週やること: リスナーが今週やるべき小さく具体的な行動を1つ提案（理由も説明）。
  8. クロージング: ニュースレター（メルマガ）登録への自然な誘導を入れてエンディング挨拶。
- エンディング例：
    {MC_A}: それではまた来週、同じ時間にお会いしましょう。
    {MC_B}: お相手は {MC_B} と、
    {MC_A}: {MC_A} でした。良い一週間を！
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
