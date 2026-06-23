from __future__ import annotations

import json
import mimetypes
import re
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from app.asr import ASRError, format_transcript, get_asr_client


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
AUDIO_DIR = DATA_DIR / "audio"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SUMMARIES_DIR = DATA_DIR / "summaries"
WEB_DIR = PROJECT_ROOT / "web"

ALLOWED_AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav", ".flac"}

JOBS_LOCK = threading.Lock()
JOBS: dict[str, dict[str, object]] = {}


def ensure_directories() -> None:
    for path in (AUDIO_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR):
        path.mkdir(parents=True, exist_ok=True)


def json_bytes(payload: object) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name or f"audio-{int(time.time())}.m4a"


def meeting_id_from_name(filename: str) -> str:
    stem = Path(filename).stem.strip()
    stem = re.sub(r"[\\/:*?\"<>|]+", "_", stem)
    stem = re.sub(r"\s+", "-", stem)
    return stem or f"meeting-{int(time.time())}"


def unique_audio_path(filename: str) -> Path:
    clean_name = safe_filename(filename)
    target = AUDIO_DIR / clean_name
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return AUDIO_DIR / f"{stem}-{stamp}{suffix}"


def list_files(directory: Path, suffixes: set[str] | None = None) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in sorted(directory.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file() or path.name == ".gitkeep":
            continue
        if suffixes and path.suffix.lower() not in suffixes:
            continue
        stat = path.stat()
        items.append(
            {
                "name": path.name,
                "meeting_id": meeting_id_from_name(path.name),
                "size": stat.st_size,
                "updated_at": int(stat.st_mtime),
            }
        )
    return items


def transcript_exists(meeting_id: str) -> bool:
    return (TRANSCRIPTS_DIR / f"{meeting_id}.md").is_file()


def summary_exists(meeting_id: str) -> bool:
    return (SUMMARIES_DIR / f"{meeting_id}.md").is_file()


def get_job(meeting_id: str) -> dict[str, object] | None:
    with JOBS_LOCK:
        job = JOBS.get(meeting_id)
        return dict(job) if job else None


def set_job(meeting_id: str, **updates: object) -> dict[str, object]:
    with JOBS_LOCK:
        job = JOBS.setdefault(
            meeting_id,
            {
                "meeting_id": meeting_id,
                "state": "idle",
                "step": "等待",
                "progress": 0,
                "message": "",
                "started_at": None,
                "finished_at": None,
            },
        )
        job.update(updates)
        return dict(job)


def list_jobs() -> list[dict[str, object]]:
    with JOBS_LOCK:
        return [dict(job) for job in JOBS.values()]


def transcribe_in_background(meeting_id: str, audio: Path) -> None:
    set_job(
        meeting_id,
        state="running",
        step="语音识别中",
        progress=35,
        message="正在调用本地 ASR 模型识别音频。长音频在 CPU 上可能需要较久。",
    )
    try:
        result = get_asr_client().transcribe(audio)
        set_job(
            meeting_id,
            step="写入转写稿",
            progress=85,
            message=f"识别完成，正在保存 {len(result.segments)} 个片段。",
        )
        transcript = TRANSCRIPTS_DIR / f"{meeting_id}.md"
        transcript.write_text(format_transcript(audio.name, result), encoding="utf-8")
        set_job(
            meeting_id,
            state="succeeded",
            step="完成",
            progress=100,
            message=f"转写稿已生成：{transcript.name}",
            transcript=transcript.name,
            segments=len(result.segments),
            finished_at=int(time.time()),
        )
    except ASRError as exc:
        set_job(
            meeting_id,
            state="failed",
            step="失败",
            progress=100,
            message=str(exc),
            finished_at=int(time.time()),
        )
    except Exception as exc:  # Keep background failures visible to the UI.
        set_job(
            meeting_id,
            state="failed",
            step="失败",
            progress=100,
            message=f"Unexpected transcription failure: {exc}",
            finished_at=int(time.time()),
        )


def read_markdown(directory: Path, meeting_id: str) -> str | None:
    path = directory / f"{meeting_id}.md"
    if not path.exists() or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def write_placeholder_transcript(meeting_id: str, audio_name: str) -> Path:
    target = TRANSCRIPTS_DIR / f"{meeting_id}.md"
    if target.exists():
        return target

    target.write_text(
        "\n".join(
            [
                "# 会议转写与规整稿",
                "",
                f"音频文件：{audio_name}",
                "识别模型：待接入",
                "",
                "## 原始转写",
                "",
                "[待接入 ASR] 当前阶段已完成音频文件接收和本地文件流转，下一阶段接入语音识别后写入真实转写内容。",
                "",
                "## 规整记录",
                "",
                "[待接入 LLM] 当前阶段暂不生成规整内容。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return target


def write_placeholder_summary(meeting_id: str) -> Path:
    target = SUMMARIES_DIR / f"{meeting_id}.md"
    if target.exists():
        return target

    target.write_text(
        "\n".join(
            [
                "# 会议内容提要",
                "",
                "## 当前状态",
                "",
                "- 音频文件已进入本地处理目录。",
                "- ASR、文本规整和内容提要模型尚未接入。",
                "- 后续接入模型后，此文件将写入真实会议内容提要。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return target


class MeetingAssistantHandler(BaseHTTPRequestHandler):
    server_version = "MeetingAssistant/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_json({"status": "ok"})
            return
        if parsed.path == "/api/files":
            self.send_json(
                {
                    "audio": list_files(AUDIO_DIR, ALLOWED_AUDIO_EXTENSIONS),
                    "transcripts": list_files(TRANSCRIPTS_DIR, {".md"}),
                    "summaries": list_files(SUMMARIES_DIR, {".md"}),
                    "jobs": list_jobs(),
                }
            )
            return
        if parsed.path.startswith("/api/jobs/"):
            meeting_id = unquote(parsed.path.removeprefix("/api/jobs/"))
            job = get_job(meeting_id)
            if job is None:
                self.send_json(
                    {
                        "meeting_id": meeting_id,
                        "state": "succeeded" if transcript_exists(meeting_id) else "idle",
                        "step": "已有转写稿" if transcript_exists(meeting_id) else "等待",
                        "progress": 100 if transcript_exists(meeting_id) else 0,
                        "message": "转写稿已存在。" if transcript_exists(meeting_id) else "尚未开始转写。",
                        "transcript_exists": transcript_exists(meeting_id),
                        "summary_exists": summary_exists(meeting_id),
                    }
                )
                return
            job["transcript_exists"] = transcript_exists(meeting_id)
            job["summary_exists"] = summary_exists(meeting_id)
            self.send_json(job)
            return
        if parsed.path.startswith("/api/transcripts/"):
            meeting_id = unquote(parsed.path.removeprefix("/api/transcripts/"))
            self.send_markdown_response(read_markdown(TRANSCRIPTS_DIR, meeting_id))
            return
        if parsed.path.startswith("/api/summaries/"):
            meeting_id = unquote(parsed.path.removeprefix("/api/summaries/"))
            self.send_markdown_response(read_markdown(SUMMARIES_DIR, meeting_id))
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/audio":
            self.handle_audio_upload(parsed.query)
            return
        if parsed.path.startswith("/api/transcribe/"):
            meeting_id = unquote(parsed.path.removeprefix("/api/transcribe/"))
            self.handle_placeholder_transcribe(meeting_id)
            return
        if parsed.path.startswith("/api/process/"):
            meeting_id = unquote(parsed.path.removeprefix("/api/process/"))
            self.handle_placeholder_process(meeting_id)
            return
        self.send_error_json(HTTPStatus.NOT_FOUND, "Endpoint not found.")

    def handle_audio_upload(self, query: str) -> None:
        params = parse_qs(query)
        filename = params.get("filename", [""])[0]
        filename = safe_filename(unquote(filename))
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            self.send_error_json(
                HTTPStatus.BAD_REQUEST,
                f"Unsupported audio type: {extension or '(none)'}",
            )
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Upload body is empty.")
            return

        target = unique_audio_path(filename)
        remaining = length
        with target.open("wb") as output:
            while remaining > 0:
                chunk = self.rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                output.write(chunk)
                remaining -= len(chunk)

        if remaining:
            target.unlink(missing_ok=True)
            self.send_error_json(HTTPStatus.BAD_REQUEST, "Upload body ended unexpectedly.")
            return

        self.send_json(
            {
                "meeting_id": meeting_id_from_name(target.name),
                "name": target.name,
                "size": target.stat().st_size,
            },
            HTTPStatus.CREATED,
        )

    def handle_placeholder_transcribe(self, meeting_id: str) -> None:
        audio = self.find_audio(meeting_id)
        if audio is None:
            self.send_error_json(HTTPStatus.NOT_FOUND, "Audio file not found.")
            return
        current = get_job(meeting_id)
        if current and current.get("state") == "running":
            self.send_json(current, HTTPStatus.ACCEPTED)
            return

        job = set_job(
            meeting_id,
            state="queued",
            step="排队",
            progress=5,
            message="转写任务已创建。",
            started_at=int(time.time()),
            finished_at=None,
            transcript=None,
            segments=None,
        )
        thread = threading.Thread(target=transcribe_in_background, args=(meeting_id, audio), daemon=True)
        thread.start()
        self.send_json(job, HTTPStatus.ACCEPTED)

    def handle_placeholder_process(self, meeting_id: str) -> None:
        audio = self.find_audio(meeting_id)
        if audio is None:
            self.send_error_json(HTTPStatus.NOT_FOUND, "Audio file not found.")
            return
        transcript = write_placeholder_transcript(meeting_id, audio.name)
        summary = write_placeholder_summary(meeting_id)
        self.send_json(
            {
                "meeting_id": meeting_id,
                "transcript": transcript.name,
                "summary": summary.name,
                "status": "placeholder_created",
            }
        )

    def find_audio(self, meeting_id: str) -> Path | None:
        for path in AUDIO_DIR.iterdir():
            if path.is_file() and path.name != ".gitkeep" and meeting_id_from_name(path.name) == meeting_id:
                return path
        return None

    def serve_static(self, request_path: str) -> None:
        if request_path in ("", "/"):
            target = WEB_DIR / "index.html"
        else:
            relative = request_path.lstrip("/")
            target = (WEB_DIR / relative).resolve()
            if WEB_DIR.resolve() not in target.parents and target != WEB_DIR.resolve():
                self.send_error(HTTPStatus.FORBIDDEN)
                return

        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_markdown_response(self, content: str | None) -> None:
        if content is None:
            self.send_error_json(HTTPStatus.NOT_FOUND, "Markdown file not found.")
            return
        self.send_json({"content": content})

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"error": message}, status)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.log_date_time_string()} {self.address_string()} {format % args}")


def main() -> None:
    ensure_directories()
    server = ThreadingHTTPServer(("127.0.0.1", 8765), MeetingAssistantHandler)
    print("Meeting Assistant running at http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()
