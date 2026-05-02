"""Edge-TTSで音声を生成"""
import asyncio
import logging
import tempfile
from pathlib import Path
from pydub import AudioSegment

import edge_tts

from config import TTS_VOICE_A, TTS_VOICE_B, TTS_RATE_A, TTS_RATE_B, AUDIO_DIR, MC_A, MC_B, PRONUNCIATION_FIXES

logger = logging.getLogger(__name__)

VOICE_MAP = {
    MC_A: (TTS_VOICE_A, TTS_RATE_A),
    MC_B: (TTS_VOICE_B, TTS_RATE_B),
}

SILENCE_BETWEEN = 400  # セリフ間の無音（ミリ秒）


def fix_pronunciation(text: str) -> str:
    """発音辞書に従ってTTSが誤読しやすい表記を補正"""
    for original, fixed in PRONUNCIATION_FIXES.items():
        text = text.replace(original, fixed)
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
            logger.debug(f"TTS [{speaker}] line {i}")
        except Exception as e:
            logger.warning(f"TTS failed line {i}: {e}")
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
    logger.info(f"Audio combined: {duration_sec:.1f}s → {output_path}")
    return duration_sec


def generate_audio(script: list[tuple[str, str]], filename: str) -> tuple[str, float]:
    """台本から音声ファイルを生成。(出力パス, 秒数)を返す"""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(AUDIO_DIR / filename)

    with tempfile.TemporaryDirectory() as temp_dir:
        audio_paths = asyncio.run(generate_all_lines(script, temp_dir))
        if not audio_paths:
            raise ValueError("No audio files were generated")
        duration = combine_audio(audio_paths, output_path)

    return output_path, duration


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_script = [
        (MC_A, "AI朝刊へようこそ!"),
        (MC_B, "今日のAIニュースをお届けします!"),
        (MC_A, "それでは、いきましょう。"),
    ]
    path, dur = generate_audio(test_script, "test_episode.mp3")
    print(f"Generated: {path} ({dur:.1f}s)")
