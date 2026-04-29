"""Streamlit entrypoint for the CLARITY Patient Explainer Dashboard prototype."""

import json
from pathlib import Path

import streamlit as st


APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = APP_ROOT / "data"
SAMPLE_NOTE_PATH = DATA_DIR / "sample_case_note.txt"
FACT_BASE_PATH = DATA_DIR / "extracted_fact_base.json"
VERSION_METADATA_PATH = DATA_DIR / "version_metadata.json"
WRITEUP_DIR = APP_ROOT / "writeup"
LIMITATIONS_PATH = WRITEUP_DIR / "limitations_and_next_steps.md"


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


def load_markdown(path: Path) -> str:
    """Load a markdown document from disk with graceful error handling.

    Args:
        path: Path to the markdown file that should be rendered in the app.

    Returns:
        The markdown text when it can be read, or an empty string when the file
        is missing or unreadable.

    CLARITY pipeline role:
        Supports transcript, prompt, and writeup display throughout the
        prototype. Markdown assets are intentionally stored as editable files so
        scripts and documentation can be revised without changing the Streamlit
        application logic.
    """
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # Missing files are expected during iteration; the dashboard should
        # point to the missing asset instead of failing mid-demo.
        st.warning(f"Markdown file was not found: {path}")
    except OSError as exc:
        st.error(f"Unable to read markdown file {path.name}: {exc}")
    return ""


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


def display_key_takeaways(fact_base: dict) -> None:
    """Display concise patient-facing takeaways from the shared fact base.

    Args:
        fact_base: Dictionary loaded from `data/extracted_fact_base.json`.

    Returns:
        None. The takeaways are rendered directly into the Streamlit page.

    CLARITY pipeline role:
        Provides a short patient-facing summary that is anchored to the same
        structured facts used by every explanation mode. This gives evaluators
        a stable reference point before they compare style-controlled scripts.
    """
    st.markdown("### Key Takeaways")
    takeaways = fact_base.get("key_takeaways", [])
    if not takeaways:
        st.warning("No key takeaways are available in the shared fact base.")
        return

    for takeaway in takeaways:
        st.markdown(f"- {takeaway}")


def display_questions_for_care_team(fact_base: dict) -> None:
    """Display suggested questions for the patient to ask their care team.

    Args:
        fact_base: Dictionary loaded from `data/extracted_fact_base.json`.

    Returns:
        None. The questions are rendered directly into the Streamlit page.

    CLARITY pipeline role:
        Turns the verified fact base into practical discussion prompts. The
        questions are educational and preparatory, not direct medical advice,
        which helps keep the prototype aligned with its patient education role.
    """
    st.markdown("### Questions for Your Care Team")
    questions = fact_base.get("questions_for_care_team", [])
    if not questions:
        st.warning("No care team questions are available in the shared fact base.")
        return

    for question in questions:
        st.markdown(f"- {question}")


def display_version_metadata(metadata: dict) -> None:
    """Render the selected explanation mode metadata.

    Args:
        metadata: Dictionary describing the currently selected explanation
        version, including title, language, communication goal, tone, technical
        detail, and uncertainty detail.

    Returns:
        None. The version metadata is rendered directly into the Streamlit page.

    CLARITY pipeline role:
        Implements Step 3 by making the style-control layer visible. The
        selected mode changes how an explanation is presented, but it should not
        change the underlying shared clinical facts loaded in Step 2.
    """
    st.subheader("Step 3. Choose Explanation Mode")

    if not metadata:
        st.warning("No explanation mode metadata is available yet.")
        return

    st.markdown(f"### {metadata.get('title', 'Selected version')}")
    st.write(metadata.get("communication_goal", "No communication goal provided."))

    language_col, tone_col = st.columns(2)
    language_col.markdown(f"**Language:** {metadata.get('language', 'Not available')}")
    tone_col.markdown(f"**Tone:** {metadata.get('tone', 'Not available')}")

    detail_col, uncertainty_col = st.columns(2)
    detail_col.markdown(
        f"**Technical detail:** {metadata.get('technical_detail', 'Not available')}"
    )
    uncertainty_col.markdown(
        f"**Uncertainty detail:** {metadata.get('uncertainty_detail', 'Not available')}"
    )


def select_explanation_mode(version_metadata: dict) -> tuple[str, dict]:
    """Render the sidebar explanation mode selector.

    Args:
        version_metadata: Dictionary loaded from `data/version_metadata.json`,
        keyed by stable mode identifiers.

    Returns:
        A tuple of `(selected_mode_key, selected_mode_metadata)`. If metadata is
        unavailable, returns an empty key and empty dictionary.

    CLARITY pipeline role:
        Allows the evaluator to switch between the five predefined presentation
        styles required by the interview task. This function is intentionally
        limited to selecting cached/predefined versions; later production work
        could connect these choices to real-time generation after verification
        safeguards are in place.
    """
    st.sidebar.header("Explanation mode")

    if not version_metadata:
        st.sidebar.warning("Version metadata is unavailable.")
        return "", {}

    mode_keys = list(version_metadata.keys())
    labels = {
        key: version_metadata[key].get("title", key.replace("_", " ").title())
        for key in mode_keys
    }
    selected_key = st.sidebar.selectbox(
        "Choose a predefined explanation mode",
        options=mode_keys,
        format_func=lambda key: labels[key],
    )
    return selected_key, version_metadata[selected_key]


def display_future_personalization_controls() -> dict:
    """Render placeholder controls for future patient preference selection.

    Args:
        None.

    Returns:
        A dictionary mapping stable preference names to boolean selections.

    CLARITY pipeline role:
        Shows how participants might eventually choose presentation preferences
        such as simpler language, more technical detail, clearer uncertainty, a
        more reassuring tone, or Spanish language. In this prototype the
        controls intentionally do not regenerate content; evaluators should use
        the five predefined modes until a verified real-time generation pipeline
        exists.
    """
    st.sidebar.header("Future personalization controls")
    st.sidebar.info(
        "These controls are placeholders for future real-time generation. In "
        "this prototype, please use the five predefined modes below."
    )

    return {
        "Make it easier to understand": st.sidebar.checkbox(
            "Make it easier to understand"
        ),
        "Include more technical detail": st.sidebar.checkbox(
            "Include more technical detail"
        ),
        "Explain uncertainty more clearly": st.sidebar.checkbox(
            "Explain uncertainty more clearly"
        ),
        "Use a more reassuring tone": st.sidebar.checkbox(
            "Use a more reassuring tone"
        ),
        "Spanish language": st.sidebar.checkbox("Spanish language"),
    }


def display_personalization_summary(preferences: dict) -> None:
    """Show a non-generative summary of selected future preferences.

    Args:
        preferences: Dictionary returned by
        `display_future_personalization_controls`.

    Returns:
        None. The summary is rendered into the Streamlit page.

    CLARITY pipeline role:
        Makes placeholder personalization choices visible without changing the
        current transcript or video. This avoids implying that the prototype is
        performing live AI generation or clinical verification.
    """
    selected_preferences = [
        label for label, is_selected in preferences.items() if is_selected
    ]

    st.markdown("**Selected preferences summary**")
    if selected_preferences:
        for preference in selected_preferences:
            st.markdown(f"- {preference}")
    else:
        st.write("No future personalization preferences selected.")

    st.caption(
        "Preference controls are placeholders only; the selected predefined "
        "mode determines the script and cached video shown in this prototype."
    )


def display_script(script_path: Path) -> None:
    """Display the selected explanation script or a graceful missing-file note.

    Args:
        script_path: Path to the markdown transcript associated with the
        selected explanation mode.

    Returns:
        None. The transcript or fallback warning is rendered into the page.

    CLARITY pipeline role:
        Implements the transcript half of Step 4. In the prototype, scripts are
        loaded from cached markdown files rather than generated live. This keeps
        the interview demo reproducible and reinforces that style-controlled
        explanation should happen after fact extraction and verification.
    """
    with st.expander("View transcript / script", expanded=False):
        script_text = load_markdown(script_path)
        if script_text:
            st.markdown(script_text)
        else:
            st.warning(
                "No transcript is available for this selected version yet. "
                "Add a markdown file at the path listed in version metadata."
            )


def display_video_or_placeholder(video_path: Path) -> None:
    """Display a cached explainer video or an intentional placeholder panel.

    Args:
        video_path: Path to the cached video file for the selected explanation
        mode.

    Returns:
        None. The video or placeholder message is rendered into the page.

    CLARITY pipeline role:
        Implements the video half of Step 4. The prototype intentionally reads
        cached videos rather than generating videos in real time because video
        generation is slow, expensive, and should follow script verification.
        This function makes that design choice visible while keeping the
        dashboard ready to host generated videos once they are available.
    """
    st.markdown("**Cached video explainer**")

    if video_path.exists():
        st.video(str(video_path))
        return

    # Missing cached video files are expected at this prototype stage. The
    # fallback should look deliberate so evaluators understand the dashboard is
    # prepared for videos, not broken by their absence.
    st.info(
        "Video not generated yet.\n\n"
        "This space will display the 5-10 minute NotebookLM-style explainer "
        "video for the selected version.\n\n"
        "For the current prototype, the dashboard is prepared to host the "
        "generated video once available."
    )


def display_pipeline_transparency() -> None:
    """Display the prototype generation workflow and transparency rationale.

    Args:
        None.

    Returns:
        None. The pipeline explanation is rendered inside a Streamlit expander.

    CLARITY pipeline role:
        Implements the transparency portion of Step 5. It helps interview
        evaluators understand that CLARITY separates note import, fact-base
        creation, style-controlled script drafting, verification, and video
        generation instead of treating the final explainer as a black box.
    """
    with st.expander("How this prototype was generated", expanded=False):
        st.markdown(
            """
1. Import or select a de-identified clinical note.
2. Load a structured clinical fact base.
3. Convert facts into a patient-facing outline.
4. Generate five style-controlled scripts from the same fact base.
5. Verify scripts against the source note for unsupported claims or missing critical information.
6. Convert verified scripts into video explainers.
7. Present cached videos and transcripts through this dashboard.
"""
        )
        st.info(
            "All five versions should come from one shared fact base. This "
            "reduces factual drift when the communication style changes across "
            "language, trust-building, technical detail, and uncertainty framing."
        )


def display_limitations(writeup_path: Path) -> None:
    """Display limitations and next steps from a maintained markdown writeup.

    Args:
        writeup_path: Path to the limitations and next steps markdown file.

    Returns:
        None. The writeup is rendered inside a Streamlit expander.

    CLARITY pipeline role:
        Completes the limitations portion of Step 5 by making prototype
        boundaries explicit. This is important for an interview demo because it
        distinguishes the current local dashboard from a clinically deployable
        production system that would require verification, audit trails,
        privacy controls, translation review, and comprehension testing.
    """
    with st.expander("Limitations and next steps", expanded=False):
        writeup = load_markdown(writeup_path)
        if writeup:
            st.markdown(writeup)
        else:
            st.warning(
                "Limitations writeup is not available. Add the markdown file "
                "under `writeup/` so evaluators can review prototype boundaries."
            )


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

    version_metadata = load_json(VERSION_METADATA_PATH)
    selected_mode_key, selected_mode_metadata = select_explanation_mode(
        version_metadata
    )
    personalization_preferences = display_future_personalization_controls()

    fact_base = load_json(FACT_BASE_PATH)
    display_case_snapshot(fact_base)
    if fact_base:
        takeaway_col, question_col = st.columns(2)
        with takeaway_col:
            display_key_takeaways(fact_base)
        with question_col:
            display_questions_for_care_team(fact_base)
    display_version_metadata(selected_mode_metadata)
    display_personalization_summary(personalization_preferences)

    st.subheader("Step 4. Review Script and Cached Video")
    script_file = selected_mode_metadata.get("script_file") if selected_mode_metadata else ""
    if script_file:
        display_script(APP_ROOT / script_file)
    else:
        st.warning("No script file is configured for the selected mode.")

    video_file = selected_mode_metadata.get("video_file") if selected_mode_metadata else ""
    if video_file:
        display_video_or_placeholder(APP_ROOT / video_file)
    else:
        st.warning("No video file is configured for the selected mode.")

    st.subheader("Step 5. Review Pipeline Transparency, Limitations, and Next Steps")
    display_pipeline_transparency()
    display_limitations(LIMITATIONS_PATH)


if __name__ == "__main__":
    main()
