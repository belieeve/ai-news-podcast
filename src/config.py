"""毎朝トレンドラジオ - 設定ファイル"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# パス
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"
AUDIO_DIR = OUTPUT_DIR / "episodes"
SCRIPTS_DIR = OUTPUT_DIR / "scripts"
RSS_FILE = OUTPUT_DIR / "feed.xml"
LOG_DIR = PROJECT_ROOT / "logs"

# Google News（日本語）
# AIを軸に、マーケティング・ビジネス・エンタメ・SNSトレンドまで幅広く拾う
NEWS_QUERIES = [
    # AI（番組の軸）
    "ChatGPT 新機能", "Claude AI 最新", "Gemini 最新",
    "OpenAI", "Anthropic", "生成AI 新サービス",
    "AIエージェント", "AIツール 話題", "AI 業務効率化",
    "AI スタートアップ 資金調達",
    # マーケティング・ビジネス
    "マーケティング 話題", "SNSマーケティング 事例",
    "広告 キャンペーン 話題", "ヒット商品 なぜ",
    "スタートアップ 新サービス 発表", "ビジネス トレンド",
    # エンタメ
    "Netflix 話題 作品", "映画 ヒット 興行収入",
    "アニメ 話題", "音楽 ヒット 話題",
    "ゲーム 新作 話題", "YouTube 話題",
    # SNS・トレンド全般
    "SNS バズ 話題", "TikTok 流行",
    "X トレンド 話題", "海外 話題 バズ",
    "Z世代 流行",
]
MAX_ARTICLES = 15

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# MC名（固定）
MC_A = "リナ"   # メインMC（お姉ギャル）
MC_B = "モモ"   # サブMC（ハイテンションギャル）

# Edge-TTS 音声（日本語）
TTS_VOICE_A = "ja-JP-NanamiNeural"   # 女性（リナ）※Edge-TTSの日本語女性はNanamiのみ。2人はピッチ・速度で差別化
TTS_VOICE_B = "ja-JP-NanamiNeural"   # 女性（モモ）
TTS_RATE_A = "+2%"
TTS_RATE_B = "+10%"
TTS_PITCH_A = "-6Hz"
TTS_PITCH_B = "+18Hz"

# Podcast メタデータ（Spotify for Podcasters と一致させる）
PODCAST_TITLE = "リナとモモの朝アゲトレンド｜AI・エンタメ・ビジネスの話題まとめ"
PODCAST_DESCRIPTION = "AIを軸に、マーケティング・ビジネス・エンタメ・SNSでバズっている話題まで。ギャルMC2人のリナとモモが、今話題になっていることを毎朝10〜15分でゆるっと楽しくお届けします。"
PODCAST_AUTHOR = "リナ＆モモ"
PODCAST_EMAIL = "believe.spotify33@gmail.com"
PODCAST_LANGUAGE = "ja"
PODCAST_CATEGORY = "Technology"
PODCAST_IMAGE = "artwork_v4.jpg"

# GitHub Pages
GITHUB_PAGES_REPO_PATH = os.getenv("GITHUB_PAGES_REPO_PATH", "")
GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "")

# エピソード管理
MAX_EPISODES = 50
MAX_SCRIPT_CHARS = 7000  # デイリー台本は3,500〜4,800文字が目安（Edge-TTS日本語ボイスで概ね5〜6文字/秒＝10〜15分）

# 発音・イントネーション補正辞書
# Edge-TTSが固有名詞を誤読する場合、ここに「元の表記 → TTSが正しく読む表記」を追加。
# とくにカタカナ中黒「・」はアクセントを乱しやすいので外すと安定することが多い。
PRONUNCIATION_FIXES = {
    "イーロン・マスク": "イーロンマスク",
}

# BGM設定（assets/bgm.mp3 が存在する場合のみ自動でナレーションにミックスされる）
BGM_FILE = PROJECT_ROOT.parent / "assets" / "bgm.mp3"
BGM_VOLUME_DB = -22           # BGM音量。数字を小さくするほど静かに（例: -25でさらに控えめ、-18で少し大きめ）
BGM_FADEOUT_MS = 3000         # 番組末尾のフェードアウト時間（ミリ秒）
BGM_LOOP_CROSSFADE_MS = 1500  # ループ繋ぎ目のクロスフェード時間（ミリ秒）
