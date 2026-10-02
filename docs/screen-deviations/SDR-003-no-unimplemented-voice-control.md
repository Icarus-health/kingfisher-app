# Approved screen deviation — no inactive voice control

Approved by the product owner in the implementation conversation on 2026-09-03:
functions that do not work must not be included.

## Start dashboard and conversation composer

- The approved V3 microphone artwork is not rendered until Kingfisher has a
  real, local speech-to-text flow with explicit microphone permission, defined
  storage behavior and an acceptance test.
- The prior active control only displayed a "not yet implemented" notice. It
  has been removed rather than presented as an available feature.
- The approved upward-send arrow remains the sole composer action.

No new icon, fallback, browser speech service or external transcription
provider is introduced by this record.
