"""AI News Podcast - 設定ファイル"""
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

# Google News
NEWS_QUERIES = [
    # AIツール・サービスの最新情報
    "ChatGPT 新機能", "Claude アップデート", "Gemini 新機能",
    "Copilot アップデート", "Perplexity AI", "NotebookLM",
    "Midjourney", "Stable Diffusion 新機能", "Suno AI", "Runway AI",
    # AI業界の動向
    "OpenAI", "Anthropic", "Google AI", "Apple AI",
    "Meta AI", "NVIDIA AI", "Microsoft AI",
    # 話題になりやすいトピック
    "生成AI 新サービス", "AIエージェント", "AI 無料ツール",
    "AI 仕事効率化", "AI副業", "AIアプリ 話題",
]
MAX_ARTICLES = 7

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# MC名（固定）
MC_A = "タケシ"   # メインMC（男性）
MC_B = "アイ"     # サブMC（女性）

# Edge-TTS 音声
TTS_VOICE_A = "ja-JP-KeitaNeural"   # 男性（タケシ）
TTS_VOICE_B = "ja-JP-NanamiNeural"  # 女性（アイ）
TTS_RATE_A = "+15%"
TTS_RATE_B = "+10%"

# Podcast メタデータ
PODCAST_TITLE = "あさイチAI"
PODCAST_DESCRIPTION = "AIの最新ニュースを毎朝タケシとアイの2人がわかりやすく解説するPodcast"
PODCAST_AUTHOR = "あさイチAI"
PODCAST_LANGUAGE = "ja"
PODCAST_CATEGORY = "Technology"
PODCAST_IMAGE = "artwork.jpg"

# GitHub Pages
GITHUB_PAGES_REPO_PATH = os.getenv("GITHUB_PAGES_REPO_PATH", "")
GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "")

# エピソード管理
MAX_EPISODES = 50
MAX_SCRIPT_CHARS = 4000
