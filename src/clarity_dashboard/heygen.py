"""HeyGen Video Agent helpers for the CLARITY Stage 5 video pipeline.

This module uses the Python standard library (plus `fpdf2`, imported only when
a visual-directions PDF is built, and `imageio-ffmpeg`, imported only when
frames are extracted for the visual check) and does not import Streamlit, so the
experiment notebook can use it directly and the source-text helpers can be
tested without network access or API keys.
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
# Measured on rendered Video Agent narration: 157 words in 58 s, 655 words in 255 s.
DEFAULT_WORDS_PER_MINUTE = 155


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
    files: list[dict] | None = None,
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
        files: Optional attachments, such as a base64 visual-directions PDF.

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
    if files:
        payload["files"] = files
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


def send_video_agent_message(
    api_key: str,
    session_id: str,
    message: str | None = None,
    voice_id: str | None = None,
    edit_plan: list[dict] | None = None,
) -> dict:
    """Send a follow-up revision request to an existing Video Agent session.

    Args:
        api_key: HeyGen API key.
        session_id: Session ID of a previously generated video.
        message: Plain-language revision, such as a background music change.
        voice_id: Optional voice override.
        edit_plan: Optional scene edits built with `build_scene_edit`; only
        the named scenes are revised.

    Returns:
        Response data containing `session_id`, `run_id`, and the draft
        `video_id`.

    CLARITY pipeline role:
        Lets a reviewer fix one production detail, such as music or a scene
        with unsupported on-screen text, while the agent keeps the rest of
        the approved video.
    """
    if not message and not edit_plan:
        raise HeyGenError("Provide a message or an edit_plan.")
    payload: dict[str, Any] = {}
    if message:
        payload["message"] = message
    if edit_plan:
        payload["edit_plan"] = edit_plan
    if voice_id:
        payload["voice_id"] = voice_id
    return heygen_request(api_key, "POST", f"/v3/video-agents/{session_id}", payload=payload)["data"]


def get_video_scenes(api_key: str, video_id: str) -> dict:
    """Return a completed Video Agent video's scenes and its `edit_version`.

    Each scene has an `id`, its `script` (narration), `background`, and
    `elements`. Scene IDs change on every new draft, so read them fresh from
    the video being edited.
    """
    return heygen_request(api_key, "GET", f"/v3/videos/{video_id}/scenes")["data"]


def build_scene_edit(scene_id: str, text: str, snapshot_video_id: str, edit_version: str) -> dict:
    """Build one `edit_plan` item for `send_video_agent_message`."""
    return {
        "scene_id": scene_id,
        "text": text,
        "scene_snapshot_video_id": snapshot_video_id,
        "edit_version": edit_version,
    }


def get_video_agent_session(api_key: str, session_id: str) -> dict:
    """Return the current Video Agent session status and assigned video ID."""
    return heygen_request(api_key, "GET", f"/v3/video-agents/{session_id}")["data"]


def get_video(api_key: str, video_id: str) -> dict:
    """Return the current render status and download URLs for one video."""
    return heygen_request(api_key, "GET", f"/v3/videos/{video_id}")["data"]


def awaiting_draft_approval(session: dict) -> str | None:
    """Return the draft resource ID when the agent is paused for draft review.

    After scene edits, the Video Agent can post a draft preview and ask
    "Ready to go?" instead of rendering. The session then stays
    `generating` with a `pending` video until someone replies.
    """
    messages = session.get("messages") or []
    if not messages:
        return None
    latest = messages[0]
    if latest.get("role") != "model":
        return None
    drafts = [rid for rid in latest.get("resource_ids") or [] if str(rid).startswith("draft_")]
    return drafts[0] if drafts else None


def wait_for_video(
    api_key: str,
    session_id: str,
    poll_interval_seconds: int = 60,
    timeout_seconds: int = 60 * 60,
    log: Callable[[str], None] = print,
    previous_video_id: str | None = None,
    on_draft_ready: Callable[[str], bool] | None = None,
) -> dict:
    """Poll a Video Agent session until its video completes or fails.

    Args:
        api_key: HeyGen API key.
        session_id: Session ID returned by `create_video_agent_session`.
        poll_interval_seconds: Delay between status checks.
        timeout_seconds: Maximum total wait before raising.
        log: Function used to report status changes.
        previous_video_id: After a revision request, the already-completed
        video ID to ignore until the session assigns a new one.
        on_draft_ready: Called once with the draft video ID when the agent
        pauses for draft review (common after scene edits). Return True after
        checking the draft to send approval and start the final render;
        return False to stop waiting and raise.

    Returns:
        The completed video object, including `video_url` and `subtitle_url`.

    CLARITY pipeline role:
        HeyGen renders take roughly 5-10x the video length, so Stage 5 submits
        every version first and then waits here, instead of blocking on each
        version before submitting the next.
    """
    deadline = time.monotonic() + timeout_seconds
    last_status = None
    handled_drafts: set[str] = set()
    while True:
        session = get_video_agent_session(api_key, session_id)
        draft_id = awaiting_draft_approval(session)
        if draft_id and draft_id not in handled_drafts:
            handled_drafts.add(draft_id)
            log(f"[{session_id}] agent is waiting for draft approval ({draft_id})")
            if on_draft_ready is None or not on_draft_ready(session.get("video_id") or ""):
                raise HeyGenError(
                    f"Session {session_id} is waiting for draft approval ({draft_id}); "
                    "review the draft, then approve it with send_video_agent_message."
                )
            send_video_agent_message(
                api_key,
                session_id,
                message="The draft is approved. Please proceed with the final video generation now, "
                "keeping every narration line exactly as in the draft.",
            )
            log(f"[{session_id}] draft approved; final render requested")
        if session.get("status") == "failed":
            # The session-level error can be misleading (for example
            # `free_tier_quota_exceeded` when the wallet balance is too low),
            # so report the video's own failure code when one exists.
            detail = session.get("error")
            failed_video_id = session.get("video_id")
            if failed_video_id and failed_video_id != previous_video_id:
                failed_video = get_video(api_key, failed_video_id)
                if failed_video.get("failure_code") or failed_video.get("failure_message"):
                    detail = f"{failed_video.get('failure_code')} - {failed_video.get('failure_message')}"
            if isinstance(detail, dict) and detail.get("code") == "free_tier_quota_exceeded":
                detail = (
                    f"{detail}. HeyGen also reports this when the wallet balance cannot cover the render; "
                    "check GET /v3/users/me before assuming a plan quota."
                )
            raise HeyGenError(f"Video Agent session {session_id} failed: {detail}")

        video_id = session.get("video_id")
        if video_id == previous_video_id:
            video_id = None
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


def structured_script_to_video_source(script: dict) -> str:
    """Convert a structured script JSON into a scene-by-scene video source.

    Args:
        script: Either a Stage 3 script (`script_sections` with `narration`
        and `visual_plan`) or a hand-revised scene script (`scenes` with
        `narration`, `visual_prompt`, and `minimal_on_screen_text`).

    Returns:
        Plain text in the `Scene N: title` / `Voiceover:` layout used by
        Stage 5. Narration is copied verbatim; checklists, fact lists, and
        audit fields are dropped because HeyGen should not see them.

    CLARITY pipeline role:
        Gives Stage 5 a deterministic path from an approved script to the
        video prompt, so no LLM rewrite happens between the audited narration
        and the narration HeyGen reads.
    """
    brief = []
    if script.get("overall_voice") or script.get("overall_tone"):
        brief.append(f"Narration voice: {script.get('overall_voice') or script.get('overall_tone')}")
    if script.get("visual_safety_constraints"):
        brief.append("Visual rules: " + " ".join(script["visual_safety_constraints"]))

    blocks = ["VIDEO STYLE BRIEF\n" + "\n".join(brief)] if brief else []
    scenes = script.get("scenes") or script.get("script_sections") or []
    for number, scene in enumerate(scenes, start=1):
        title = scene.get("section_label") or scene.get("section_title") or ""
        visual_plan = scene.get("visual_plan") or {}
        visual = scene.get("visual_prompt") or " ".join(
            part
            for part in (visual_plan.get("main_visual"), visual_plan.get("motion_or_transition"))
            if part
        )
        on_screen = scene.get("minimal_on_screen_text") or visual_plan.get(
            "minimal_on_screen_text"
        )
        lines = [f"Scene {number}: {title}".rstrip(": "), "Voiceover:", scene["narration"].strip()]
        if visual:
            lines += ["Visual direction:", visual.strip()]
        if on_screen:
            lines += ["Minimal on-screen text:", str(on_screen).strip()]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def limit_scenes(video_source: str, max_scenes: int | None) -> str:
    """Keep the preamble and only the first `max_scenes` scenes of a source.

    CLARITY pipeline role:
        Supports short, low-cost HeyGen test renders of the same approved
        script before committing credits to the full-length video.
    """
    if not max_scenes:
        return video_source
    parts = re.split(r"(?im)^(?=[ \t]*\**[ \t]*scene[ \t]+\d+)", video_source)
    preamble, scenes = parts[0], parts[1:]
    return (preamble + "".join(scenes[:max_scenes])).strip()


def parse_scenes(video_source: str) -> tuple[str, list[dict]]:
    """Split a scene-by-scene source into its preamble and structured scenes.

    Returns:
        A tuple of `(preamble, scenes)`, where each scene has `title`,
        `voiceover`, `visual`, and `on_screen` text.
    """
    fields = {
        "voiceover": "voiceover",
        "visual direction": "visual",
        "minimal on-screen text": "on_screen",
        "on-screen text": "on_screen",
    }
    preamble: list[str] = []
    scenes: list[dict] = []
    field = None
    for raw_line in video_source.splitlines():
        label = _normalize_label(raw_line)
        lower = label.lower()
        if re.match(r"^scene\s+\d+", lower):
            title = label.split(":", 1)[1].strip() if ":" in label else ""
            scenes.append({"title": title, "voiceover": [], "visual": [], "on_screen": []})
            field = None
            continue
        matched = next((key for key in fields if lower.startswith(key + ":") or lower == key), None)
        if scenes and matched:
            field = fields[matched]
            remainder = label.split(":", 1)[1].strip() if ":" in label else ""
            if remainder:
                scenes[-1][field].append(remainder)
            continue
        if not scenes:
            preamble.append(raw_line)
        elif field and raw_line.strip():
            scenes[-1][field].append(raw_line.strip())
    for scene in scenes:
        for key in ("voiceover", "visual", "on_screen"):
            scene[key] = " ".join(scene[key])
    return "\n".join(preamble).strip(), scenes


def narration_only_source(video_source: str) -> str:
    """Return the source with only scene titles and verbatim voiceover.

    CLARITY pipeline role:
        Keeps long scripts under the Video Agent prompt limit by moving visual
        directions into an attached PDF while the approved narration stays in
        the prompt itself, where the agent follows it most closely.
    """
    preamble, scenes = parse_scenes(video_source)
    blocks = [preamble] if preamble else []
    for number, scene in enumerate(scenes, start=1):
        heading = f"Scene {number}: {scene['title']}".rstrip(": ")
        blocks.append(f"{heading}\nVoiceover:\n{scene['voiceover']}")
    return "\n\n".join(blocks)


def _pdf_safe(text: str) -> str:
    """Map characters outside Latin-1 so the built-in PDF fonts can render them."""
    replacements = {"→": "->", "←": "<-", "—": "-", "–": "-",
                    "‘": "'", "’": "'", "“": '"', "”": '"',
                    "…": "...", "•": "-", "≥": ">=", "≤": "<=", "≠": "is not"}
    for original, replacement in replacements.items():
        text = text.replace(original, replacement)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def build_visual_directions_pdf(video_source: str, title: str) -> bytes:
    """Render every scene's visual direction and on-screen text as a PDF.

    Args:
        video_source: Scene-by-scene source with Visual direction lines.
        title: Heading printed at the top of the document.

    Returns:
        PDF bytes suitable for a Video Agent `files` base64 attachment.

    CLARITY pipeline role:
        Carries the production-only visual plan for long scripts. Each entry
        repeats the scene's first narration words so the agent can match the
        visual to the right spoken line.
    """
    from fpdf import FPDF

    _, scenes = parse_scenes(video_source)
    pdf = FPDF(format="Letter")

    def write(height: float, text: str) -> None:
        pdf.multi_cell(0, height, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 15)
    write(8, title)
    pdf.set_font("Helvetica", "", 10)
    write(
        5,
        "Production reference for the video team. Scene numbers match the scenes in the prompt. "
        "Do not read this document aloud and do not show it on screen.",
    )
    pdf.ln(3)
    for number, scene in enumerate(scenes, start=1):
        opening = " ".join(scene["voiceover"].split()[:12])
        pdf.set_font("Helvetica", "B", 11)
        write(6, f"Scene {number}: {scene['title']}".rstrip(": "))
        pdf.set_font("Helvetica", "I", 9)
        write(5, f'Narration starts: "{opening}..."')
        pdf.set_font("Helvetica", "", 10)
        if scene["visual"]:
            write(5, f"Visual: {scene['visual']}")
        if scene["on_screen"]:
            write(5, f"On-screen text: {scene['on_screen']}")
        pdf.ln(2)
    return bytes(pdf.output())


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


def estimate_duration_seconds(
    narration: str, words_per_minute: int = DEFAULT_WORDS_PER_MINUTE
) -> int:
    """Estimate spoken length in seconds from narration word count."""
    word_count = len(narration.split())
    return max(1, math.ceil(word_count * 60 / words_per_minute))


def format_target_duration(seconds: int) -> str:
    """Describe a target length for the prompt, such as "67-second" or "5-minute".

    CLARITY pipeline role:
        Short test renders are stated in seconds so HeyGen does not pad a
        one-minute narration out to a rounded-up whole minute.
    """
    if seconds < 120:
        return f"{seconds}-second"
    return f"{round(seconds / 60)}-minute"


def srt_to_text(srt_text: str) -> str:
    """Return only the caption text from an SRT subtitle file."""
    lines = []
    for raw_line in srt_text.lstrip("﻿").splitlines():
        line = raw_line.strip()
        if not line or line.isdigit() or "-->" in line:
            continue
        lines.append(line)
    return " ".join(lines)


def parse_srt(srt_text: str) -> list[tuple[float, float, str]]:
    """Return `(start_seconds, end_seconds, text)` for every SRT caption cue."""

    def seconds(stamp: str) -> float:
        hours, minutes, rest = stamp.strip().replace(",", ".").split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(rest)

    cues = []
    for block in srt_text.lstrip("﻿").strip().split("\n\n"):
        lines = [line for line in block.splitlines() if line.strip()]
        timing = next((line for line in lines if "-->" in line), None)
        if not timing:
            continue
        start, end = timing.split("-->")
        text = " ".join(lines[lines.index(timing) + 1 :])
        cues.append((seconds(start), seconds(end), text))
    return cues


def scene_time_ranges(scene_texts: list[str], srt_text: str) -> list[tuple[float, float]]:
    """Estimate when each scene is on screen from the rendered subtitles.

    Args:
        scene_texts: Each scene's narration, in order.
        srt_text: The rendered video's SRT subtitles.

    Returns:
        One `(start_seconds, end_seconds)` pair per scene.

    CLARITY pipeline role:
        Captions carry timing but not scene boundaries. Spreading each cue's
        duration over its words and then walking the scenes' word counts
        gives each scene's time range, so frames can be sampled while that
        scene's narration is being spoken.
    """
    word_times: list[float] = []
    for start, end, text in parse_srt(srt_text):
        words = _words(text)
        for index in range(len(words)):
            word_times.append(start + (end - start) * index / max(1, len(words)))
    if not word_times:
        raise ValueError("The subtitles contain no words.")
    ranges = []
    position = 0
    for text in scene_texts:
        count = max(1, len(_words(text)))
        first = min(position, len(word_times) - 1)
        last = min(position + count, len(word_times)) - 1
        end = word_times[last + 1] if last + 1 < len(word_times) else word_times[-1] + 1.0
        ranges.append((word_times[first], max(end, word_times[first] + 0.5)))
        position += count
    return ranges


def extract_frame(video_path: Path, seconds: float, destination: Path, width: int = 640) -> Path:
    """Save one JPEG frame from a video at the given time (requires imageio-ffmpeg)."""
    import subprocess

    import imageio_ffmpeg

    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
            "-ss", f"{seconds:.2f}", "-i", str(video_path),
            "-frames:v", "1", "-vf", f"scale={width}:-1", str(destination),
        ],
        check=True,
    )
    return destination


def detect_layout_changes(
    video_path: Path,
    fps: int = 2,
    active_level: float = 3.0,
    change_level: float = 5.5,
) -> list[float]:
    """Return the times, in seconds, where the picture changes to a new layout.

    Frames are sampled at `fps`, shrunk to 160x90 grayscale, and each frame is
    compared with the frame one second earlier (mean absolute pixel
    difference, 0-255). A run of frames above `active_level` is one change,
    and it counts as a new layout when its peak reaches `change_level`.

    Calibrated on Video Agent output: its soft crossfades on pale backgrounds
    do not trigger ffmpeg's built-in scene detection, while an element fading
    in within one layout typically scores 2-4 and a new full-screen layout
    scores above 5.5.
    """
    import subprocess

    import imageio_ffmpeg

    width, height = 160, 90
    raw = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(), "-loglevel", "error", "-i", str(video_path),
            "-vf", f"fps={fps},scale={width}:{height},format=gray", "-f", "rawvideo", "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    size = width * height
    frames = [raw[i : i + size] for i in range(0, len(raw) - size + 1, size)]
    changes: list[float] = []
    run_peak, run_peak_time = 0.0, 0.0
    for index in range(fps, len(frames) + 1):
        if index < len(frames):
            current, earlier = frames[index], frames[index - fps]
            difference = sum(abs(a - b) for a, b in zip(current, earlier)) / size
        else:
            difference = 0.0  # flush a run that reaches the end of the video
        if difference > active_level:
            if difference > run_peak:
                run_peak, run_peak_time = difference, index / fps
        elif run_peak:
            if run_peak >= change_level:
                changes.append(run_peak_time)
            run_peak = 0.0
    return changes


def pacing_report(change_times: list[float], duration: float, short_hold_seconds: float = 4.0) -> dict:
    """Summarize how long each layout stays on screen.

    CLARITY pipeline role:
        A patient needs time to take in each visual. This deterministic check
        flags videos that cut to a new graphic every few seconds, which the
        per-scene visual check cannot see.
    """
    edges = [0.0] + sorted(t for t in change_times if 0 < t < duration) + [duration]
    holds = [round(b - a, 1) for a, b in zip(edges, edges[1:]) if b - a > 0.2]
    holds_sorted = sorted(holds)
    return {
        "duration_seconds": round(duration, 1),
        "layout_changes": len(edges) - 2,
        "changes_per_minute": round((len(edges) - 2) / (duration / 60), 1) if duration else 0,
        "median_hold_seconds": holds_sorted[len(holds_sorted) // 2] if holds_sorted else duration,
        "holds_under_seconds": short_hold_seconds,
        "short_holds": sum(1 for hold in holds if hold < short_hold_seconds),
        "holds": holds,
    }


def _words(text: str) -> list[str]:
    """Lowercase word tokens with punctuation removed, for narration diffing."""
    return re.findall(r"[\w']+", text.lower())


def compare_narration(expected: str, actual: str) -> dict:
    """Compare approved narration against HeyGen's rendered subtitles.

    Args:
        expected: Approved voice-over narration.
        actual: Caption text extracted from the rendered video's SRT file.

    Returns:
        A report with the similarity ratio, a pass/needs_review status, and
        every inserted, deleted, or replaced word span. The status is "pass"
        only when the rendered words match the approved words exactly
        (ignoring case and punctuation). A similarity ratio alone is not
        used, because one dropped or duplicated sentence, such as a missing
        list of affected body areas, barely moves the ratio on a long script.

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
    return {
        "status": "needs_review" if differences else "pass",
        "similarity": round(matcher.ratio(), 4),
        "approved_word_count": len(expected_words),
        "rendered_word_count": len(actual_words),
        "differences": differences,
    }
