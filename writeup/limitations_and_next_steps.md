# Limitations and Next Steps

## Current limitations

- This is a prototype, not medical advice.
- Real patient-facing use requires clinician review before deployment.
- Spanish versions require review by a bilingual clinician or certified medical translator.
- Production deployment would need HIPAA-compliant storage and processing.
- Generated scripts need audit trails linking each claim back to the clinical source.
- Video generation should happen only after script verification.
- Patient comprehension testing is needed before deployment.
- The current prototype uses cached or placeholder videos rather than real-time video generation.

## Needed resources

- Final clinician-approved clinical case note and structured fact base.
- Final scripts for all five communication versions.
- Verification workflow comparing scripts against the source note and fact base.
- Reviewed Spanish-language materials.
- Generated and captioned video files for each selected mode.
- A secure deployment plan if any real patient information is ever processed.

## Practical next steps

1. Finalize the structured fact base with clinician review.
2. Revise the five scripts using the shared fact base.
3. Run verification to flag unsupported claims, missing critical information, and overconfident uncertainty language.
4. Generate videos only after scripts are verified.
5. Add cached `.mp4` files to the `videos/` directory for local demo playback.
6. Conduct patient comprehension testing before any real-world patient-facing use.
