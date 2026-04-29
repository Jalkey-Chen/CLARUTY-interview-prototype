"""Configuration constants for the CLARITY dashboard prototype."""

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = APP_ROOT / "data"
SAMPLE_NOTE_PATH = DATA_DIR / "sample_case_note.txt"
FACT_BASE_PATH = DATA_DIR / "extracted_fact_base.json"
VERSION_METADATA_PATH = DATA_DIR / "version_metadata.json"
WRITEUP_DIR = APP_ROOT / "writeup"
LIMITATIONS_PATH = WRITEUP_DIR / "limitations_and_next_steps.md"
ENV_PATH = APP_ROOT / ".env"
API_TIMEOUT_SECONDS = 60
API_ENABLE_FLAG = "CLARITY_ENABLE_API_CALLS"
PLACEHOLDER_API_HOSTS = {
    "localhost:8000",
    "127.0.0.1:8000",
}

API_ENV_VARS = {
    API_ENABLE_FLAG: "Set to true to call configured API endpoints",
    "OPENAI_API_KEY": "LLM/script generation provider key",
    "LLM_MODEL": "OpenAI model used for direct API mode",
    "NOTE_INGESTION_API_URL": "Future Step 1 secure note ingestion endpoint",
    "FACT_EXTRACTION_API_URL": "Future Step 2 fact extraction endpoint",
    "SCRIPT_GENERATION_API_URL": "Future Step 3 script generation endpoint",
    "VERIFICATION_API_URL": "Future script verification endpoint",
    "VIDEO_GENERATION_API_URL": "Future Step 4 video generation endpoint",
}
