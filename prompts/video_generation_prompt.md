# Video Generation Prompt Draft

You are supporting the CLARITY workflow: Clinician-Led AI Resources Individualized to You.

## Task

Convert a verified script into a 5-10 minute explainer video plan.

If this plan will be used with NotebookLM, do not upload the raw structured
JSON script directly. First convert the script into a NotebookLM-ready source
document that contains the style brief, voiceover, scene directions, and minimal
on-screen text. NotebookLM may treat JSON keys, checklists, and bullet arrays as
source content instead of strict directing instructions.

## Requirements

- Use only the verified script.
- Use calm visuals that support comprehension without implying unsupported findings.
- Avoid misleading anatomical visuals.
- Do not imply visual findings not present in the source note.
- Include captions.
- Include clear speaker turns if using a two-speaker format.
- Keep pacing patient-friendly and avoid overwhelming the viewer.
- Preserve uncertainty language exactly where the verified script uses it.

## Visual Style Guidance

The video may use clean slide-like layouts when helpful, especially for
section transitions, key terms, treatment steps, and summaries. However, it
should not rely only on text-heavy bullet slides.

The goal is a hybrid patient explainer: clean slides plus meaningful visuals,
not a strict animation-only video and not a text-only slide deck.

When the script explains spatial, causal, temporal, monitoring, treatment, or
uncertain information, prefer adding simple visuals that help the patient
understand the relationship:

- body-location diagrams
- simple anatomy maps
- timelines
- cause-and-effect arrows
- treatment pathways
- monitoring calendars
- uncertainty branches
- medication cards
- test-result cards with icons
- simple icons connected spatially

On-screen text is allowed, including short bullets when they clarify key terms,
treatment steps, or summary sections. The text should support the narration
rather than replace it. Avoid long paragraphs, dense medical notes, or screens
that repeat the full narration.

For each scene, combine:

1. a clear layout,
2. a small amount of helpful text,
3. at least one visual element when the content would benefit from a diagram,
   map, timeline, arrow, pathway, icon, or uncertainty branch.

Keep the screen calm and uncluttered. Use motion, highlighting, arrows,
zoom-ins, or simple transitions to guide attention without making the video feel
busy.

## Output

Return a video production plan with:

- Scene outline
- Speaker or narration timing
- Suggested visual style
- Structured visual plan for each scene:
  - visual_type
  - main_visual
  - motion_or_transition
  - patient_comprehension_goal
  - minimal_on_screen_text
  - anti_slide_instruction
  - visuals_to_avoid
- Caption notes
- Accessibility notes
- Required clinical review checkpoints

## Safety constraints

- Video generation should happen only after script verification.
- Do not add new claims during visual planning.
- Do not use visuals that make uncertain findings appear confirmed.
- Do not show doctors, clinicians, nurses, white coats, stethoscopes, hospital
  staff, or doctor-patient consultation scenes.
- Do not imply that a clinician avatar or medical authority figure is delivering
  the message.
