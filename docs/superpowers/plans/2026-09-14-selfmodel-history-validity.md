# M1b: User profile corrections invalidate derived conversation input

Use superpowers:subagent-driven-development. This bounded evidence repair follows
M1 ClaimStore review and precedes M2 retrieval: a user's changed preferences must
not survive through stale assistant replies. Existing user authorization covers
implementation, tested integration and app update; no new profile store or model.

## Reproduced failure

SelfModel preference expiry/retraction removes the fresh context item, but earlier
assistant derivations remain model-visible in the same Agent and after persisted
conversation reload. Also reproduced with a fake external provider for an ordinarily
shareable preference. All probes synthetic, no network. Audit and reproduction
provided to implementer separately. This is not a claim that local-only facts were
exported by that reproduction; it is temporal/state validity within permitted history.

## Implementation

- Add bounded, versioned, application-owned SelfModel input lineage alongside existing
  ClaimStore lineage. Record ALL input assertions, not only cited output. Retain ID,
  a canonical content/state fingerprint and the supplied currency/state; do not store
  duplicate plaintext or treat model-produced metadata as authoritative.
- Resolve through authoritative SelfModelStore by ID (add a small read method if needed,
  avoid scanning the complete store for every root). One explicit instant per validation.
  Expired, future, missing, retracted, redacted, superseded, content/sensitivity change
  or currency transition invalidates old derived model history. A legitimately supplied
  disputed/outdated item remains usable only in that same explicitly qualified state;
  do not silently promote it to current fact or drop supported dispute behavior.
- Revalidate before/after provider calls, after provider errors and before tools, just
  like ClaimStore lineage. Include prior-only roots and approval follow-up paths.
  Preserve displayed history; withhold stale generated output with existing retry/reset.
- Rebuild both lineages after latest reset in load_history. Legacy/malformed SelfModel
  lineage is unknown, not verified-empty; conservatively omit and persist reset. Clear
  both accumulators wherever history clears, preserve stable valid round/reload history.
- Keep retrieval/profile floor/sensitivity ceilings and existing local/cloud egress and
  taint policy. Invalidation must never widen data sharing. Update explicit positive
  fixtures to valid versioned metadata; retain missing-marker negative controls.
- Current conversation context cards must filter invalid plain SelfModel IDs; use the
  same current source-chain validation for claim cards, which currently check status
  only. Historical message text/metadata remain inspectable as history, not rewritten.

## Acceptance

- [ ] Red/green tests for same-Agent and persisted preference expiry/retraction.
- [ ] Time-only expiry without materializing status first; provider-duration mutation
      blocks both reply and returned tool, including a prior input absent from fresh context.
- [ ] Stable preference/qualified dispute preserved; changed currency/status/content resets.
- [ ] Normal external history and local-to-cloud/sensitive/special-category boundaries retained.
- [ ] Current API context cards exclude invalid profile facts and ignored-source claims;
      visible old messages remain stored. Restart does not resurrect them as model input.
- [ ] Scoped metadata bounds/malformed/legacy cases, all reset and approval return paths.
- [ ] Focused and full suites; independent immutable review; Docker/actual local model test.

## Limits

This extends authoritative SelfModel assertion validity, not a full provenance resolver
for arbitrary tools, emails or descriptive source_ref strings. It does not claim complete
backup forgetting, all-domain profile learning, safe emotional inference, automatic
identity merging or model semantic qualification. Explicit temporal/context state rules
remain visible; conservative reset can lose conversational convenience after a correction.
