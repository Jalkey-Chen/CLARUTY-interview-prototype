"""HeyGen Video Agent helpers for the CLARITY Stage 5 video pipeline.

This module intentionally uses only the Python standard library and does not
import Streamlit, so the experiment notebook can use it directly and the
source-text helpers can be tested without network access or API keys.
"""

from __future__ import annotations

import difflib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


HEYGEN_API_BASE = "https://api.heygen.com"
HEYGEN_PROMPT_MAX_CHARS = 10_000
HEYGEN_REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_WORDS_PER_MINUTE = 140


class HeyGenError(RuntimeError):
    """Raised when a HeyGen request fails or a video render does not complete."""


def heygen_request(
    api_key: str,
    method: str,
    path: str,
    payload: dict | None = None,
    query: dict | None = None,
) -> dict:
    """Send one authenticated request to the HeyGen API.

    Args:
        api_key: HeyGen API key sent as the `X-Api-Key` header.
        method: HTTP method, such as "GET" or "POST".
        path: API path starting with `/v3/`.
        payload: Optional JSON body for POST requests.
        query: Optional query-string parameters. `None` values are dropped.

    Returns:
        The parsed JSON response object.

    CLARITY pipeline role:
        Centralizes HeyGen authentication and error reporting so every Stage 5
        call fails loudly with the HTTP status and response body instead of
        silently producing an empty video record.
    """
    if not api_key:
        raise HeyGenError("HEYGEN_API_KEY is not configured.")

    url = HEYGEN_API_BASE + path
    if query:
        clean_query = {key: value for key, value in query.items() if value is not None}
        if clean_query:
            url += "?" + urllib.parse.urlencode(clean_query)

    headers = {
        "X-Api-Key": api_key,
        "Accept": "application/json",
        "User-Agent": "clarity-pipeline/0.1",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(
            request, timeout=HEYGEN_REQUEST_TIMEOUT_SECONDS
        ) as response:
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        raise HeyGenError(
            f"HeyGen {method} {path} failed with HTTP {exc.code}: {error_text}"
        ) from exc
    except urllib.error.URLError as exc:
        raise HeyGenError(f"HeyGen {method} {path} failed: {exc.reason}") from exc

    data = json.loads(response_text)
    if not isinstance(data, dict):
        raise HeyGenError(f"HeyGen {method} {path} returned a non-object response.")
    return data


def list_voices(
    api_key: str,
    language: str | None = None,
    gender: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """List public HeyGen voices, optionally filtered by language and gender.

    Args:
        api_key: HeyGen API key.
        language: Voice language filter, such as "English" or "Spanish".
        gender: Optional "male" or "female" filter.
        limit: Number of voices to return (1-100).

    Returns:
        A list of voice objects containing `voice_id`, `name`, `language`,
        `gender`, and `preview_audio_url`.

    CLARITY pipeline role:
        Lets the researcher pin one reviewed voice per explanation version,
        including a Spanish-language voice for the Spanish script.
    """
    response = heygen_request(
        api_key,
        "GET",
        "/v3/voices",
        query={"language": language, "gender": gender, "limit": limit},
    )
    data = response.get("data", [])
    if isinstance(data, dict):
        data = data.get("voices") or data.get("items") or []
    return data


def build_video_agent_payload(
    prompt: str,
    voice_id: str | None = None,
    style_id: str | None = None,
    orientation: str = "landscape",
    incognito_mode: bool = True,
    visibility: str = "private",
    callback_id: str | None = None,
) -> dict:
    """Build a Video Agent request body for a voice-over-only CLARITY video.

    Args:
        prompt: Fully rendered Video Agent prompt.
        voice_id: Optional pinned narration voice.
        style_id: Optional Video Agent style ID for consistent visuals.
        orientation: "landscape" or "portrait".
        incognito_mode: Disables HeyGen memory injection and extraction.
        visibility: Session visibility; "private" keeps it owner-only.
        callback_id: Optional caller-defined ID, useful for tracing versions.

    Returns:
        JSON-serializable request body for `POST /v3/video-agents`.

    CLARITY pipeline role:
        `avatar_id` is deliberately never sent. HeyGen documents that
        avatar-free, voice-over-only videos require omitting the avatar and
        stating "no avatar" in the prompt, which supports the no-clinician
        visual rule.
    """
    if not prompt or len(prompt) > HEYGEN_PROMPT_MAX_CHARS:
        raise HeyGenError(
            f"Video Agent prompt must be 1-{HEYGEN_PROMPT_MAX_CHARS:,} characters; "
            f"got {len(prompt):,}."
        )

    payload: dict[str, Any] = {
        "prompt": prompt,
        "mode": "generate",
        "orientation": orientation,
        "incognito_mode": incognito_mode,
        "visibility": visibility,
    }
    if voice_id:
        payload["voice_id"] = voice_id
    if style_id:
        payload["style_id"] = style_id
    if callback_id:
        payload["callback_id"] = callback_id
    return payload


def create_video_agent_session(api_key: str, payload: dict) -> dict:
    """Submit one Video Agent generation request.

    Args:
        api_key: HeyGen API key.
        payload: Request body from `build_video_agent_payload`.

    Returns:
        Session data containing `session_id`, `status`, and `video_id`.

    CLARITY pipeline role:
        Starts the asynchronous render for one verified explanation version.
    """
    return heygen_request(api_key, "POST", "/v3/video-agents", payload=payload)["data"]


def get_video_agent_session(api_key: str, session_id: str) -> dict:
    """Return the current Video Agent session status and assigned video ID."""
    return heygen_request(api_key, "GET", f"/v3/video-agents/{session_id}")["data"]


def get_video(api_key: str, video_id: str) -> dict:
    """Return the current render status and download URLs for one video."""
    return heygen_request(api_key, "GET", f"/v3/videos/{video_id}")["data"]


def wait_for_video(
    api_key: str,
    session_id: str,
    poll_interval_seconds: int = 60,
    timeout_seconds: int = 60 * 60,
    log: Callable[[str], None] = print,
) -> dict:
    """Poll a Video Agent session until its video completes or fails.

    Args:
        api_key: HeyGen API key.
        session_id: Session ID returned by `create_video_agent_session`.
        poll_interval_seconds: Delay between status checks.
        timeout_seconds: Maximum total wait before raising.
        log: Function used to report status changes.

    Returns:
        The completed video object, including `video_url` and `subtitle_url`.

    CLARITY pipeline role:
        HeyGen renders take roughly 5-10x the video length, so Stage 5 submits
        every version first and then waits here, instead of blocking on each
        version before submitting the next.
    """
    deadline = time.monotonic() + timeout_seconds
    last_status = None
    while True:
        session = get_video_agent_session(api_key, session_id)
        if session.get("status") == "failed":
            raise HeyGenError(f"Video Agent session {session_id} failed: {session}")

        video_id = session.get("video_id")
        if video_id:
            video = get_video(api_key, video_id)
            status = f"video {video_id}: {video.get('status')}"
            if video.get("status") == "completed":
                log(f"[{session_id}] {status}")
                return video
            if video.get("status") == "failed":
                raise HeyGenError(
                    f"Video {video_id} failed: {video.get('failure_code')} - "
                    f"{video.get('failure_message')}"
                )
        else:
            status = f"session: {session.get('status')}"

        if status != last_status:
            log(f"[{session_id}] {status}")
            last_status = status
        if time.monotonic() >= deadline:
            raise HeyGenError(
                f"Timed out after {timeout_seconds}s waiting for session {session_id}; "
                "the render may still finish. Re-run the wait step later."
            )
        time.sleep(poll_interval_seconds)


def download_file(url: str, destination: Path) -> Path:
    """Download a presigned HeyGen file URL to disk.

    Args:
        url: Presigned download URL from a completed video object.
        destination: Local output path.

    Returns:
        The destination path.

    CLARITY pipeline role:
        HeyGen download URLs are presigned and expire, so completed videos and
        subtitles are copied into the ignored outputs folder immediately. The
        API key is not sent to the file host.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "clarity-pipeline/0.1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        destination.write_bytes(response.read())
    return destination


def _normalize_label(line: str) -> str:
    """Strip markdown emphasis and heading markers from a label line."""
    return line.strip().strip("*#_ ").strip()


def markdown_dialogue_to_video_source(markdown_text: str) -> str:
    """Convert a `scripts/*.md` Speaker dialogue into a scene-by-scene source.

    Args:
        markdown_text: Markdown script with `### Section` headings and
        `**Speaker N:** line` dialogue.

    Returns:
        Plain text in the same `Scene N: title` / `Voiceover:` layout produced
        by the Stage 3.5 packager. Speaker labels are removed because the
        HeyGen video uses one voice-over narrator. The `Prototype note`
        section is dropped because it is authoring metadata, not narration.

    CLARITY pipeline role:
        Lets the existing hand-written control script be used as a short,
        low-cost HeyGen test input before the full LLM pipeline has produced
        a reviewed Stage 3.5 source document.
    """
    scenes: list[tuple[str, list[str]]] = []
    skip_section = False
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## ") and not line.startswith("### "):
            skip_section = "prototype note" in line.lower()
            continue
        if line.startswith("### "):
            skip_section = False
            scenes.append((line[4:].strip(), []))
            continue
        if skip_section or not line or line.startswith("# ") or not scenes:
            continue
        speaker_match = re.match(r"^\*\*Speaker\s*\d+:\*\*\s*(.+)$", line)
        scenes[-1][1].append(speaker_match.group(1) if speaker_match else line)

    blocks = []
    for number, (title, lines) in enumerate(
        (scene for scene in scenes if scene[1]), start=1
    ):
        blocks.append(f"Scene {number}: {title}\nVoiceover:\n" + " ".join(lines))
    return "\n\n".join(blocks)


def extract_narration(video_source: str) -> str:
    """Extract only the spoken voice-over text from a scene-by-scene source.

    Args:
        video_source: Stage 3.5 packager output or the output of
        `markdown_dialogue_to_video_source`.

    Returns:
        Voice-over text in scene order, one scene per paragraph.

    CLARITY pipeline role:
        Provides the reference narration used to estimate video length and to
        check HeyGen's subtitles for paraphrasing after rendering.
    """
    section_labels = (
        "visual direction",
        "minimal on-screen text",
        "on-screen text",
        "video style brief",
        "global visual rules",
        "scene-by-scene video script",
    )
    paragraphs: list[str] = []
    current: list[str] | None = None
    for raw_line in video_source.splitlines():
        label = _normalize_label(raw_line)
        lower = label.lower()
        if lower.startswith("voiceover"):
            if current:
                paragraphs.append(" ".join(current))
            current = []
            remainder = label.split(":", 1)[1].strip() if ":" in label else ""
            if remainder:
                current.append(remainder)
            continue
        if re.match(r"^scene\s+\d+", lower) or lower.startswith(section_labels):
            if current:
                paragraphs.append(" ".join(current))
            current = None
            continue
        if current is not None and raw_line.strip():
            current.append(raw_line.strip())
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def estimate_duration_minutes(
    narration: str, words_per_minute: int = DEFAULT_WORDS_PER_MINUTE
) -> int:
    """Estimate spoken length in whole minutes from narration word count."""
    word_count = len(narration.split())
    return max(1, math.ceil(word_count / words_per_minute))


def srt_to_text(srt_text: str) -> str:
    """Return only the caption text from an SRT subtitle file."""
    lines = []
    for raw_line in srt_text.lstrip("﻿").splitlines():
        line = raw_line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        lines.append(line)
    return " ".join(lines)


def _words(text: str) -> list[str]:
    """Lowercase word tokens with punctuation removed, for narration diffing."""
    return re.findall(r"[\w']+", text.lower())


def compare_narration(
    expected: str, actual: str, pass_threshold: float = 0.95
) -> dict:
    """Compare approved narration against HeyGen's rendered subtitles.

    Args:
        expected: Approved voice-over narration.
        actual: Caption text extracted from the rendered video's SRT file.
        pass_threshold: Minimum word-sequence similarity for "pass".

    Returns:
        A report with the similarity ratio, a pass/needs_review status, and
        every inserted, deleted, or replaced word span.

    CLARITY pipeline role:
        HeyGen's Video Agent may smooth or rewrite pasted scripts. Because the
        narration was medically audited, any change to it, especially to
        uncertainty wording, must be surfaced for clinician review before the
        video is used.
    """
    expected_words = _words(expected)
    actual_words = _words(actual)
    matcher = difflib.SequenceMatcher(None, expected_words, actual_words, autojunk=False)
    differences = [
        {
            "change": tag,
            "approved": " ".join(expected_words[i1:i2]),
            "rendered": " ".join(actual_words[j1:j2]),
        }
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]
    ratio = round(matcher.ratio(), 4)
    return {
        "status": "pass" if ratio >= pass_threshold else "needs_review",
        "similarity": ratio,
        "pass_threshold": pass_threshold,
        "approved_word_count": len(expected_words),
        "rendered_word_count": len(actual_words),
        "differences": differences,
    }
