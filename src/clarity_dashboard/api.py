"""API client helpers for uploaded-case CLARITY dashboard mode."""

import json
import urllib.error
import urllib.request
from hashlib import sha256

import streamlit as st

from .config import API_TIMEOUT_SECONDS


def get_note_hash(note_text: str) -> str:
    """Create a stable short hash for a loaded clinical note.

    Args:
        note_text: Raw imported clinical note text.

    Returns:
        A short SHA-256 digest that can be used as a session-state cache key.

    CLARITY pipeline role:
        Lets the API-backed prototype avoid repeating the same extraction or
        generation calls on every Streamlit rerun for the same uploaded note.
    """
    return sha256(note_text.encode("utf-8")).hexdigest()[:16]


def get_text_hash(text: str) -> str:
    """Create a stable short hash for generated text.

    Args:
        text: Script or other generated text.

    Returns:
        A short SHA-256 digest.

    CLARITY pipeline role:
        Supports cache keys for script verification and video generation so the
        app reruns do not repeatedly call APIs for unchanged generated content.
    """
    return sha256(text.encode("utf-8")).hexdigest()[:16]


def post_json_to_api(endpoint_url: str, payload: dict, api_key: str = "") -> dict:
    """POST JSON to an API endpoint and parse a JSON object response.

    Args:
        endpoint_url: Fully qualified API endpoint URL.
        payload: JSON-serializable request body.
        api_key: Optional bearer token used for future hosted API providers.

    Returns:
        Parsed JSON object response. Returns an empty dictionary when the
        request fails, the response is not valid JSON, or the response JSON is
        not an object.

    CLARITY pipeline role:
        Provides a small API bridge for uploaded-note mode. The local demo uses
        cached files, but uploaded cases should move through API-backed Step 2
        fact extraction, Step 3 script generation/verification, and Step 4 video
        generation or retrieval.
    """
    request_body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        endpoint_url,
        data=request_body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
            response_text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_text = exc.read().decode("utf-8", errors="replace")
        st.error(f"API request failed with HTTP {exc.code}: {error_text}")
        return {}
    except urllib.error.URLError as exc:
        st.error(f"API request failed: {exc.reason}")
        return {}
    except TimeoutError:
        st.error("API request timed out.")
        return {}

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as exc:
        st.error(f"API response was not valid JSON: {exc}")
        return {}

    if not isinstance(data, dict):
        st.error("API response must be a JSON object.")
        return {}
    return data


def extract_response_object(response: dict, keys: list[str]) -> dict:
    """Extract a nested dictionary from an API response.

    Args:
        response: Parsed API response object.
        keys: Candidate keys that may contain the desired nested object.

    Returns:
        The first nested dictionary found under the candidate keys, or the
        original response if none of those keys are present.

    CLARITY pipeline role:
        Makes the prototype tolerant of common API response envelopes such as
        `{ "fact_base": {...} }` while still accepting direct JSON objects.
    """
    for key in keys:
        value = response.get(key)
        if isinstance(value, dict):
            return value
    return response


def extract_response_text(response: dict, keys: list[str]) -> str:
    """Extract text content from an API response.

    Args:
        response: Parsed API response object.
        keys: Candidate string keys, ordered by preference.

    Returns:
        The first non-empty string found under the candidate keys, or an empty
        string if the response does not include generated text.

    CLARITY pipeline role:
        Lets the Step 4 script panel accept several likely API response shapes
        without forcing the first backend prototype to use one exact field name.
    """
    for key in keys:
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def call_fact_extraction_api(note_text: str, api_config: dict) -> dict:
    """Call the configured fact extraction API for an uploaded case.

    Args:
        note_text: Raw text extracted from the uploaded clinical note.
        api_config: Environment-derived API configuration.

    Returns:
        Structured fact base dictionary returned by the API, or an empty
        dictionary when the endpoint is missing or the request fails.

    CLARITY pipeline role:
        Implements API mode for Step 2. Uploaded notes should not reuse the
        sample fact base; they need a case-specific fact extraction response.
    """
    endpoint_url = api_config.get("FACT_EXTRACTION_API_URL", "")
    if not endpoint_url:
        st.warning(
            "API mode is active, but `FACT_EXTRACTION_API_URL` is not configured."
        )
        return {}

    response = post_json_to_api(
        endpoint_url,
        {"clinical_note": note_text},
        api_config.get("OPENAI_API_KEY", ""),
    )
    return extract_response_object(response, ["fact_base", "data", "result"])


def call_note_ingestion_api(note_text: str, api_config: dict) -> dict:
    """Call the optional note ingestion API for an uploaded case.

    Args:
        note_text: Raw text extracted from the uploaded clinical note.
        api_config: Environment-derived API configuration.

    Returns:
        Ingestion API response dictionary, or an empty dictionary when the
        endpoint is missing or the request fails.

    CLARITY pipeline role:
        Represents API mode for Step 1. The prototype can still pass extracted
        note text directly to downstream APIs, but this hook documents and
        exercises the intended secure ingestion boundary for uploaded cases.
    """
    endpoint_url = api_config.get("NOTE_INGESTION_API_URL", "")
    if not endpoint_url:
        st.warning(
            "API mode is active, but `NOTE_INGESTION_API_URL` is not configured; "
            "using local uploaded text for downstream API payloads."
        )
        return {}

    return post_json_to_api(
        endpoint_url,
        {"clinical_note": note_text},
        api_config.get("OPENAI_API_KEY", ""),
    )


def call_script_generation_api(
    note_text: str,
    fact_base: dict,
    mode_key: str,
    mode_metadata: dict,
    preferences: dict,
    api_config: dict,
) -> str:
    """Call the configured script generation API for an uploaded case.

    Args:
        note_text: Raw imported clinical note text.
        fact_base: Structured fact base from Step 2.
        mode_key: Selected explanation mode identifier.
        mode_metadata: Selected explanation mode metadata.
        preferences: Placeholder personalization selections from the sidebar.
        api_config: Environment-derived API configuration.

    Returns:
        Generated script markdown/text, or an empty string when unavailable.

    CLARITY pipeline role:
        Implements API mode for the script portion of Step 4. This keeps
        uploaded cases from showing static demo scripts that belong to the
        sample case.
    """
    endpoint_url = api_config.get("SCRIPT_GENERATION_API_URL", "")
    if not endpoint_url:
        st.warning(
            "API mode is active, but `SCRIPT_GENERATION_API_URL` is not configured."
        )
        return ""

    response = post_json_to_api(
        endpoint_url,
        {
            "clinical_note": note_text,
            "fact_base": fact_base,
            "mode_key": mode_key,
            "mode_metadata": mode_metadata,
            "preferences": preferences,
        },
        api_config.get("OPENAI_API_KEY", ""),
    )
    return extract_response_text(
        response,
        ["script_markdown", "script", "transcript", "content", "text"],
    )


def call_verification_api(
    note_text: str,
    fact_base: dict,
    script_text: str,
    mode_key: str,
    api_config: dict,
) -> dict:
    """Call the optional verification API for an uploaded-case script.

    Args:
        note_text: Raw imported clinical note text.
        fact_base: Structured fact base from Step 2.
        script_text: Script generated for the selected mode.
        mode_key: Selected explanation mode identifier.
        api_config: Environment-derived API configuration.

    Returns:
        Verification report dictionary, or an empty dictionary when the endpoint
        is not configured or the request fails.

    CLARITY pipeline role:
        Supports the intended CLARITY safeguard between script generation and
        video generation. The current UI displays the returned report but does
        not block video requests unless future API logic chooses to do so.
    """
    endpoint_url = api_config.get("VERIFICATION_API_URL", "")
    if not endpoint_url:
        st.warning(
            "API mode is active, but `VERIFICATION_API_URL` is not configured; "
            "script verification was skipped."
        )
        return {}

    return post_json_to_api(
        endpoint_url,
        {
            "clinical_note": note_text,
            "fact_base": fact_base,
            "script": script_text,
            "mode_key": mode_key,
        },
        api_config.get("OPENAI_API_KEY", ""),
    )


def call_video_generation_api(
    fact_base: dict,
    script_text: str,
    mode_key: str,
    mode_metadata: dict,
    verification_report: dict,
    api_config: dict,
) -> dict:
    """Call the configured video generation or retrieval API.

    Args:
        fact_base: Structured fact base from Step 2.
        script_text: Generated script text for the selected mode.
        mode_key: Selected explanation mode identifier.
        mode_metadata: Selected explanation mode metadata.
        verification_report: Optional verification report from the verification
        API.
        api_config: Environment-derived API configuration.

    Returns:
        Video API response dictionary. Common supported fields include
        `video_url`, `video_file`, `video_path`, `status`, and `message`.

    CLARITY pipeline role:
        Implements API mode for the video portion of Step 4. Uploaded cases
        should request or retrieve video outputs from the configured service
        instead of showing sample cached videos.
    """
    endpoint_url = api_config.get("VIDEO_GENERATION_API_URL", "")
    if not endpoint_url:
        st.warning(
            "API mode is active, but `VIDEO_GENERATION_API_URL` is not configured."
        )
        return {}

    return post_json_to_api(
        endpoint_url,
        {
            "fact_base": fact_base,
            "script": script_text,
            "mode_key": mode_key,
            "mode_metadata": mode_metadata,
            "verification_report": verification_report,
        },
        api_config.get("OPENAI_API_KEY", ""),
    )
