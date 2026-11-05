# Independent calendar cancellation re-review · fix 01

Reviewed `calendar-fix01.diff` against package 01 and the six Important findings in `calendar-cancellation-review.md`. The authorized EpisodeStore change is limited to internal ICS ordering metadata.

- **Specification verdict · Changes required.** Five original cases are addressed. Sparse masters are still handled incorrectly when they include DTSTART. A partially populated revision replay can also discard ordering evidence and let an older active version replace current support.
- **Code-quality verdict · Changes required.** The EpisodeStore transaction makes head changes retryable, and its private revision field preserves the unchanged episode identity. The sparse occurrence projection and the update of known revision fields need correction.
- **Critical · None identified.** The previously deferred combined section workload cap remains Minor and outside this repair.

## Original Important findings

| Finding | Result | Evidence |
| --- | --- | --- |
| 1. Failed head advance blocks retry | **ADDRESSED** | `calendar_memory.py:405`–417 joins record, head advancement, restoration, and revision update in the EpisodeStore transaction. The tested branches retry successfully or preserve a subsequent user exclusion. Claims use a separate transaction, so a failed transition can still leave an affected claim disputed while its episode rolls back. The author reports and tests that boundary. |
| 2. Malformed detached occurrence withdraws its saved head | **ADDRESSED** | `connectors/calendar.py:1068`–1074 retains the unusable memory row through the completeness check at 1178–1183. The job can ingest the healthy neighbor while the earlier occurrence remains current. |
| 3. Publication delta withdraws a neighbor | **ADDRESSED** | `connectors/calendar.py:1147`–1149 marks recognized scheduling methods, including PUBLISH, incomplete. Positive changes can still be applied. |
| 4. Identical legacy replay invalidates unchanged evidence | **ADDRESSED** | `calendar_memory.py:384`–397 updates the technical order without a head transition. `episodes.py:1177`–1195 and 2312–2327 constrain and preserve the private field. The public Episode representation and evidence metadata digest exclude it. The author's regression checks the same ID and both fingerprints, a still-usable accepted claim, restart persistence, and invalidation for an actual content change. A separate ordering regression remains below. |
| 5. Master discards the detached cancellation's actual content | **ADDRESSED** | `connectors/calendar.py:1025`–1029 selects the detached cancellation itself when present. The regression checks its own note, capture stamp, and occurrence start. |
| 6. Sparse master leaves known occurrences active | **NOT ADDRESSED across supported sparse shapes** | `calendar_memory.py:330`–349 correctly ties the new fan-out to the same source, a normalized occurrence key, and a stored raw-UID marker. The author covers both methods for a master without DTSTART, a newer stored exception, an independent literal UID, and ambiguous legacy identity. The timed sparse variants below still fail. |

## Important remaining findings

1. **A sparse master with DTSTART either supplies the wrong occurrence time or leaves occurrences active** · `sidecar/icarus_memory/connectors/calendar.py:972`–976 and `sidecar/icarus_memory/calendar_memory.py:345`–348. I synced a synthetic daily series with two verified stored occurrences on September 8 and 9, revision 1. I sent a revision 2 cancellation for the raw UID with DTSTART and DTEND on September 8, without RRULE or RECURRENCE-ID. With METHOD:CANCEL, the job marked the verified September 9 occurrence cancelled and recorded September 8 as its occurrence time. Without METHOD, the same STATUS:CANCELLED VEVENT was classified as a standalone cancellation and the September 9 occurrence stayed active. The raw UID cancellation may retain the master fields. Per-occurrence cancellation evidence needs to leave start/end empty when its source supplies only the master's schedule. Recognize the STATUS-only master from the verified known series link without inventing additional identities or times.

2. **An unchanged replay can erase a known LAST-MODIFIED and allow stale replacement** · `sidecar/icarus_memory/calendar_memory.py:374`–387. The unchanged-body path replaces the entire revision marker when one field is absent in the latest row, even if ordering ties on SEQUENCE. I synced an active standalone event with SEQUENCE:4 and LAST-MODIFIED September 4. An identical-body replay carrying only SEQUENCE:4 rewrote the revision marker to `4:`. An active copy with the same sequence, LAST-MODIFIED September 3 and a stale location then replaced the current head. Preserve already established ordering components when an unchanged replay omits them. Keep updates to genuinely newer revisions distinct from evidence-preserving replays.

## Verification boundary

I ran a focused synthetic in-process subscription/job reproduction covering both timed sparse variants and the partial-revision replay. I used temporary SQLite stores and did not rerun the author's suite. The author reports 26 dedicated cases and 337 affected cases passing with three TLS cases deselected and one existing warning. The controller's earlier combined and separate TLS runs precede fix 01. Live provider, native UI, project overview and conversation readbacks, and frozen answer grading remain outside this re-review.
