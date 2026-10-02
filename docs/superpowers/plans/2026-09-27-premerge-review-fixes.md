# Kingfisher PR integration repairs
Spec: docs/00-produktvision.md and user authorization on 2026-09-27 to review, fix and merge suitable PRs, prepare Mac testing tomorrow, connectors later.

## Global Constraints
- Personal memory must remain source-bound, current, correctable and withdrawable.
- User choices must never be silently overwritten or discarded.
- No cloud activation, model downloads, external messages, or modifications to user's live data.
- Preserve approved visual design; repair concrete UX defects.
- Source-only project-map conversation paths must work without a connected LLM where implemented.
- Merge is authorized by the user; root performs remote operations only after review and verification.

## Task 1: Repair independently reproduced premerge findings
Checkout: exact upstream 0353712 snapshot in this repository. Combined upstream changes from 985f6ec in ../diffs.json; PR descriptions ../prs.json.
Use systematic-debugging and test-driven-development. Read relevant existing code first.
1. server.py calendar followup dedup omits UID, scopes by localized title/time. Distinct same-title same-time events with identical notes conflate sources. Scope identity to stable occurrence plus content without turning additions into replacing versions. Retrying same note must stay idempotent even if TZ changes. Test distinct UIDs, distinct participants/projects, additions.
2. working_memory_answers render freshness hashes lexical candidates but ignores new semantic-only evidence. Invalidate saved selection when current semantic source inventory changes; rendering must not require embedding provider. Preserve original source controls and avoid stale semantic-only evidence.
3. server.py _search_calendar cached events survive calendar deselection/replacement; old in-flight worker can republish revoked events. Bind cache/workers to calendar instance and source selection generation or current source consent. Test withdrawal, provider replacement, in-flight result retirement without model/network.
4. source_corrections.py carries quoted commitment substring into a new negating block. Preserve old classification only for unchanged complete contextual blocks; otherwise keep full changed block as change. Repro old 'Ich liefere die Druckdaten morgen.' corrected to 'Die folgende Zusage gilt nicht mehr: Ich liefere die Druckdaten morgen.' must not surface old commitment as active.
5. CalendarFollowup.tsx late calendarAssignment overwrites user's project choice; form stays editable while saving then clears newer edits. Guard request/application against touched user choice; disable editable fields/file selection while sending or preserve post-submit edits. Browser validate.
6. App.tsx prevents all chat/source-only map paths when status.chat false, while server reports provider availability. Permit implemented model-free source question/choice paths with honest fallback for genuinely model-required operations. Inspect backend integration before changing.
7. Calendar inactive controls use white background and light foreground in dark scheme. Use existing theme tokens; validate dark contrast and mobile overflow. Preserve approved design.
8. Small UX truthfulness repairs: MemoryStatus must not say all classified when skipped>0; LocalModelSettings classification offer must reference configured confirmed model or clear on unsaved edits. Mappe conditional label 'Bedingte Aussage', not generic 'Bedingte Zusage'.
Write behavioral regression tests for memory/data integrity; no CSS implementation-mirroring tests. Run focused red/green and suite. Root will perform final full verification.
Do not spawn agents. Commit only modified source/tests, not downloaded baseline assets or root-owned docs.
Report with exact files, tests and remaining risks to ../fix-report.md.

