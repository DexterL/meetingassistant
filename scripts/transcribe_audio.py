from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.asr import ASRError, format_transcript, get_asr_client
from app.server import AUDIO_DIR, TRANSCRIPTS_DIR, meeting_id_from_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe a local meeting audio file.")
    parser.add_argument("audio", help="Audio filename in data/audio, meeting_id, or absolute path.")
    return parser.parse_args()


def resolve_audio(value: str) -> Path:
    candidate = Path(value)
    if candidate.exists():
        return candidate

    by_name = AUDIO_DIR / value
    if by_name.exists():
        return by_name

    for path in AUDIO_DIR.iterdir():
        if path.is_file() and meeting_id_from_name(path.name) == value:
            return path

    raise FileNotFoundError(f"Audio not found: {value}")


def main() -> None:
    args = parse_args()
    audio_path = resolve_audio(args.audio)
    meeting_id = meeting_id_from_name(audio_path.name)
    transcript_path = TRANSCRIPTS_DIR / f"{meeting_id}.md"

    try:
        result = get_asr_client().transcribe(audio_path)
    except ASRError as exc:
        raise SystemExit(f"ASR failed: {exc}") from exc

    transcript_path.write_text(format_transcript(audio_path.name, result), encoding="utf-8")
    print(transcript_path)


if __name__ == "__main__":
    main()
