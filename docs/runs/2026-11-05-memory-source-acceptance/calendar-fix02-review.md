# Independent calendar cancellation re-review · fix 02

Reviewed `calendar-fix02.diff` against the two open findings in `calendar-fix01-review.md`. The previous five closures carry forward. The deferred Minor workload cap is outside this round.

- **Specification verdict · Changes required.** The original timed sparse and tied revision replays now work. Two adjacent cases still violate the same requirements for incomplete reads and stale evidence.
- **Code-quality verdict · Changes required.** The new tests cover the direct repros. The guards still depend on actual fan-out or on a comparison that can equate a later secondary timestamp with a fully ordered new revision.
- **Critical · None identified.**

## Important

1. **Timed sparse master · NOT ADDRESSED across legacy identity states** · `sidecar/icarus_memory/calendar_memory.py:289`–292, 345–353, `sidecar/icarus_memory/connectors/calendar.py:1179`–1183. For verified occurrences, both timed cancellation forms now retain the date on the raw master, leave each projected occurrence undated, and suppress omission. When only unmarked legacy occurrence heads exist, there is deliberately no verified fan-out. The timed, method-free cancellation therefore leaves `complete=True`, and an active neighbor authorizes withdrawal by omission. I stored two legacy occurrences and an unrelated neighbor using the pre-fix display projection. I then synced a timed, method-free STATUS:CANCELLED master without RRULE or RECURRENCE-ID and the healthy neighbor through the real subscription job. It reported `entzogen=2`, and the previously current September 9 occurrence became ignored. An unmarked occurrence-shaped key must stay in its current state when the cancellation cannot verify its association. Suppress omission when a timed sparse master may refer to those ambiguous heads, even when no explicit projection is emitted.

2. **Partial revision replay · NOT ADDRESSED across comparison paths** · `sidecar/icarus_memory/calendar_memory.py:379`–400. The merge now preserves known fields for an equal-order, unchanged-body replay and correctly allows a higher explicit SEQUENCE to start without the previous sequence's timestamp. A later LAST-MODIFIED without SEQUENCE, however, compares greater using the secondary field and takes the replacement branch. I synced an active event with SEQUENCE:4 and LAST-MODIFIED September 4, then the same body with only LAST-MODIFIED September 5. The private revision changed to `:2026-09-05T12:00:00+00:00`. A subsequent SEQUENCE:3 copy with LAST-MODIFIED September 6 and a stale location reported `geaendert=1` and replaced the head. Preserve the known sequence on a same-content replay that advances only the secondary stamp, while allowing a strictly higher explicit sequence to reset the timestamp.

## Evidence and boundaries

Both remaining behaviors were observed in focused synthetic production subscription/job calls using temporary SQLite stores and in-process HTTP. I did not rerun the author's tests. The author reports 5 dedicated selected cases, 112 broader cases, and 35 selected calendar cases passing for this fix. This review provides no new evidence for live providers, UI, downstream recall or release acceptance.
