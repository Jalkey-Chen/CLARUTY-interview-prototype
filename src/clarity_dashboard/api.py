"""API client helpers for uploaded-case CLARITY dashboard mode."""

import json
import urllib.error
import urllib.request
from hashlib import sha256

import streamlit as st
from openai import OpenAI, OpenAIError

from .config import API_TIMEOUT_SECONDS
from .env_config import api_calls_enabled, endpoint_is_placeholder


DEFAULT_LLM_MODEL = "gpt-4.1-mini"


def endpoint_is_callable(api_config: dict, variable_name: str) -> bool:
    """Return whether a configured endpoint should be called.

    Args:
        api_config: Environment-derived API configuration.
        variable_name: Endpoint variable name to check.

    Returns:
        True when live API calls are enabled and the endpoint is not a template
        placeholder.

    CLARITY pipeline role:
        Allows uploaded cases to enter API mode without causing connection
        refused errors when users have only copied `.env.example`.
    """
    endpoint_url = api_config.get(variable_name, "")
    if not endpoint_url:
        st.warning(f"API mode is active, but `{variable_name}` is not configured.")
        return False

    if not api_calls_enabled(api_config):
        st.info(
            "API mode is active, but live API calls are disabled. Set "
            "`CLARITY_ENABLE_API_CALLS=true` in `.env` after configuring real "
            "endpoints."
        )
        return False

    if endpoint_is_placeholder(endpoint_url):
        st.info(
            f"`{variable_name}` is still set to the template localhost endpoint. "
            "Replace it with a running backend URL before enabling this step."
        )
        return False

    return True


def direct_openai_enabled(api_config: dict) -> bool:
    """Return whether direct OpenAI mode can be used.

    Args:
        api_config: Environment-derived API configuration.

    Returns:
        True when live calls are enabled and `OPENAI_API_KEY` is configured.

    CLARITY pipeline role:
        Lets the prototype run Step 2-4 without a custom FastAPI backend. This
        is useful for interviews where the available integration is an OpenAI
        API key rather than deployed CLARITY service endpoints.
    """
    return api_calls_enabled(api_config) and bool(api_config.get("OPENAI_API_KEY"))


def get_llm_model(api_config: dict) -> str:
    """Return the configured model for direct OpenAI mode.

    Args:
        api_config: Environment-derived API configuration.

    Returns:
        The model name from `LLM_MODEL`, or a conservative default when the
        value is missing or still set to the template placeholder.

    CLARITY pipeline role:
        Keeps model selection configurable without hard-coding it throughout
        fact extraction, script generation, and verification calls.
    """
    model = api_config.get("LLM_MODEL", "").strip()
    if not model or model == "replace-with-selected-model":
        return DEFAULT_LLM_MODEL
    return model


def extract_output_text(response) -> str:
    """Extract text from an OpenAI Responses API response.

    Args:
        response: Response object returned by the OpenAI Python SDK.

    Returns:
        Best-effort generated text.

    CLARITY pipeline role:
        Keeps direct OpenAI mode tolerant of small SDK response-shape changes
        while preserving a simple text interface for downstream parsers.
    """
    output_text = getattr(response, "output_text", "")
    if output_text:
        return output_text

    chunks: list[str] = []
    for item in getattr(response, "output", []) or []:
        for content in getattr(item, "content", []) or []:
            text = getattr(content, "text", "")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def parse_json_object_from_text(text: str) -> dict:
    """Parse a JSON object from model output.

    Args:
        text: Raw model output that should contain a JSON object.

    Returns:
        Parsed JSON object, or an empty dictionary if parsing fails.

    CLARITY pipeline role:
        Allows direct OpenAI mode to recover structured fact bases and
        verification reports from text responses.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        st.error(f"OpenAI response was not valid JSON: {exc}")
        return {}

    if not isinstance(parsed, dict):
        st.error("OpenAI response JSON must be an object.")
        return {}
    return parsed


def call_openai_text(api_config: dict, developer_prompt: str, user_prompt: str) -> str:
    """Call OpenAI directly and return generated text.

    Args:
        api_config: Environment-derived API configuration.
        developer_prompt: High-priority instructions for the model.
        user_prompt: Case-specific input prompt.

    Returns:
        Generated text, or an empty string if the call fails.

    CLARITY pipeline role:
        Provides the direct OpenAI fallback for uploaded cases when no custom
        CLARITY backend endpoint is configured.
    """
    if not direct_openai_enabled(api_config):
        st.info(
            "Direct OpenAI mode is not ready. Set `OPENAI_API_KEY` and "
            "`CLARITY_ENABLE_API_CALLS=true` in `.env`, or configure a custom "
            "backend endpoint."
        )
        return ""

    client = OpenAI(api_key=api_config.get("OPENAI_API_KEY"))
    try:
        response = client.responses.create(
            model=get_llm_model(api_config),
            input=[
                {"role": "developer", "content": developer_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except OpenAIError as exc:
        st.error(f"OpenAI API request failed: {exc}")
        return ""

    return extract_output_text(response)


def call_openai_fact_extraction(note_text: str, api_config: dict) -> dict:
    """Extract a structured fact base directly with OpenAI.

    Args:
        note_text: Raw uploaded clinical note text.
        api_config: Environment-derived API configuration.

    Returns:
        Structured fact base dictionary, or an empty dictionary when unavailable.

    CLARITY pipeline role:
        Implements Step 2 without a custom backend when the interview prototype
        is configured with only an OpenAI API key.
    """
    developer_prompt = (
        "You extract a clinician-reviewable CLARITY fact base from a "
        "de-identified clinical note. Extract only facts explicitly supported "
        "by the note. Do not infer prognosis, diagnoses, or treatment beyond "
        "the note. Separate confirmed facts from uncertainty. Return only JSON."
    )
    user_prompt = f"""
Return a JSON object with exactly these keys:
case_id, diagnosis, stage, patient_age, main_areas_involved,
current_treatment, recommended_next_treatment, uncertainty_points,
key_takeaways, questions_for_care_team, safety_note.

Use arrays for main_areas_involved, uncertainty_points, key_takeaways, and
questions_for_care_team. If a value is missing, use "Not specified in the note".

Clinical note:
{note_text}
"""
    text = call_openai_text(api_config, developer_prompt, user_prompt)
    return parse_json_object_from_text(text) if text else {}


def call_openai_script_generation(
    note_text: str,
    fact_base: dict,
    mode_key: str,
    mode_metadata: dict,
    preferences: dict,
    api_config: dict,
) -> str:
    """Generate a patient explainer script directly with OpenAI.

    Args:
        note_text: Raw uploaded clinical note text.
        fact_base: Structured fact base from Step 2.
        mode_key: Selected explanation mode identifier.
        mode_metadata: Selected explanation mode metadata.
        preferences: Sidebar personalization preferences.
        api_config: Environment-derived API configuration.

    Returns:
        Markdown script text, or an empty string when unavailable.

    CLARITY pipeline role:
        Implements Step 4 script generation without a custom backend while
        preserving the same fact-base-first flow.
    """
    developer_prompt = (
        "You generate CLARITY patient education scripts. Use only the verified "
        "fact base. Do not add unsupported medical claims or advice. Keep final "
        "content clinician-reviewable."
    )
    user_prompt = f"""
Generate a NotebookLM-style two-speaker patient explainer script in Markdown.

Selected mode key: {mode_key}
Mode metadata: {json.dumps(mode_metadata, ensure_ascii=False)}
Future preferences: {json.dumps(preferences, ensure_ascii=False)}

Use this structure:
- Title
- Prototype note
- Speaker 1 / Speaker 2 dialogue
- Opening
- Main diagnosis
- What the scans and biopsy showed
- Current and recommended treatment
- What is still uncertain
- Questions to discuss with the care team
- Closing

Shared fact base:
{json.dumps(fact_base, ensure_ascii=False, indent=2)}

Original clinical note for grounding only:
{note_text}
"""
    return call_openai_text(api_config, developer_prompt, user_prompt)


def call_openai_verification(
    note_text: str,
    fact_base: dict,
    script_text: str,
    mode_key: str,
    api_config: dict,
) -> dict:
    """Verify a generated script directly with OpenAI.

    Args:
        note_text: Raw uploaded clinical note text.
        fact_base: Structured fact base from Step 2.
        script_text: Generated script text.
        mode_key: Selected explanation mode identifier.
        api_config: Environment-derived API configuration.

    Returns:
        Verification report dictionary.

    CLARITY pipeline role:
        Implements the CLARITY verification checkpoint without a custom backend.
    """
    developer_prompt = (
        "You verify patient education scripts against a clinical note and fact "
        "base. Return only JSON. Flag unsupported claims, missing critical "
        "information, overconfident uncertainty language, and direct medical "
        "advice."
    )
    user_prompt = f"""
Return a JSON object with keys:
overall_status, unsupported_claims, missing_critical_information,
uncertainty_language_concerns, medical_advice_concerns,
translation_or_readability_concerns, recommended_edits.

Mode key: {mode_key}

Clinical note:
{note_text}

Fact base:
{json.dumps(fact_base, ensure_ascii=False, indent=2)}

Generated script:
{script_text}
"""
    text = call_openai_text(api_config, developer_prompt, user_prompt)
    return parse_json_object_from_text(text) if text else {}


def build_direct_openai_video_status(
    script_text: str,
    verification_report: dict,
    mode_key: str,
) -> dict:
    """Return a video status object for direct OpenAI mode.

    Args:
        script_text: Generated script text.
        verification_report: Verification report dictionary.
        mode_key: Selected explanation mode identifier.

    Returns:
        Video status dictionary for the UI.

    CLARITY pipeline role:
        Makes clear that direct OpenAI mode can prepare verified text assets but
        does not currently generate the final 5-10 minute video file. That video
        should still be produced and cached after verification.
    """
    return {
        "status": (
            "Direct OpenAI mode generated the script and verification report. "
            "Final video generation is not connected in this prototype yet; "
            "add a cached video file or configure VIDEO_GENERATION_API_URL."
        ),
        "mode_key": mode_key,
        "script_ready": bool(script_text),
        "verification_status": verification_report.get("overall_status", "not_run"),
    }


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
    if not endpoint_is_callable(api_config, "FACT_EXTRACTION_API_URL"):
        return {}
    endpoint_url = api_config.get("FACT_EXTRACTION_API_URL", "")

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
        st.info(
            "`NOTE_INGESTION_API_URL` is not configured; using local uploaded "
            "text for downstream API payloads."
        )
        return {}
    if not endpoint_is_callable(api_config, "NOTE_INGESTION_API_URL"):
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
    if not endpoint_is_callable(api_config, "SCRIPT_GENERATION_API_URL"):
        return ""
    endpoint_url = api_config.get("SCRIPT_GENERATION_API_URL", "")

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
    if not endpoint_is_callable(api_config, "VERIFICATION_API_URL"):
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
    if not endpoint_is_callable(api_config, "VIDEO_GENERATION_API_URL"):
        return {}
    endpoint_url = api_config.get("VIDEO_GENERATION_API_URL", "")

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
