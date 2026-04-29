# Script Generation Prompt Draft

You are supporting the CLARITY workflow: Clinician-Led AI Resources Individualized to You.

## Task

Generate a NotebookLM-style two-speaker patient explainer script from the verified structured fact base.

## Inputs

- Verified clinical fact base.
- Selected communication mode:
  - Balanced / Control
  - Spanish
  - Trust-building
  - Technical + explicit uncertainty
  - Simpler + broad uncertainty

## Requirements

- Use the verified fact base as the source of truth.
- Preserve all clinical facts exactly in meaning.
- Adjust language, tone, technical detail, and uncertainty framing according to the selected communication mode.
- Do not introduce unsupported diagnoses, prognosis, treatment recommendations, or causal claims.
- Do not provide medical advice beyond the note.
- Include a reminder that final content should be reviewed by a clinician.

## Suggested structure

- Title
- Prototype note
- Speaker 1 / Speaker 2 dialogue
- Opening
- Main diagnosis
- What the scans and biopsy showed
- Current and recommended treatment
- What is still uncertain
- Questions to discuss with the care team
- Closing
