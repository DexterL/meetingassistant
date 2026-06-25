from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from app.asr import load_config


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class LLMResult:
    model: str
    content: str


def extract_original_transcript(markdown: str) -> str:
    marker = "## 原始转写"
    next_marker = "\n## "
    if marker not in markdown:
        return markdown.strip()

    content = markdown.split(marker, 1)[1]
    if next_marker in content:
        content = content.split(next_marker, 1)[0]
    return content.strip()


def format_cleaned_record(source_name: str, model: str, cleaned_text: str) -> str:
    return "\n".join(
        [
            "# 会议记录",
            "",
            f"来源转写稿：{source_name}",
            f"整理模型：{model}",
            "",
            "## 整理内容",
            "",
            cleaned_text.strip(),
            "",
        ]
    )


class LLMClient:
    def clean_transcript(self, transcript_markdown: str) -> LLMResult:
        raise NotImplementedError


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = str(config.get("base_url", "http://127.0.0.1:11434/v1")).rstrip("/")
        self.api_key = str(config.get("api_key", "local"))
        self.model = str(config.get("model", "qwen2.5:7b"))
        self.temperature = float(config.get("temperature", 0.2))
        self.max_tokens = int(config.get("max_tokens", 4096))

    def clean_transcript(self, transcript_markdown: str) -> LLMResult:
        original = extract_original_transcript(transcript_markdown)
        if not original:
            raise LLMError("Transcript has no content to clean.")

        prompt = "\n".join(
            [
                "你是会议记录整理助手。请将下面的 ASR 原始转写整理为可读的会议记录。",
                "",
                "要求：",
                "1. 只整理表达，不新增事实。",
                "2. 删除明显语气词、重复、口头禅和无意义停顿。",
                "3. 修正明显口误；不确定的内容保留原词。",
                "4. 保留关键数字、名称、日期、项目名和术语。",
                "5. 保持会议讨论顺序。",
                "6. 输出 Markdown 正文，不要解释你的处理过程。",
                "",
                "ASR 原始转写：",
                original,
            ]
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你只根据用户提供的会议转写内容进行整理。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        try:
            data = self._post_json(f"{self.base_url}/chat/completions", payload)
            content = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM response format is not compatible with OpenAI chat completions.") from exc

        return LLMResult(model=self.model, content=content)

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        opener = build_opener(ProxyHandler({}))
        try:
            with opener.open(request, timeout=300) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"LLM service returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise LLMError(f"LLM service is unavailable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LLMError("LLM service request timed out.") from exc


def get_llm_client() -> LLMClient:
    config = load_config().get("llm", {})
    provider = str(config.get("provider", "openai_compatible"))
    if provider != "openai_compatible":
        raise LLMError(f"Unsupported LLM provider: {provider}")
    return OpenAICompatibleLLMClient(config)


def clean_transcript_file(transcript_path: Path, output_path: Path) -> tuple[str, LLMResult]:
    transcript = transcript_path.read_text(encoding="utf-8")
    result = get_llm_client().clean_transcript(transcript)
    record = format_cleaned_record(transcript_path.name, result.model, result.content)
    output_path.write_text(record, encoding="utf-8")
    return record, result
