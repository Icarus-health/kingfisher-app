# Intake coverage fix 01 review

## Spec compliance

✅ **Spec compliant within the bounded recall task. I1 is resolved.** The corrected read returns a known capture gap first, then a known analysis gap, then generic unverified coverage. The empty result still makes no completeness claim. The two independently unknown states reproduced in review 01 now leave the known analysis notice visible. `sidecar/icarus_memory/mail_intake.py:691`, `:697`, `:708`, `:711`; `sidecar/tests/test_intake_coverage_recall.py:157`

## Code quality

✅ **Approved.** The correction reorders the existing read-only checks and retains current-generation and source-head eligibility, the bound parameters, the shared opcode budget, and cleanup after interruption. A missing or disabled account can make the fallback unverified without masking an observed gap in another account. No change to conversation projection, model history, MCP, or UI is present in this delta. `sidecar/icarus_memory/mail_intake.py:675`, `:688`, `:697`, `:716`

The parametrized authenticated POST/GET test covers an unstarted Archive and a disabled second account. It checks that the analyzed source and its link stay visible, the notice appears in both view contexts and text, the connector and intake processing are untouched, and GET adds neither a model call nor an episode DB write. The retained author logs record two pre-fix failures and 70 affected tests passing after the fix. No suite was rerun for this review. `sidecar/tests/test_intake_coverage_recall.py:157`, `:177`, `:187`; `/private/tmp/kf-intake-coverage-20261105/fix01-red.log`; `/private/tmp/kf-intake-coverage-20261105/fix01-green.log`

**Counts** 0 new findings, 1 resolved important finding. The two earlier minor items remain deferred for the final branch or P2 feedback review. The notice remains transient in ConversationStore and provider history. An explicitly submitted feedback snapshot can still include the displayed suffix, as documented in M1. Native UI interaction and full P1 acceptance remain outside this gate.
