"""Environment loading helpers for future API-backed CLARITY integrations."""

import os
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

from .config import API_ENABLE_FLAG, API_ENV_VARS, PLACEHOLDER_API_HOSTS


def load_environment_config(env_path: Path) -> dict:
    """Load local environment variables for future API-backed steps.

    Args:
        env_path: Path to the local `.env` file. The file is intentionally not
        committed; `.env.example` documents the expected variable names.

    Returns:
        A dictionary containing configured values for the API-related variables
        used by future CLARITY integrations. Missing variables are represented
        as empty strings.

    CLARITY pipeline role:
        Prepares the prototype for Step 1-4 API integration without calling any
        external services in the current demo. This gives evaluators and future
        developers a clear place to configure ingestion, extraction, script
        generation, verification, and video generation services.
    """
    if env_path.exists():
        load_dotenv(env_path, override=True)

    return {name: os.getenv(name, "") for name in API_ENV_VARS}


def api_calls_enabled(api_config: dict) -> bool:
    """Return whether live API calls are enabled for uploaded-case mode.

    Args:
        api_config: Mapping returned by `load_environment_config`.

    Returns:
        True when `CLARITY_ENABLE_API_CALLS` is set to a truthy value.

    CLARITY pipeline role:
        Prevents copied `.env.example` URLs from accidentally triggering live
        network requests. Uploaded cases still enter API mode, but the app
        shows configuration guidance until API calls are explicitly enabled.
    """
    return api_config.get(API_ENABLE_FLAG, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def endpoint_is_placeholder(endpoint_url: str) -> bool:
    """Detect template endpoints that should not be called by default.

    Args:
        endpoint_url: Endpoint URL from `.env`.

    Returns:
        True when the endpoint appears to be one of the template localhost URLs.

    CLARITY pipeline role:
        Keeps copied `.env.example` values from producing noisy connection
        refused errors when no backend server is running.
    """
    if not endpoint_url:
        return False
    parsed = urlparse(endpoint_url)
    return parsed.netloc in PLACEHOLDER_API_HOSTS


def display_api_config_status(api_config: dict) -> None:
    """Display non-secret API configuration readiness in the sidebar.

    Args:
        api_config: Mapping returned by `load_environment_config`.

    Returns:
        None. The status is rendered into the Streamlit sidebar.

    CLARITY pipeline role:
        Makes it explicit that the current app is API-ready but still operates
        with local cached assets. Values are never printed, only whether each
        expected variable is configured.
    """
    with st.sidebar.expander("API configuration", expanded=False):
        st.caption(
            "Optional for this prototype. Add values to `.env` using "
            "`.env.example` as the template when connecting Steps 1-4 to APIs."
        )
        enabled = api_calls_enabled(api_config)
        st.markdown(f"**Live API calls:** {'Enabled' if enabled else 'Disabled'}")
        for variable_name, description in API_ENV_VARS.items():
            configured = bool(api_config.get(variable_name))
            if variable_name == API_ENABLE_FLAG:
                status_label = "Enabled" if enabled else "Disabled"
                status_icon = "OK" if enabled else "Off"
            elif configured and endpoint_is_placeholder(api_config[variable_name]):
                status_label = "Template placeholder"
                status_icon = "Placeholder"
            else:
                status_label = "Configured" if configured else "Not set"
                status_icon = "OK" if configured else "Missing"
            st.markdown(f"**{variable_name}**: {status_icon} - {status_label}")
            st.caption(description)
