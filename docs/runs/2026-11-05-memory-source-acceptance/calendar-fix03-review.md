# Independent calendar cancellation re-review · fix 03

Reviewed `calendar-fix03.diff` against the two open Important findings in `calendar-fix02-review.md`. The SHA-256 hashes of all three changed files match the author's inventory.

- **Specification verdict · Pass for the scoped calendar cancellation repair.** Both remaining findings are addressed. The five previously closed findings carry forward.
- **Code-quality verdict · Pass for this repair.** The parser owns omission eligibility, and revision merging happens after the existing stale and conflict checks. No new blocking finding in the fix.
- **Severity · No Critical or Important items remain in scope.** The combined dated and undated workload cap remains a deferred Minor from the initial review.

## Findings

1. **Timed sparse cancellation with only unmarked legacy occurrences · ADDRESSED** · `sidecar/icarus_memory/connectors/calendar.py:1178`–1184 and `sidecar/icarus_memory/calendar_memory.py:285`–292. A sparse cancellation candidate makes the ICS memory read incomplete even if DTSTART is present and the reconciliation finds zero verified occurrences. The production memory job already forwards that flag. Positive evidence can still enter the store. Neither the raw UID marker requirement nor the rule clearing the master's time on projected occurrences changed. The added production-path test at `sidecar/tests/test_calendar_cancellation.py:485` records legacy episodes, supplies a timed STATUS-only master and a separate positive update, and checks that both legacy heads and the unlisted neighbor survive. The conservative rule also delays omission when a cancellation without RRULE or RECURRENCE-ID is actually standalone. A later complete read can establish absence.

2. **Later LAST-MODIFIED-only replay drops a known SEQUENCE · ADDRESSED** · `sidecar/icarus_memory/calendar_memory.py:374`–395. A later comparable LAST-MODIFIED without SEQUENCE now advances the timestamp while keeping the known sequence. The stale lower-SEQUENCE copy therefore compares lower, even with a later timestamp. A same-sequence content change can retain its previous timestamp if the input omits it. Only a higher explicit SEQUENCE resets the prior sequence interval's timestamp. The expanded regression table checks both missing fields, stale copies ordered by either field, the unchanged public episode and the support fingerprint. The higher-SEQUENCE test checks the legitimate reset.

## Verification boundary

I inspected the fix and its tests and verified the changed-file hashes. I did not rerun the author suite. The author reports 8 targeted cases, 117 broader cases including all 36 dedicated cancellation cases, and 35 selected calendar regressions passing on this snapshot. The existing warning and TLS exclusions are recorded in the author's report. Ambiguous legacy identity remains intentionally unresolved, and provider omission can still leave no explicit cancellation evidence. Live provider operation, native UI, downstream project and conversation readbacks, frozen answer grading, and release acceptance remain separate.
