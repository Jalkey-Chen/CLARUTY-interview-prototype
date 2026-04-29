# CLARITY Patient Explainer Dashboard

CLARITY stands for **Clinician-Led AI Resources Individualized to You**. This repository contains a local Streamlit prototype for demonstrating how a de-identified clinical note can move through a patient-facing explanation workflow.

The prototype is designed for an interview demo. It prioritizes a clear end-to-end flow, easy local setup, readable source code, and obvious extension points for future script generation, verification, and video production.

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The intended local entrypoint is:

```bash
streamlit run app.py
```

## Project Structure

```text
.
├── app.py
├── README.md
├── requirements.txt
├── .gitignore
├── data/
├── scripts/
├── videos/
├── prompts/
└── writeup/
```

## Current Prototype Goal

The dashboard will be organized as a step-by-step workflow:

1. Import Clinical Note
2. Review Shared Fact Base
3. Choose Explanation Mode
4. Review Script and Cached Video
5. Review Pipeline Transparency, Limitations, and Next Steps

## Planned Capabilities

This prototype is intended to demonstrate how CLARITY could:

- Load or upload a de-identified clinical note. Implemented for `.txt` and `.md` files.
- Load a structured, clinician-verifiable fact base. Implemented with `data/extracted_fact_base.json`.
- Show a patient-facing case snapshot. Implemented from the shared fact base.
- Show key takeaways and suggested questions for the care team from the shared fact base.
- Switch between five explanation modes:
  - Balanced / Control
  - Spanish
  - Trust-building
  - Technical + explicit uncertainty
  - Simpler + broad uncertainty
  Metadata is implemented in `data/version_metadata.json`.
- Display a corresponding transcript/script. Implemented with draft markdown files in `scripts/`.
- Display a cached video when available, with an intentional placeholder when no local video file exists.
- Explain pipeline transparency, limitations, and next steps. Pipeline transparency is implemented in Step 5.

## Placeholders

This repository will intentionally use placeholders for parts of the workflow that should not happen live in the demo:

- Fact extraction will load a pre-verified JSON file rather than calling an external model.
- Scripts will initially be draft markdown files.
- Videos will be read from cached local files if available.
- Missing videos will show an intentional placeholder panel.
- No OpenAI, Gemini, ElevenLabs, HeyGen, or other external API calls are used.

## Interview Task Mapping

The prototype is structured to address the interview task requirements:

- Convert a de-identified clinical case into lay-person explanation materials.
- Support a NotebookLM-style explainer workflow using scripts and cached videos.
- Demonstrate five communication versions.
- Provide controls for future participant-selected presentation preferences.
- Show future personalization controls as placeholders without live generation.
- Clearly document limitations, needed resources, and next steps.

## Notes

The initial file upload flow will support `.txt` and `.md` files. For `.docx` clinical notes, convert the file to plain text first or add `python-docx` support in a future iteration.
