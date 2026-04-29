"""Environment loading helpers for future API-backed CLARITY integrations."""

import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from .config import API_ENV_VARS


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
        for variable_name, description in API_ENV_VARS.items():
            configured = bool(api_config.get(variable_name))
            status_label = "Configured" if configured else "Not set"
            status_icon = "OK" if configured else "Missing"
            st.markdown(f"**{variable_name}**: {status_icon} - {status_label}")
            st.caption(description)
