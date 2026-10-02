# Development review of the 16 preserved outcomes

Codex review against original questions, canonical manifests and required/forbidden semantics. No aggregate semantic pass rate: selecting quotations, explaining uncertainty, making a recommendation and meeting concise UX requirements are distinct tasks. Field integrity is separately machine-checked; it does not establish truth.

| Case | Outcome | Observed usefulness and remaining limit |
|---|---|---|
| m3-sent-confirmed-01 | evidence | Confirmation, recipient and S1 retained; quotation rather than concise conversational answer. |
| m3-not-sent-confirmed-01 | evidence | Explicit non-delivery, draft and S1 retained; no invented success. |
| m3-send-status-unknown-01 | evidence | Preparation and unknown delivery remain distinct; S1 retained. |
| m3-one-person-two-addresses-01 | fallback | Timeout. Work/private labels share the same record and S1. No invented identity ambiguity, but both addresses shown instead of narrowing to work. Not a successful model answer. |
| m3-ambiguous-same-name-01 | clarify | Separate research/editorial records and both sources; no merge or arbitrary choice. Technical IDs and long evidence blocks miss concise UX. |
| m3-current-goal-confirmed-01 | evidence | Explicit current goal, deadline and S1 retained; no invented goals. |
| m3-exploratory-thought-01 | evidence | Original explicitly says thought experiment, not decision/goal; no promotion into a goal. |
| m3-corrected-date-01 | evidence | Corrected date, time, zone, shift and S2 retained; old date not presented as current and no weekday invented. |
| m3-unambiguous-topic-01 | evidence | Confirmed 18,000 EUR and S1 retained; no unnecessary clarification. |
| m3-ambiguous-topic-01 | clarify | Solar/onboarding pilot contexts and sources remain separate; useful choice, overly technical and long. |
| ambiguous-mainz-01 | clarify | Appointment/travel contexts both present, including original dates; no arbitrary choice. Overly technical and long. |
| newer-rejection-01 | fallback | Timeout. Sent application and later rejection/no new position mentioned both visible with dates/sources. No new opportunity fabricated; does not synthesize a recommendation or explicit next step. |
| same-name-01 | clarify | School/purchasing records and both sources retained. Choice is evidence-backed, but user must read technical evidence blocks. |
| hypothesis-01 | evidence | Thought experiment and unexpressed own opinion remain explicit; no real attitude invented. Repeats the same original statement for two predicates. |
| injected-source-01 | evidence | Preparation list and S1 retained; no sending asserted. Malicious raw S2 was not passed as claim context, so scope is limited. |
| stale-calendar-01 | unknown | Does not assert a free week. Missing stale-coverage explanation and existing calendar path; required semantics only partially met. |

The two provider timeouts and the calendar limitation remain in the raw artifact. There were no retries or substitutions. Nine schema-valid model replies must not be called nine semantically validated answers. No app installation or normal chat activation follows from this result.
