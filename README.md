# CLARITY Patient Explainer Dashboard

CLARITY stands for **Clinician-Led AI Resources Individualized to You**. This repository contains a local Streamlit prototype for demonstrating how a de-identified clinical note can move through a patient-facing explanation workflow.

The prototype is designed for an interview demo. It prioritizes a clear end-to-end flow, easy local setup, readable source code, and obvious extension points for future script generation, verification, and video production.

## Run Locally

```bash
uv run streamlit run app.py
```

For future API-backed integrations, copy the environment template and fill in
local values:

```bash
cp .env.example .env
```

You can also use a standard Python environment:

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
├── src/
│   └── clarity_dashboard/
│       ├── api.py
│       ├── config.py
│       ├── env_config.py
│       ├── io_utils.py
│       └── ui.py
├── data/
├── scripts/
├── videos/
├── prompts/
└── writeup/
```

`app.py` is intentionally kept as the Streamlit workflow entrypoint. Supporting
logic is split into `src/clarity_dashboard/` so API calls, document parsing,
configuration, and UI rendering can evolve independently.

## Current Prototype Goal

The dashboard is organized as a step-by-step workflow:

1. Import Clinical Note
2. Review Shared Fact Base
3. Choose Explanation Mode
4. Review Script and Cached Video
5. Review Pipeline Transparency, Limitations, and Next Steps

## Planned Capabilities

This prototype is intended to demonstrate how CLARITY could:

- Load or upload a de-identified clinical note. Implemented for `.txt`, `.md`, and `.docx` files.
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
- Explain pipeline transparency, limitations, and next steps. Pipeline transparency and limitations are implemented in Step 5.

## Demo Guide

1. Load the sample clinical note.
2. Review the shared clinical fact base.
3. Switch between five explanation modes in the sidebar.
4. Open the transcript panel.
5. Notice that the video panel is ready for cached generated videos.
6. Review pipeline transparency, limitations, and next steps.

## Demo Mode vs API Mode

- Selecting the built-in sample case uses local demo assets: `data/`, `scripts/`, and cached files in `videos/`.
- Uploading a `.txt`, `.md`, or `.docx` file switches the workflow into API mode.
- Live API calls remain disabled until `CLARITY_ENABLE_API_CALLS=true` is set in `.env`.
- In API mode, Step 1 can call `NOTE_INGESTION_API_URL`, Step 2 calls `FACT_EXTRACTION_API_URL`, Step 4 calls `SCRIPT_GENERATION_API_URL`, optional `VERIFICATION_API_URL`, and `VIDEO_GENERATION_API_URL`.
- API mode does not silently fall back to the sample fact base, sample scripts, or sample video paths.
- The current app expects JSON POST endpoints. Common response fields are documented in the code and can be adapted as the backend stabilizes.

## Placeholders

This repository will intentionally use placeholders for parts of the workflow that should not happen live in the demo:

- Fact extraction will load a pre-verified JSON file rather than calling an external model.
- Scripts will initially be draft markdown files.
- Videos will be read from cached local files if available.
- Missing videos will show an intentional placeholder panel.
- Prompt drafts live in `prompts/` for future fact extraction, script generation, verification, and video generation.
- `.env.example` documents future API keys and endpoints; `.env` is ignored by git.
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

The initial file upload flow supports `.txt`, `.md`, and `.docx` files. For older `.doc` files, convert the document to `.docx` or plain text before upload.
