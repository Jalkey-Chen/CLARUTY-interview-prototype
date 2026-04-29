"""Streamlit entrypoint for the CLARITY Patient Explainer Dashboard prototype."""

from pathlib import Path

import streamlit as st


APP_ROOT = Path(__file__).resolve().parent


def main() -> None:
    """Render the initial CLARITY Streamlit application shell.

    This placeholder entrypoint exists for Milestone 1 so the repository has a
    valid local application target at `streamlit run app.py`. Later milestones
    will expand this function into the full step-by-step CLARITY prototype
    pipeline: note import, shared fact-base review, explanation mode selection,
    script/video review, and transparency/limitations documentation.

    Args:
        None.

    Returns:
        None. Streamlit renders the page as a side effect.

    CLARITY pipeline role:
        Provides the stable application entrypoint that future milestones will
        use to present the patient-facing explainer workflow.
    """
    st.set_page_config(
        page_title="CLARITY Patient Explainer Dashboard",
        layout="wide",
    )

    st.title("CLARITY Patient Explainer Dashboard")
    st.caption(
        "A prototype for turning clinician-verified notes into patient-facing "
        "video explanations."
    )
    st.info(
        "Project scaffold is ready. The step-by-step demo workflow will be "
        "implemented across the next milestones."
    )


if __name__ == "__main__":
    main()
