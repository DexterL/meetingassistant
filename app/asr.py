from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "app.json"


class ASRError(RuntimeError):
    pass


@dataclass(frozen=True)
class ASRSegment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass(frozen=True)
class ASRResult:
    model: str
    language: str | None
    segments: list[ASRSegment]


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_transcript(audio_name: str, result: ASRResult) -> str:
    lines = [
        "# 会议原始转写稿",
        "",
        f"音频文件：{audio_name}",
        f"识别模型：{result.model}",
    ]
    if result.language:
        lines.append(f"识别语言：{result.language}")
    lines.extend(["", "## 原始转写", ""])

    for segment in result.segments:
        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        speaker = f"{segment.speaker}：" if segment.speaker else ""
        lines.append(f"[{start} - {end}] {speaker}{segment.text.strip()}")

    lines.append("")
    return "\n".join(lines)


class ASRClient:
    def transcribe(self, audio_path: Path) -> ASRResult:
        raise NotImplementedError


class FasterWhisperASRClient(ASRClient):
    def __init__(self, config: dict[str, Any]) -> None:
        self.model_name = str(config.get("model", "base"))
        self.device = str(config.get("device", "auto"))
        self.compute_type = str(config.get("compute_type", "default"))
        self.language = config.get("language", "zh")
        self.beam_size = int(config.get("beam_size", 5))
        self.best_of = int(config.get("best_of", 5))
        self.temperature = config.get("temperature", 0)
        self.vad_filter = bool(config.get("vad_filter", True))
        self.vad_parameters = config.get("vad_parameters")
        self.initial_prompt = config.get("initial_prompt")
        self.condition_on_previous_text = bool(config.get("condition_on_previous_text", True))

    def transcribe(self, audio_path: Path) -> ASRResult:
        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError as exc:
            raise ASRError(
                "faster-whisper is not installed. Install local ASR dependencies before running transcription."
            ) from exc

        kwargs: dict[str, Any] = {"device": self.device}
        if self.compute_type != "default":
            kwargs["compute_type"] = self.compute_type

        try:
            model = WhisperModel(self.model_name, **kwargs)
            transcribe_kwargs: dict[str, Any] = {
                "language": self.language,
                "beam_size": self.beam_size,
                "best_of": self.best_of,
                "temperature": self.temperature,
                "vad_filter": self.vad_filter,
                "condition_on_previous_text": self.condition_on_previous_text,
            }
            if self.vad_parameters:
                transcribe_kwargs["vad_parameters"] = self.vad_parameters
            if self.initial_prompt:
                transcribe_kwargs["initial_prompt"] = self.initial_prompt

            segments_iter, info = model.transcribe(str(audio_path), **transcribe_kwargs)
            segments = [
                ASRSegment(start=float(segment.start), end=float(segment.end), text=segment.text)
                for segment in segments_iter
            ]
        except Exception as exc:  # The ASR backend raises several dependency/runtime-specific errors.
            raise ASRError(str(exc)) from exc

        return ASRResult(
            model=f"faster-whisper:{self.model_name}",
            language=getattr(info, "language", self.language),
            segments=segments,
        )


def get_asr_client() -> ASRClient:
    config = load_config().get("asr", {})
    provider = str(config.get("provider", "faster_whisper"))
    if provider != "faster_whisper":
        raise ASRError(f"Unsupported ASR provider: {provider}")
    return FasterWhisperASRClient(config)
