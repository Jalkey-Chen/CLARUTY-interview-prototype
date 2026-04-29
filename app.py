"""Streamlit entrypoint for the CLARITY Patient Explainer Dashboard prototype."""

import json

import streamlit as st

from src.clarity_dashboard.api import (
    build_direct_openai_video_status,
    call_fact_extraction_api,
    call_note_ingestion_api,
    call_openai_fact_extraction,
    call_openai_script_generation,
    call_openai_verification,
    call_script_generation_api,
    call_verification_api,
    call_video_generation_api,
    direct_openai_enabled,
    get_note_hash,
    get_text_hash,
)
from src.clarity_dashboard.config import (
    APP_ROOT,
    ENV_PATH,
    FACT_BASE_PATH,
    LIMITATIONS_PATH,
    SAMPLE_NOTE_PATH,
    VERSION_METADATA_PATH,
)
from src.clarity_dashboard.env_config import (
    api_calls_enabled,
    display_api_config_status,
    endpoint_is_placeholder,
    load_environment_config,
)
from src.clarity_dashboard.io_utils import load_json
from src.clarity_dashboard.ui import (
    display_api_video_response,
    display_api_video_placeholder,
    display_case_snapshot,
    display_demo_guide,
    display_demo_overview,
    display_future_personalization_controls,
    display_key_takeaways,
    display_limitations,
    display_personalization_summary,
    display_pipeline_transparency,
    display_questions_for_care_team,
    display_safety_notice,
    display_script,
    display_script_text,
    display_version_metadata,
    display_video_or_placeholder,
    handle_case_import,
    inject_custom_css,
    render_step_header,
    render_workflow_strip,
    select_explanation_mode,
)


def api_endpoint_ready(api_config: dict, endpoint_name: str) -> bool:
    """Return whether an API endpoint is ready for the UI to call.

    Args:
        api_config: Environment-derived API configuration.
        endpoint_name: Name of the endpoint environment variable.

    Returns:
        True when live API calls are enabled and the endpoint is configured with
        a non-template URL.

    CLARITY pipeline role:
        Lets the Streamlit workflow show one clear setup message instead of
        calling placeholder endpoints and producing repeated low-level network
        errors.
    """
    endpoint_url = api_config.get(endpoint_name, "")
    return (
        api_calls_enabled(api_config)
        and bool(endpoint_url)
        and not endpoint_is_placeholder(endpoint_url)
    )


def api_or_openai_ready(api_config: dict, endpoint_name: str) -> bool:
    """Return whether a step can run through a backend endpoint or OpenAI.

    Args:
        api_config: Environment-derived API configuration.
        endpoint_name: Name of the custom endpoint environment variable.

    Returns:
        True when a custom endpoint is ready or direct OpenAI mode is ready.

    CLARITY pipeline role:
        Lets uploaded cases work with only an OpenAI API key while still
        supporting future custom CLARITY backend endpoints.
    """
    return api_endpoint_ready(api_config, endpoint_name) or direct_openai_enabled(
        api_config
    )


def display_api_setup_needed(step_name: str, endpoint_name: str) -> None:
    """Explain why uploaded-case API mode is waiting for backend setup.

    Args:
        step_name: Human-readable workflow step name.
        endpoint_name: Required endpoint environment variable name.

    Returns:
        None. The setup explanation is rendered directly into Streamlit.

    CLARITY pipeline role:
        Makes API mode understandable for evaluators: uploaded cases are routed
        to real services by design, but those services must be configured before
        generated facts, scripts, or videos can appear.
    """
    st.info(
        f"{step_name} is waiting for a backend API connection. Because you "
        "uploaded your own document, the app will not use the sample demo data. "
        "To run this step, either configure a custom backend endpoint "
        f"(`{endpoint_name}`) or set `OPENAI_API_KEY`, set "
        "`CLARITY_ENABLE_API_CALLS=true`, and choose `LLM_MODEL`. To see the "
        "static demo immediately, use the built-in sample case instead."
    )


def render_fact_base_step(
    pipeline_mode: str,
    note_hash: str,
    note_text: str,
    api_config: dict,
) -> dict:
    """Render Step 2 and return the active structured fact base.

    Args:
        pipeline_mode: "demo", "api", or "none" based on the Step 1 import
        path.
        note_hash: Stable hash of the imported note, used for API result
        caching.
        note_text: Raw imported clinical note text.
        api_config: Environment-derived API configuration.

    Returns:
        The local demo fact base in demo mode, the API-generated fact base in
        uploaded-case mode, or an empty dictionary when unavailable.

    CLARITY pipeline role:
        Keeps the Step 2 branching explicit: sample cases use local fixtures,
        while uploaded cases call the configured fact extraction API and do not
        silently fall back to sample data.
    """
    if pipeline_mode == "demo":
        fact_base = load_json(FACT_BASE_PATH)
    elif pipeline_mode == "api" and note_hash:
        if not api_or_openai_ready(api_config, "FACT_EXTRACTION_API_URL"):
            display_api_setup_needed(
                "Step 2 fact extraction",
                "FACT_EXTRACTION_API_URL",
            )
            fact_base = {}
            display_case_snapshot(fact_base, pipeline_mode)
            return fact_base

        provider_key = (
            api_config.get("FACT_EXTRACTION_API_URL")
            or f"openai:{api_config.get('LLM_MODEL', '')}"
        )
        fact_cache_key = f"api_fact_base:{note_hash}:{provider_key}"
        if fact_cache_key not in st.session_state:
            with st.spinner("Calling fact extraction API..."):
                if api_endpoint_ready(api_config, "FACT_EXTRACTION_API_URL"):
                    st.session_state[fact_cache_key] = call_fact_extraction_api(
                        note_text,
                        api_config,
                    )
                else:
                    st.session_state[fact_cache_key] = call_openai_fact_extraction(
                        note_text,
                        api_config,
                    )
        fact_base = st.session_state[fact_cache_key]
    else:
        fact_base = {}

    display_case_snapshot(fact_base, pipeline_mode)
    if fact_base:
        takeaway_col, question_col = st.columns(2)
        with takeaway_col:
            display_key_takeaways(fact_base)
        with question_col:
            display_questions_for_care_team(fact_base)
    return fact_base


def render_uploaded_case_ingestion(
    pipeline_mode: str,
    note_hash: str,
    note_text: str,
    api_config: dict,
) -> None:
    """Call and display optional Step 1 ingestion API results.

    Args:
        pipeline_mode: "api" only triggers ingestion.
        note_hash: Stable hash of the uploaded note.
        note_text: Raw imported clinical note text.
        api_config: Environment-derived API configuration.

    Returns:
        None. Any ingestion API response is displayed in an expander.

    CLARITY pipeline role:
        Represents the future secure note ingestion boundary for uploaded cases
        while preserving the current local demo flow for the sample case.
    """
    if pipeline_mode != "api" or not note_hash:
        return
    if not api_endpoint_ready(api_config, "NOTE_INGESTION_API_URL"):
        return

    ingestion_cache_key = (
        f"api_ingestion:{note_hash}:{api_config.get('NOTE_INGESTION_API_URL', '')}"
    )
    if ingestion_cache_key not in st.session_state:
        with st.spinner("Calling note ingestion API..."):
            st.session_state[ingestion_cache_key] = call_note_ingestion_api(
                note_text,
                api_config,
            )
    if st.session_state[ingestion_cache_key]:
        with st.expander("Step 1 API ingestion response", expanded=False):
            st.json(st.session_state[ingestion_cache_key])


def render_step_four(
    pipeline_mode: str,
    note_hash: str,
    note_text: str,
    fact_base: dict,
    selected_mode_key: str,
    selected_mode_metadata: dict,
    personalization_preferences: dict,
    api_config: dict,
) -> None:
    """Render Step 4 for either local demo mode or uploaded-case API mode.

    Args:
        pipeline_mode: "demo", "api", or "none".
        note_hash: Stable hash of the imported note.
        note_text: Raw imported clinical note text.
        fact_base: Active structured fact base from Step 2.
        selected_mode_key: Stable selected explanation mode key.
        selected_mode_metadata: Metadata for the selected explanation mode.
        personalization_preferences: Sidebar preference selections.
        api_config: Environment-derived API configuration.

    Returns:
        None. Script and video sections are rendered directly into Streamlit.

    CLARITY pipeline role:
        Enforces the key product behavior: uploaded cases use API-generated
        scripts and video responses, while sample cases use local cached assets.
    """
    render_step_header(
        4,
        "Review Script and Cached Video",
        "Open the selected transcript and confirm the video slot is ready for cached generated media.",
    )

    script_file = (
        selected_mode_metadata.get("script_file") if selected_mode_metadata else ""
    )
    video_file = (
        selected_mode_metadata.get("video_file") if selected_mode_metadata else ""
    )

    if pipeline_mode == "api":
        render_api_step_four(
            note_hash,
            note_text,
            fact_base,
            selected_mode_key,
            selected_mode_metadata,
            personalization_preferences,
            api_config,
        )
        return

    if script_file:
        display_script(APP_ROOT / script_file)
    else:
        st.warning("No script file is configured for the selected mode.")

    if video_file:
        display_video_or_placeholder(APP_ROOT / video_file)
    else:
        st.warning("No video file is configured for the selected mode.")


def render_api_step_four(
    note_hash: str,
    note_text: str,
    fact_base: dict,
    selected_mode_key: str,
    selected_mode_metadata: dict,
    personalization_preferences: dict,
    api_config: dict,
) -> None:
    """Render API-backed script, verification, and video panels for Step 4.

    Args:
        note_hash: Stable hash of the uploaded note.
        note_text: Raw uploaded note text.
        fact_base: API-generated structured fact base.
        selected_mode_key: Stable selected explanation mode key.
        selected_mode_metadata: Metadata for the selected explanation mode.
        personalization_preferences: Sidebar preference selections.
        api_config: Environment-derived API configuration.

    Returns:
        None. Generated content and API responses are rendered into Streamlit.

    CLARITY pipeline role:
        Keeps uploaded-case script and video handling separate from local demo
        markdown/video files, preventing accidental sample-content fallback.
    """
    if not fact_base:
        st.info(
            "Step 4 is waiting for Step 2. Once the fact extraction API returns "
            "a structured fact base for the uploaded document, this section can "
            "call the script, verification, and video APIs."
        )
        display_script_text("", "Source: script generation API")
        display_api_video_placeholder(
            "The uploaded case does not have a structured fact base yet."
        )
        return

    preferences_key = json.dumps(personalization_preferences, sort_keys=True)
    script_provider_key = (
        api_config.get("SCRIPT_GENERATION_API_URL")
        or f"openai:{api_config.get('LLM_MODEL', '')}"
    )
    script_cache_key = (
        f"api_script:{note_hash}:{selected_mode_key}:"
        f"{script_provider_key}:{preferences_key}"
    )
    if script_cache_key not in st.session_state:
        with st.spinner("Calling script generation API..."):
            if api_endpoint_ready(api_config, "SCRIPT_GENERATION_API_URL"):
                st.session_state[script_cache_key] = call_script_generation_api(
                    note_text,
                    fact_base,
                    selected_mode_key,
                    selected_mode_metadata,
                    personalization_preferences,
                    api_config,
                )
            else:
                st.session_state[script_cache_key] = call_openai_script_generation(
                    note_text,
                    fact_base,
                    selected_mode_key,
                    selected_mode_metadata,
                    personalization_preferences,
                    api_config,
                )
    script_text = st.session_state[script_cache_key]
    display_script_text(script_text, "Source: script generation API")

    if not script_text:
        st.warning("Skipping video API call because no script was generated.")
        display_api_video_placeholder(
            "The uploaded case does not have a generated script yet."
        )
        return

    script_hash = get_text_hash(script_text)
    verification_report = render_verification_response(
        note_hash,
        note_text,
        fact_base,
        script_text,
        script_hash,
        selected_mode_key,
        api_config,
    )

    video_provider_key = (
        api_config.get("VIDEO_GENERATION_API_URL")
        or f"openai_status:{api_config.get('LLM_MODEL', '')}"
    )
    video_cache_key = (
        f"api_video:{note_hash}:{selected_mode_key}:{video_provider_key}:{script_hash}"
    )
    if video_cache_key not in st.session_state:
        if api_endpoint_ready(api_config, "VIDEO_GENERATION_API_URL"):
            with st.spinner("Calling video generation API..."):
                st.session_state[video_cache_key] = call_video_generation_api(
                    fact_base,
                    script_text,
                    selected_mode_key,
                    selected_mode_metadata,
                    verification_report,
                    api_config,
                )
        else:
            st.session_state[video_cache_key] = build_direct_openai_video_status(
                script_text,
                verification_report,
                selected_mode_key,
            )
    display_api_video_response(st.session_state[video_cache_key])


def render_verification_response(
    note_hash: str,
    note_text: str,
    fact_base: dict,
    script_text: str,
    script_hash: str,
    selected_mode_key: str,
    api_config: dict,
) -> dict:
    """Render optional verification API output for an uploaded-case script.

    Args:
        note_hash: Stable hash of the uploaded note.
        note_text: Raw uploaded note text.
        fact_base: API-generated structured fact base.
        script_text: API-generated script text.
        script_hash: Stable hash of the generated script.
        selected_mode_key: Stable selected explanation mode key.
        api_config: Environment-derived API configuration.

    Returns:
        Verification report dictionary, or an empty dictionary when unavailable.

    CLARITY pipeline role:
        Preserves the intended CLARITY verification checkpoint between script
        generation and video generation.
    """
    verification_provider_key = (
        api_config.get("VERIFICATION_API_URL")
        or f"openai:{api_config.get('LLM_MODEL', '')}"
    )
    verification_cache_key = (
        f"api_verification:{note_hash}:{selected_mode_key}:"
        f"{verification_provider_key}:{script_hash}"
    )
    if verification_cache_key not in st.session_state:
        with st.spinner("Calling verification API..."):
            if api_endpoint_ready(api_config, "VERIFICATION_API_URL"):
                st.session_state[verification_cache_key] = call_verification_api(
                    note_text,
                    fact_base,
                    script_text,
                    selected_mode_key,
                    api_config,
                )
            else:
                st.session_state[verification_cache_key] = call_openai_verification(
                    note_text,
                    fact_base,
                    script_text,
                    selected_mode_key,
                    api_config,
                )
    verification_report = st.session_state[verification_cache_key]
    if verification_report:
        with st.expander("Verification API response", expanded=False):
            st.json(verification_report)
    return verification_report


def main() -> None:
    """Render the CLARITY Streamlit application shell.

    Args:
        None.

    Returns:
        None. Streamlit renders the page as a side effect.

    CLARITY pipeline role:
        Coordinates the patient explainer workflow while delegating config,
        document loading, API calls, and UI rendering to focused modules.
    """
    st.set_page_config(
        page_title="CLARITY Patient Explainer Dashboard",
        layout="wide",
    )
    inject_custom_css()
    api_config = load_environment_config(ENV_PATH)

    st.title("CLARITY Patient Explainer Dashboard")
    st.caption(
        "A prototype for turning clinician-verified notes into patient-facing "
        "video explanations."
    )
    st.markdown(
        "This local demo walks through the CLARITY pipeline one step at a time, "
        "from note import to patient-facing explanation materials."
    )

    display_demo_overview()
    render_workflow_strip()
    display_safety_notice()

    st.divider()
    case_status, note_text, pipeline_mode = handle_case_import(SAMPLE_NOTE_PATH)

    st.markdown(f"**Current case status:** {case_status}")
    if pipeline_mode == "api":
        st.markdown("**Pipeline mode:** API mode for uploaded case")
    elif pipeline_mode == "demo":
        st.markdown("**Pipeline mode:** Local demo mode")
    if note_text:
        with st.expander("Raw clinical note preview", expanded=False):
            st.text_area(
                "Imported note text",
                value=note_text,
                height=260,
                disabled=True,
                label_visibility="collapsed",
            )

    st.divider()
    version_metadata = load_json(VERSION_METADATA_PATH)
    selected_mode_key, selected_mode_metadata = select_explanation_mode(
        version_metadata
    )
    personalization_preferences = display_future_personalization_controls()
    display_api_config_status(api_config)

    note_hash = get_note_hash(note_text) if note_text else ""
    render_uploaded_case_ingestion(
        pipeline_mode,
        note_hash,
        note_text,
        api_config,
    )
    fact_base = render_fact_base_step(
        pipeline_mode,
        note_hash,
        note_text,
        api_config,
    )

    st.divider()
    display_version_metadata(selected_mode_metadata)
    display_personalization_summary(personalization_preferences)

    st.divider()
    render_step_four(
        pipeline_mode,
        note_hash,
        note_text,
        fact_base,
        selected_mode_key,
        selected_mode_metadata,
        personalization_preferences,
        api_config,
    )

    st.divider()
    render_step_header(
        5,
        "Review Pipeline Transparency, Limitations, and Next Steps",
        "Show how the prototype was generated and what must happen before real patient-facing use.",
    )
    display_demo_guide()
    display_pipeline_transparency()
    display_limitations(LIMITATIONS_PATH)


if __name__ == "__main__":
    main()
