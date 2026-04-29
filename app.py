"""Streamlit entrypoint for the CLARITY Patient Explainer Dashboard prototype."""

import json
from pathlib import Path

import streamlit as st


APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
SAMPLE_NOTE_PATH = DATA_DIR / "sample_case_note.txt"
FACT_BASE_PATH = DATA_DIR / "extracted_fact_base.json"


def load_json(path: Path) -> dict:
    """Load a JSON object from disk with Streamlit-friendly error handling.

    Args:
        path: Path to a JSON file expected to contain a top-level object.

    Returns:
        A dictionary parsed from the JSON file. Returns an empty dictionary when
        the file is missing, unreadable, malformed, or does not contain a JSON
        object.

    CLARITY pipeline role:
        Provides a safe loader for structured prototype assets such as the
        clinician-verifiable fact base and, in later milestones, version
        metadata. Safe loading matters because this dashboard is meant to stay
        demoable even while scripts, prompts, and videos are being iterated.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # A missing data file should be visible to the evaluator without
        # collapsing the rest of the prototype page.
        st.warning(f"Required JSON file was not found: {path}")
        return {}
    except json.JSONDecodeError as exc:
        st.error(f"Invalid JSON in {path.name}: {exc}")
        return {}
    except OSError as exc:
        st.error(f"Unable to read JSON file {path.name}: {exc}")
        return {}

    if not isinstance(data, dict):
        st.error(f"Expected {path.name} to contain a JSON object.")
        return {}
    return data


def load_sample_note(path: Path) -> str:
    """Load the built-in de-identified sample clinical note.

    Args:
        path: Path to the sample clinical note text file.

    Returns:
        The note text when the file can be read, or an empty string when the
        file is missing or unreadable.

    CLARITY pipeline role:
        Supports Step 1 of the prototype workflow by giving interview
        evaluators a reliable built-in case to load before they test upload
        behavior. This keeps the demo runnable even when the evaluator does not
        have a local clinical note prepared.
    """
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Missing demo assets should not crash the app; graceful fallback keeps
        # the prototype usable while clearly showing what needs to be restored.
        st.warning(f"Sample note file was not found: {path}")
    except OSError as exc:
        st.error(f"Unable to read sample note: {exc}")
    return ""


def handle_case_import(sample_path: Path) -> tuple[str, str]:
    """Render the clinical note import controls and return the loaded case.

    Args:
        sample_path: Path to the built-in sample note used by the demo flow.

    Returns:
        A tuple of `(case_status, note_text)`. `case_status` is one of
        "No case loaded", "Sample case loaded", or "Uploaded case loaded".
        `note_text` contains the loaded raw clinical note text, or an empty
        string when no case is loaded.

    CLARITY pipeline role:
        Implements Step 1, where a de-identified clinical note enters the
        patient explainer workflow. The current prototype only imports plain
        text and markdown so the demo stays lightweight; structured fact
        extraction is handled separately in later steps.
    """
    st.subheader("Step 1. Import Clinical Note")
    st.write(
        "Start by loading a de-identified note. For the interview demo, use the "
        "built-in sample note or upload a local `.txt` / `.md` file."
    )

    use_sample = st.checkbox("Use sample de-identified case note", value=True)
    uploaded_file = st.file_uploader(
        "Upload a de-identified clinical note",
        type=["txt", "md"],
        help="Current prototype supports plain text and markdown files.",
    )

    if uploaded_file is not None:
        raw_bytes = uploaded_file.getvalue()
        note_text = raw_bytes.decode("utf-8", errors="replace")
        st.success(f"Uploaded case loaded: {uploaded_file.name}")
        return "Uploaded case loaded", note_text

    if use_sample:
        note_text = load_sample_note(sample_path)
        if note_text:
            st.success("Sample case loaded")
            return "Sample case loaded", note_text

    st.info("No case loaded")
    return "No case loaded", ""


def display_safety_notice() -> None:
    """Display the prototype safety notice.

    Args:
        None.

    Returns:
        None. The notice is rendered directly into the Streamlit page.

    CLARITY pipeline role:
        Reinforces that the dashboard is a patient education prototype, not a
        source of medical advice. This notice frames every downstream step:
        fact review, script presentation, and cached video display should all be
        understood as materials requiring clinician review before real use.
    """
    st.warning(
        "Prototype safety note: this dashboard is for demonstration and patient "
        "education design only. It is not medical advice, and final content "
        "should be reviewed by clinicians before patient-facing use."
    )


def display_case_snapshot(fact_base: dict) -> None:
    """Render a patient-facing snapshot from the shared structured fact base.

    Args:
        fact_base: Dictionary loaded from `data/extracted_fact_base.json`.

    Returns:
        None. The snapshot is rendered directly into the Streamlit page.

    CLARITY pipeline role:
        Implements Step 2 by showing the structured facts that will anchor all
        explanation versions. The five communication modes should share this
        same fact base so tone, language, and uncertainty framing can vary
        without allowing facts to drift between versions.
    """
    st.subheader("Step 2. Review Shared Fact Base")
    st.info(
        "For this prototype, the structured fact base is loaded from a "
        "pre-verified JSON file. In a production workflow, this step would be "
        "generated from the clinical note and reviewed by a clinician."
    )

    if not fact_base:
        st.warning("No structured fact base is available yet.")
        return

    # Fact extraction and style-controlled script presentation are separated so
    # every version can preserve the same clinical content while changing only
    # language, tone, complexity, and uncertainty framing.
    st.markdown(
        "**Shared fact base:** all explanation versions should be generated "
        "from this same structured source to reduce factual drift."
    )

    diagnosis_col, stage_col, age_col = st.columns(3)
    diagnosis_col.metric("Diagnosis", fact_base.get("diagnosis", "Not available"))
    stage_col.metric("Stage", fact_base.get("stage", "Not available"))
    age_col.metric("Patient age", fact_base.get("patient_age", "Not available"))

    area_col, treatment_col = st.columns(2)
    with area_col:
        st.markdown("**Main areas involved**")
        for area in fact_base.get("main_areas_involved", []):
            st.markdown(f"- {area}")

    with treatment_col:
        st.markdown("**Current treatment**")
        st.write(fact_base.get("current_treatment", "Not available"))
        st.markdown("**Recommended next treatment**")
        st.write(fact_base.get("recommended_next_treatment", "Not available"))

    st.markdown("**Key uncertainty / monitoring points**")
    for point in fact_base.get("uncertainty_points", []):
        st.markdown(f"- {point}")


def main() -> None:
    """Render the CLARITY Streamlit application shell.

    This function configures the page and coordinates the visible workflow. At
    this milestone it renders the clinical note import step; later milestones
    will add shared fact-base review, explanation mode selection, script/video
    review, and transparency/limitations documentation.

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

    st.markdown(
        "This local demo walks through the CLARITY pipeline one step at a time, "
        "from note import to patient-facing explanation materials."
    )

    display_safety_notice()

    case_status, note_text = handle_case_import(SAMPLE_NOTE_PATH)

    st.markdown(f"**Current case status:** {case_status}")
    if note_text:
        with st.expander("Raw clinical note preview", expanded=False):
            st.text_area(
                "Imported note text",
                value=note_text,
                height=260,
                disabled=True,
                label_visibility="collapsed",
            )

    fact_base = load_json(FACT_BASE_PATH)
    display_case_snapshot(fact_base)


if __name__ == "__main__":
    main()
