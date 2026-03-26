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

# Google News (英語)
NEWS_QUERIES = [
    # AI tools & services
    "ChatGPT new feature", "Claude AI update", "Gemini AI update",
    "Copilot update", "Perplexity AI", "NotebookLM",
    "Midjourney", "Stable Diffusion update", "Suno AI", "Runway AI",
    # AI industry
    "OpenAI", "Anthropic", "Google AI", "Apple AI",
    "Meta AI", "NVIDIA AI", "Microsoft AI",
    # Trending topics
    "generative AI launch", "AI agent", "free AI tool",
    "AI productivity", "AI startup funding", "AI app trending",
]
MAX_ARTICLES = 7

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# MC名（固定）
MC_A = "Alex"    # メインMC（男性）
MC_B = "Sara"    # サブMC（女性）

# Edge-TTS 音声（英語）
TTS_VOICE_A = "en-US-GuyNeural"     # 男性（Alex）
TTS_VOICE_B = "en-US-JennyNeural"   # 女性（Sara）
TTS_RATE_A = "+10%"
TTS_RATE_B = "+5%"

# Podcast メタデータ（Spotify for Podcasters と一致させる）
PODCAST_TITLE = "AI Morning Brief"
PODCAST_DESCRIPTION = "Your daily AI news briefing. Alex and Sara break down the latest updates on ChatGPT, Claude, image generation AI, and trending AI tools and services every morning."
PODCAST_AUTHOR = "Believe"
PODCAST_EMAIL = "believe.spotify33@gmail.com"
PODCAST_LANGUAGE = "en"
PODCAST_CATEGORY = "Technology"
PODCAST_IMAGE = "artwork.jpg"

# GitHub Pages
GITHUB_PAGES_REPO_PATH = os.getenv("GITHUB_PAGES_REPO_PATH", "")
GITHUB_PAGES_URL = os.getenv("GITHUB_PAGES_URL", "")

# エピソード管理
MAX_EPISODES = 50
MAX_SCRIPT_CHARS = 4000
