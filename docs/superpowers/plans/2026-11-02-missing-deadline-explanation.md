# Missing deadline explanation and bounded source pilot

**Goal:** Explain that a requested deadline is not established without claiming the archive contains no information; retain relevant conditional timing evidence. Then validate a four-source Sonnet pilot while the bulk import stays paused.

**Architecture:** Reuse the current selection schema, source bindings, freshness checks and unknown-answer status. Clarify the existing selector instruction. Give unknown questions a query-neutral, scoped explanation; do not infer a date or promote unselected candidates. Use existing source-analysis/category/task validators for the private pilot.

**Tech stack:** Existing Python sidecar, pytest, stored Anthropic API access; no new dependencies.

**Authorization:** User explicitly requested the repair and a small Sonnet source package. No plugin architecture implementation. No bulk import or permanent cloud activation. Private source content stays out of commits and reviewers. Pilot plus follow-up API work is capped at USD 0.50 before each send.

## Task 1: Deadline explanation

- [ ] Add a failing regression using real source stores and the normal prepare/render path.
- [ ] Cover conditional timing, unknown selection, incomplete search, source withdrawal, ordinary non-deadline questions and unrelated date fields.
- [ ] Add only a query-neutral missing-evidence explanation and clarify the existing selector instruction. Keep candidate/page/context limits, statuses and provenance unchanged.
- [ ] Verify red/green and affected source-selection, semantic-coverage and answer tests. Verify the actual previously inconsistent private query separately; synthetic replies do not prove model compliance.

## Task 2: Four-source private pilot

- [ ] Inventory current eligible pending sources locally, apply the existing cheap mail filter, select four diverse supported sources, preserve fingerprints and originals.
- [ ] Run Sonnet on a protected copy through normal analysis/category/task validators with cumulative request-level cost reservations.
- [ ] Review people as mentions versus identities, task owner, explicit/relative/conditional dates and historical status. Preserve unresolved cases; do not auto-confirm tasks or person merges.
- [ ] Only promote inspected results if the personal source versions still match, using normal validators and a fresh backup; otherwise retain the review as a copy-only result.
- [ ] Verify personal local models, account connections and global pause, and record exact cost and remaining gaps.

## Review focus

- Unknown deadline evidence must never become a universal absence claim.
- An employment start or appointment must not become a return deadline.
- Source retraction and changed source versions must invalidate saved answers.
- The pilot may not resume background import, alter local model roles, or confirm guessed identities/tasks.
- No paid retry or request beyond the cumulative USD 0.50 cap.

## Task 3: Concrete issues found by the four-source quality check

- [ ] Restore a unique original mail span when one complete known HTML entity is physically wrapped; preserve quotation-prefix proof, word/number boundaries, single decoding and ambiguity rejection. Do not normalize arbitrary broken words, blank paragraphs, unknown entities or non-mail documents.
- [ ] Clarify both category-analysis prompts: a product/app/subscription name alone is not a project; omit names that fit no supported entity type. No hardcoded brands or new entity types.
- [ ] Reuse already paid exact API responses for validation; pay only for genuinely new semantic review or changed category prompts within the same USD 0.50 total.
- [ ] Keep the actual source currentness, task owner, date and no-active-task checks. A global scan that did not visit the four sources is not a successful task check.
