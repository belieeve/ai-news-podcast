"""Edge-TTSで音声を生成"""
import asyncio
import logging
import tempfile
from pathlib import Path
from pydub import AudioSegment

import edge_tts

from config import TTS_VOICE_A, TTS_VOICE_B, TTS_RATE_A, TTS_RATE_B, AUDIO_DIR

logger = logging.getLogger(__name__)

VOICE_MAP = {
    "タケシ": (TTS_VOICE_A, TTS_RATE_A),
    "アイ": (TTS_VOICE_B, TTS_RATE_B),
}

SILENCE_BETWEEN = 400  # セリフ間の無音（ミリ秒）

# Edge-TTSの日本語発音補正（完全一致のみ）
PRONUNCIATION_FIXES = {
    # 挨拶系
    "こんにちは": "こんにちわ",
    "こんばんは": "こんばんわ",
    # 記号の読み
    "〜": "から",
    "＆": "アンド",
    "×": "かける",

    # === 発音補正（漢字→カタカナ） ===
    "興味津々": "キョウミシンシン",

    # === AI・テクノロジー用語 ===
    "AI": "エーアイ",
    "LLM": "エルエルエム",
    "API": "エーピーアイ",
    "GPU": "ジーピーユー",
    "CPU": "シーピーユー",
    "TPU": "ティーピーユー",
    "NPU": "エヌピーユー",
    "IoT": "アイオーティー",
    "DX": "ディーエックス",
    "SaaS": "サース",
    "PaaS": "パース",
    "IaaS": "イアース",
    "UI": "ユーアイ",
    "UX": "ユーエックス",
    "OSS": "オーエスエス",
    "RAG": "ラグ",
    "AGI": "エージーアイ",
    "ASI": "エーエスアイ",
    "NLP": "エヌエルピー",
    "CV": "シーブイ",
    "GAN": "ギャン",
    "VAE": "ブイエーイー",
    "MLOps": "エムエルオプス",
    "LLMOps": "エルエルエムオプス",
    "RLHF": "アールエルエイチエフ",
    "LoRA": "ローラ",
    "BERT": "バート",
    "GPT": "ジーピーティー",
    "VR": "ブイアール",
    "AR": "エーアール",
    "XR": "エックスアール",
    "MR": "エムアール",
    "5G": "ファイブジー",
    "6G": "シックスジー",
    "Web3": "ウェブスリー",
    "NFT": "エヌエフティー",
    "DAO": "ダオ",
    "EV": "イーブイ",
    "RPA": "アールピーエー",
    "ETL": "イーティーエル",
    "SDK": "エスディーケー",
    "IDE": "アイディーイー",
    "GDPR": "ジーディーピーアール",
    "KPI": "ケーピーアイ",
    "ROI": "アールオーアイ",
    "B2B": "ビートゥービー",
    "B2C": "ビートゥーシー",
    "SLA": "エスエルエー",

    # === 企業名・サービス名 ===
    "OpenAI": "オープンエーアイ",
    "DeepMind": "ディープマインド",
    "Anthropic": "アンソロピック",
    "NVIDIA": "エヌビディア",
    "Hugging Face": "ハギングフェイス",
    "Stability AI": "スタビリティエーアイ",
    "xAI": "エックスエーアイ",
    "Gemini": "ジェミニ",
    "Claude": "クロード",
    "Copilot": "コパイロット",
    "ChatGPT": "チャットジーピーティー",
    "Midjourney": "ミッドジャーニー",
    "DALL-E": "ダリー",
    "Sora": "ソラ",
    "Llama": "ラマ",
    "Mistral": "ミストラル",

    # === 役職・組織 ===
    "CEO": "シーイーオー",
    "CTO": "シーティーオー",
    "CFO": "シーエフオー",
    "COO": "シーオーオー",
    "CIO": "シーアイオー",
    "VP": "ブイピー",
    "MIT": "エムアイティー",
    "IEEE": "アイトリプルイー",

    # === 単位・数値表現 ===
    "TB": "テラバイト",
    "GB": "ギガバイト",
    "MB": "メガバイト",
}


def fix_pronunciation(text: str) -> str:
    """Edge-TTSの発音問題を補正（長い語から先にマッチ）"""
    sorted_fixes = sorted(PRONUNCIATION_FIXES.items(), key=lambda x: len(x[0]), reverse=True)
    for wrong, correct in sorted_fixes:
        text = text.replace(wrong, correct)
    return text


async def synthesize_line(text: str, voice: str, rate: str, output_path: str):
    """1行のセリフを音声化"""
    text = fix_pronunciation(text)
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(output_path)


async def generate_all_lines(script: list[tuple[str, str]], temp_dir: str) -> list[str]:
    """全セリフを音声化して一時ファイルパスのリストを返す"""
    paths = []
    for i, (speaker, text) in enumerate(script):
        voice, rate = VOICE_MAP.get(speaker, (TTS_VOICE_A, TTS_RATE_A))
        path = f"{temp_dir}/line_{i:04d}.mp3"
        try:
            await synthesize_line(text, voice, rate, path)
            paths.append(path)
            logger.debug(f"音声生成 [{speaker}] line {i}")
        except Exception as e:
            logger.warning(f"音声生成失敗 line {i}: {e}")
    return paths


def combine_audio(audio_paths: list[str], output_path: str):
    """複数の音声ファイルを結合"""
    silence = AudioSegment.silent(duration=SILENCE_BETWEEN)
    combined = AudioSegment.empty()

    for i, path in enumerate(audio_paths):
        segment = AudioSegment.from_mp3(path)
        if i > 0:
            combined += silence
        combined += segment

    combined.export(output_path, format="mp3", bitrate="128k")
    duration_sec = len(combined) / 1000
    logger.info(f"音声結合完了: {duration_sec:.1f}秒 → {output_path}")
    return duration_sec


def generate_audio(script: list[tuple[str, str]], filename: str) -> tuple[str, float]:
    """台本から音声ファイルを生成。(出力パス, 秒数)を返す"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(AUDIO_DIR / filename)

    with tempfile.TemporaryDirectory() as temp_dir:
        audio_paths = asyncio.run(generate_all_lines(script, temp_dir))
        if not audio_paths:
            raise ValueError("音声ファイルが1つも生成されませんでした")
        duration = combine_audio(audio_paths, output_path)

    return output_path, duration


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # テスト
    test_script = [
        ("タケシ", "こんにちは、AI News Dailyの時間です。"),
        ("アイ", "今日もAIの最新ニュースをお届けしますよ！"),
        ("タケシ", "早速いきましょう。"),
    ]
    path, dur = generate_audio(test_script, "test_episode.mp3")
    print(f"生成完了: {path} ({dur:.1f}秒)")
