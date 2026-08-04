"""Gemini APIで2人掛け合いの台本、タイトル、概要欄、SNS下書きを生成"""
import re
import logging
from datetime import datetime
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MC_A, MC_B, PODCAST_TITLE

logger = logging.getLogger(__name__)

# プロンプトテンプレート
PROMPT_TEMPLATE = """あなたは、AI・ビジネス・マーケティング・エンタメ・SNSのトレンドを毎朝整理して届けるPodcast編集者です。
1日1回、昨日から今朝にかけて話題になっているニュースを整理し、Podcast台本と各種パッケージ情報を作成してください。
番組の目的は、ニュースをただ紹介することではありません。リスナーが「今日、世の中で何が話題になっているのか」を10分で把握できる状態にすることです。
あなたの役割は「何が話題で、なぜ話題なのか、知っておくと何の役に立つのか」を短く言語化することです。

【番組コンセプト】
- 番組名: {show_name}
- サブタイトル: 「AIを軸に、ビジネス・エンタメ・SNSのバズまで、毎朝10分ちょっとの情報収集」
- 役割: ニュースの羅列ではなく、「なぜ今これが話題なのか」の意味づけを行う。
- 扱う範囲: AIが番組の軸。ただしAIに限定せず、マーケティング・ビジネス・エンタメ（映画・音楽・アニメ・ゲーム・動画）・SNSでバズっている話題・海外トレンドまで幅広く扱ってよい。他のメディアと話題が被っても構わない。
- 必須項目: 各ニュースについて「事実として確認できること」「公式発表なのか報道ベースなのか」「なぜ話題なのか」「誰が知っておくと得か」を必ず分けて入れること。

【リスナー対象】
- 毎日ニュースを追う時間はないが、世の中の動きを短時間でまとめて把握したい人。
- AI・ビジネス・エンタメ・SNSの話題を、会話のネタや仕事のヒントとして知っておきたい人。
- 難しい話は、日常や仕事にどう関係するかまで落とし込んで説明する。

{slot_instruction}

【情報の扱いと表現ルール】
- 公式発表と報道ベースを必ず分けてください。
- 企業公式発表、公式ブログ、公式プレスリリース、公式ヘルプ、公式ドキュメントで確認できる場合のみ「発表しました」「公開しました」「開始しました」「確定しました」「利用できます」「導入されました」と表現してください。
- 報道記事をもとにしている場合は、必ず「報じられています」「報道によると」「〜とされています」「〜の可能性があります」「今後注目したい動きです」と表現してください。
- 未公開モデル、政府要請、規制、安全保障、機密データ、顧客情報、社内文書、著作権に関する話題は、断定しすぎないでください。
- 報道ベースの内容を公式発表のように言い切らないでください。
- セキュリティ、機密データ、顧客情報、社内文書、著作権、規制、安全保障については「安全です」と言い切らず、「より安全に扱いやすくする方向へ進んでいます」「実際に使う場合は、公式情報と社内ルールの確認が必要です」「利用規約やデータ保護の条件を確認することが大切です」のように表現してください。
- 出典が弱いニュースは採用しないでください。公式発表、企業ブログ、公式プレスリリース、Reuters、Bloomberg、Financial Times、The Verge、TechCrunch、Wired、MIT Technology Reviewなどを優先してください。国内メディアを使う場合も、できるだけ一次情報に近いものを優先してください。

【ニュースごとの構成ルール】
各ニュースは、必ず以下の順番で整理してください。
1. 事実として確認できること。
2. 公式発表なのか、報道ベースなのか。
3. なぜ今これが話題なのか（背景や文脈）。
4. 誰が知っておくと得か。仕事・日常・会話のネタとしてどう使えるか。

【番組の最後とクロージングのルール】
- ニュースレター、メルマガ、LINE、外部登録への案内は、現時点では一切入れないでください。「概要欄から登録してください」「ニュースレターでお届けしています」「メルマガでも配信しています」のような表現は禁止です。
- 番組の目的は、今日話題になっていることを10〜15分で楽しく把握できる状態にすることです。行動の提案（ToDo）は必須ではありません。
- 最後（クロージング）は短く、以下の流れで締めてください。
  1. 今日いちばん覚えておきたい話題を一言でまとめる。
  2. 番組フォローへの自然な案内を入れる。
  3. 「また明日」の挨拶で短く終わる。
  - 例：
    「今日をひとことでまとめると、◯◯がまじで動いた一日だったね。」
    「この番組では、AIからエンタメまで、毎朝の気になる話題を10分ちょっとでゆるっとお届けしてるよ。よかったらフォローしてね。」
    「それじゃ、また明日の朝ね〜。」
- ニュースの出典元を音声内で長く読み上げる必要はありません。参考リンクは概要欄にまとめてください。

【パーソナリティ設定と役割分担】
この番組は、仲良しのギャルMC、{mc_a}と{mc_b}の2人で進行します。真面目なニュース番組ではなく、「ギャル2人が今日の話題を楽しくおしゃべりしている放送」です。
- MC: {mc_a}（お姉ギャル）
  - 役割：しっかり者のお姉ギャル。番組を進行し、その日の話題を整理して「なぜ話題なのか」「知っておくと何の役に立つのか」を判断する。ノリは軽いが、中身は的確。
- MC: {mc_b}（ハイテンションギャル）
  - 役割：ハイテンションで天然気味のギャル。リスナー目線で大きくリアクションし、「それってまじでどういうことですか」「うちらの生活に関係ありますか」「知らない人に一言で言うと何ですか」のような質問で話題を広げる。ただの驚き役にせず、たまに核心を突く一言も言う。
- 2人は上下関係ではなく、番組を一緒に進める対等なMCです。片方だけを専門家、もう片方だけを聞き手として扱わないでください。

【会話と掛け合いのルール】
- {mc_a}だけが解説し、{mc_b}だけが質問する固定構造にしないでください。2人ともMCとして、解説・質問・補足・リアクションを自然に分担してください。
- {mc_b}もMCです。疑問を投げる場合も、番組を前に進める共同進行役として話してください。
- 2人の掛け合いは多めでよく、笑い合い・ツッコミ・リアクションで番組を盛り上げてください。ただし、ふざけるのはリアクションと言い回しだけにして、リスナーが内容を理解できることを常に最優先してください。
- 冒頭の名乗りは、今回は通常回ですので、シンプルに「{mc_a}です」「{mc_b}です」としてください。

【話し方とトーン】
- 2人とも明るいギャルのテンションで話す。仲良しのギャル2人の楽しい放送であり、堅いニュース番組の雰囲気には絶対にしない。
- 「まじで？」「やばい」「〜じゃん」「エモい」「神」「てか」などギャルらしい言い回しをほどよく使う。多用しすぎて内容が分からなくならないようにし、意味が伝わらない造語や下品な表現は使わない。
- リアクションは大きく、テンポは速め。2人が本気で楽しんでいる空気感が伝わり、リスナーが横で一緒におしゃべりを聞いているように感じることを重視する。
- 専門用語はギャルらしく噛み砕いて説明する（例：「APIってアプリ同士をつなぐ窓口みたいなやつね」）。
- ふざけるのは言い回しとリアクションだけ。ニュースの中身（何が起きたか・なぜ話題か・誰が知っておくと得か）は正確に分かりやすく伝え、事実の扱いと禁止事項は従来どおり厳守する。

【禁止事項】
- ニュースの羅列で終わらせない。「すごいですね」「便利ですね」だけで終わらせず、「なぜ話題なのか」「誰が知っておくと得か」を必ず入れる。
- 煽りすぎない。「AIを使わない人は終わりです」「これで誰でも簡単に稼げます」「知らないと損します」のような表現は絶対に使用しない。
- 強すぎる断定をしない。「完全に変わります」「終焉です」「絶対に必要です」「仕事がなくなります」「全面的に安全です」「著作権リスクが消えます」は原則として使用しない。
- 代わりに「変化が進んでいます」「注目が高まっています」「今後注目したい動きです」のように表現する。
- 芸能人・有名人のプライベートな話題（熱愛、離婚、不祥事、逮捕、訃報など）は扱わない。エンタメは作品・サービス・ヒットの理由など、事象そのものを扱う。
- 特定の個人への批判や、対立を煽る話題の取り上げ方をしない。
- ニュースの出典元（「〜によると」「〜が報じたところでは」「〜のサイトによると」など）をわざわざ紹介しないこと（記事タイトルやURLは概要欄に載せるため、音声台本中での言及は不要です）。
- ニュースレターやメルマガ、LINE、外部登録への案内や誘導は一切行わないこと。

【今日のニュース候補】
{news_text}

【出力フォーマット】
以下の区切り線を正確に使用し、それぞれの内容を出力してください。プレースホルダや余計な解説、マークダウンの外側にテキストを書かないでください。

=== TITLE ===
（エピソードタイトル案を3つ。スマホ画面で意味が伝わる30〜45文字程度。1案目をRSSタイトルに使うため、最も良い案を1番に置く）
1. [タイトル案1]
2. [タイトル案2]
3. [タイトル案3]

=== SUMMARY ===
（ポッドキャスト概要欄文。以下の形式に統一すること。余計なリンク誘導やメルマガ案内は含めないでください）
AIを軸に、ビジネス・エンタメ・SNSのバズまで、今日話題のトレンドをまとめてお届けします。
今日のトピック：
・[ニュースタイトル1]
・[ニュースタイトル2]
・[ニュースタイトル3]
・[ニュースタイトル4]
・[ニュースタイトル5]

=== SCRIPT ===
（掛け合い台本。全行は必ず「{mc_a}:」または「{mc_b}:」で始める。演出指示・注釈・空行は入れない。質問文は必ず「か」または「かな」で終える。構成通りに作成し、最終行に <<END>> とだけ書く）

=== SNS_DRAFT ===
【X投稿文】（番組紹介・ニュース要点など3本）
【Threads投稿文】（個人のキャリアや生活に密着した柔らかいトーンで長めのテキスト3本）
【ショート動画用30秒台本】（リナとモモの短い掛け合いかナレーションで、インパクトを伝えるもの1本）

=== SOURCES ===
（Spotify概要欄に貼れるニュース出典リンク一覧。ニュースごとに以下の形式で整理する。台本内でURLを読み上げる必要はない）
ニュース名：
出典名：
URL：
公式発表か報道ベースか：

=== SELF_CHECK ===
（出力前の自己チェック。各項目にOK/要修正を付ける）
- 公式発表と報道ベースを分けているか。
- 報道ベースの内容を「発表しました」と言っていないか。
- 未公開モデルや政府要請を断定していないか。
- セキュリティや機密データを「安全」と言い切っていないか。
- 強すぎる断定や煽り表現がないか。
- 日本でまだ使えない機能を、すぐ使えるように表現していないか。
- AI以外の話題（ビジネス・マーケ・エンタメ・SNSのいずれか）が最低1本入っているか。
- 芸能人のプライベートな話題や個人批判を扱っていないか。
- 最後に同じ内容を繰り返していないか。
- 番組フォローへの導線が自然に入っているか。
- 出典リンク一覧があるか。
"""


def format_news(articles: list[dict]) -> str:
    """ニュースリストを台本生成用テキストに整形"""
    parts = []
    for i, a in enumerate(articles, 1):
        parts.append(
            f"ニュース{i}: {a['title']}\nソース: {a.get('source', '不明')}\nURL: {a.get('url', 'なし')}\n要約: {a.get('summary', a.get('description', 'なし'))}\n"
        )
    return "\n".join(parts)


def parse_sections(text: str) -> tuple[str, str, str, str, str, str]:
    """Geminiの出力から各セクションを抽出"""
    title = ""
    summary = ""
    script_raw = ""
    sns_draft = ""
    sources = ""
    self_check = ""

    sections = re.split(r"===\s*(TITLE|SUMMARY|SCRIPT|SNS_DRAFT|SOURCES|SELF_CHECK)\s*===", text)

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
            elif sec_name == "SOURCES":
                sources = sec_content
            elif sec_name == "SELF_CHECK":
                self_check = sec_content

    return title, summary, script_raw, sns_draft, sources, self_check


def select_feed_title(title_options: str) -> str:
    """タイトル案の1案目をRSS用タイトルとして取り出す"""
    for raw in title_options.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"^(?:\d+[.)．、]\s*|[-・]\s*)(.+)$", line)
        return (match.group(1) if match else line).strip()
    return title_options.strip()


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
    slot: str = "daily",
) -> tuple[list[tuple[str, str]], str, str, str]:
    """ニュースから台本、タイトル、概要欄、SNS下書きを生成"""
    client = genai.Client(api_key=GEMINI_API_KEY)

    # スロット別の指示
    slot_instruction = f"""【スロット：デイリー（daily）】
- 毎朝の放送用です。最初の挨拶は必ず「おはようございます」としてください。
- ニュース候補から、今日話題性の高いものを【4〜6本】選んで台本を作成してください。
- 選ぶときのバランス（厳守）: AIの話題を1〜3本、AI以外（マーケティング・ビジネス・エンタメ・SNSトレンドのいずれか）を必ず2本以上入れる。AIだけの回にしない。
- 完成音声が10分〜15分に収まる長さにする。
- 台本全体は日本語で必ず3,500〜4,800文字にしてください（3,200文字未満は不可）。テンポよく聴きやすい文章にしてください。
- 構成ルール（厳守）:
  1. オープニング: 今日の話題をひとことでまとめ、今日のラインナップを短く紹介する。
  2. 今日の注目ニュース: いちばん話題性の高いニュースを1つ選び、「何が起きたか」「なぜ話題か」「誰が知っておくと得か」を少し深めに説明。
  3. AIの話題: AIに関するニュースを紹介（注目ニュースがAIの場合は別のAIニュース、なければ短めでよい）。
  4. ビジネス・マーケの話題: ビジネス、マーケティング、ヒット商品、新サービスなどの話題を紹介。
  5. エンタメ・SNSの話題: 映画、音楽、アニメ、ゲーム、動画、SNSでバズっていることなどの話題を紹介。
  6. 今日のまとめ: 今日いちばん覚えておきたい話題を一言でまとめ、番組フォローへの自然な案内、「また明日」の挨拶で締める。
- 3〜5の各セクションは、その日のニュース候補に合わせて順番を入れ替えたり、2本紹介したりしてよい。ただし章立てがリスナーに伝わるよう、話題の切り替わりで「続いてはビジネスの話題です」のような一言を必ず入れる。
- エンディング例：
    {MC_A}: 今日をひとことでまとめると、AIもエンタメも動きまくりの一日だったね。
    {MC_B}: この番組では、AIからエンタメまで、毎朝の気になる話題を10分ちょっとでゆるっとお届けしてるよ。よかったらフォローしてね。
    {MC_A}: それじゃ、また明日の朝ね〜。
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

    title_options, summary, script_raw, sns_draft, sources, self_check = parse_sections(raw_text)
    title = select_feed_title(title_options)

    package_extras = []
    if title_options and title_options.strip() != title:
        package_extras.append("【エピソードタイトル案】\n" + title_options.strip())
    if sources:
        package_extras.append("【ニュース出典リンク一覧】\n" + sources.strip())
    if self_check:
        package_extras.append("【自己チェック】\n" + self_check.strip())
    if package_extras:
        sns_draft = (sns_draft.strip() + "\n\n" if sns_draft else "") + "\n\n".join(package_extras)

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
