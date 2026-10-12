# SDD ledger — plan: docs/superpowers/plans/2026-10-09-cos-source-preview.md

Pre-flight: Task 1 → Task 2 consumes frozen code and UI build; exact revision/version required. Shared api.ts and MemoryStatus.tsx auto-merged without conflicts; independent review required. Previous packaged evidence is historical, not proof for this revision.
Task 1: source merges complete at 26e2bda2860a3c5b65c36e666d2a4344b70fd39d; archive pinned. Tests: 195 backend pass/1 platform skip; 480 UI pass; build passed. Not final after review finding.
Final review: existing read-only reviewer found one Important visibility race in Coverage poller. Hidden tab can adopt late response; initial visibility check only. Other integration interfaces no concrete blockers. No reviewer runtime tests. Reproduce before fix, then freeze/test final revision.

Task 1: complete — final UI fix 173cef8; five review regressions RED→GREEN; seven component cases and full 485 UI green, clean archive 28 cases/build green. 195 backend passed/1 platform skip at 26e2bda with tracked backend byte identity verified at 173cef8.
Final: fixed visibility race including action rereads — tests hidden-success/hidden-failure/quick-return/action-success/action-failure RED→GREEN. Source-regex assertion replaced by functional interval/timeline/unmount proof. No remaining important findings; no runtime rereview.
Task 2: complete — native ARM build, strict deep codesign, DMG checksum, base-layer and version/content pairing verified; actual isolated image probe passed. First probe fixture retained legitimate browser cookie; corrected cookie clearing and final passed. Prepared 1.0.6-preview.173cef8, not installed.
Finish: existing authorized integration branch retained and pushed; no main merge or public release; actual window/quality/resource requirements remain open.
