"""Streamlit entrypoint for the CLARITY Patient Explainer Dashboard prototype."""

from pathlib import Path

import streamlit as st


APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
SAMPLE_NOTE_PATH = DATA_DIR / "sample_case_note.txt"


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


if __name__ == "__main__":
    main()
