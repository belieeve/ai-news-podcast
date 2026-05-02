"""AI朝刊 - 設定ファイル"""
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
NEWS_QUERIES = [
    # AIツール・サービス
    "ChatGPT 新機能", "Claude AI 最新", "Gemini 最新",
    "Copilot 最新", "Perplexity AI", "NotebookLM",
    "Midjourney", "Stable Diffusion 最新", "Suno AI", "Runway AI",
    # AI業界
    "OpenAI", "Anthropic", "Google AI", "Apple AI",
    "Meta AI", "NVIDIA AI", "Microsoft AI",
    # トレンド
    "生成AI 新サービス", "AIエージェント", "無料 AIツール",
    "AI 業務効率化", "AI スタートアップ 資金調達", "AIアプリ 話題",
]
MAX_ARTICLES = 7

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# MC名（固定）
MC_A = "ハルト"   # メインMC（男性）
MC_B = "アヤカ"   # サブMC（女性）

# Edge-TTS 音声（日本語）
TTS_VOICE_A = "ja-JP-KeitaNeural"    # 男性（ハルト）
TTS_VOICE_B = "ja-JP-NanamiNeural"   # 女性（アヤカ）
TTS_RATE_A = "+10%"
TTS_RATE_B = "+5%"

# Podcast メタデータ（Spotify for Podcasters と一致させる）
PODCAST_TITLE = "AI朝刊"
PODCAST_DESCRIPTION = "毎朝届ける、AIニュースの朝刊。ハルトとアヤカが、ChatGPT・Claude・画像生成AI・話題のAIツールやサービスの最新動向を、わかりやすく解説します。"
PODCAST_AUTHOR = "Believe"
PODCAST_EMAIL = "believe.spotify33@gmail.com"
PODCAST_LANGUAGE = "ja"
PODCAST_CATEGORY = "Technology"
PODCAST_IMAGE = "artwork.jpg"

# GitHub Pages
GITHUB_PAGES_REPO_PATH = os.getenv("GITHUB_PAGES_REPO_PATH", "")
GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "")

# エピソード管理
MAX_EPISODES = 50
MAX_SCRIPT_CHARS = 4000
