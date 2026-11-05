# P1 explicit calendar cancellation repair

Base `ff2f07513a64dab09735d3dc7831f25000cc9af7`.

## Root cause and RED

Read frozen held-out v2 N05 and N06 as bytes. Passed both into
`connectors.calendar.parse_events` for 2026-11-01 through 2026-12-01 UTC and
then into `KalenderGedaechtnis.abgleichen` under one synthetic calendar source
using temporary SQLite stores. The parser returned one N05 event and no N06
event. Synchronization returned `leer_ohne_entzug=True`. The source key still
pointed to the original N05 episode in state `new`. The assertion that
cancellation replaces that head failed, as expected.

`_gruppe` and `_serie` used one parser projection, which discarded
`STATUS:CANCELLED`. CalDAV and subscription readers passed that result to
`kalender_job` and the memory synchronizer. The empty-section guard could only
see an empty read. A nonempty response might have caused an omission withdrawal
with no cancellation episode as evidence.

Added a separate synthetic development regression file before production
changes. Its initial clean RED was **11 failed, 2 passed**. The two already
passing cases verified that empty and HTTP-error reads preserve existing heads.
Follow-up RED cases isolated METHOD:CANCEL envelope scope, detached exceptions
with no independent cancellation DTSTART, legacy UID ambiguity, a stale active
copy in the display, and an unordered replay that would discard known revision
metadata.

## Interfaces and behavior

- `connectors.calendar.parse_memory_events(ical, von=None, bis=None, *, kodierung="utf-8")`
  returns `CalendarMemoryRead(events, complete)`. Its `Event` records can carry
  cancellation status, explicit ICS ordering metadata, and an actual DTSTAMP.
  The parser honors `STATUS:CANCELLED` and scopes `METHOD:CANCEL` to its VCALENDAR
  envelope. Regular `parse_events(...)` and connector `events(...)` still return
  only displayable events. An explicit winning cancellation excludes a
  contradictory stale active copy from display. Unresolved same-snapshot
  conflicts are omitted for that identity and make the memory read incomplete.
- `CalendarConnector.memory_events(days=7, at=None)` and
  `ICalendarSubscription.memory_events(days=7, at=None)` run the existing
  connector reads and call the memory projection. The CalDAV path admits
  calendar-data from successful propstats and suppresses omission-based
  withdrawals on a partial multistatus. Incomplete ICS envelopes, scheduling
  deltas and partial HTTP responses likewise cannot establish omission.
- `calendar_memory.kalender_job` uses the memory method when available and
  forwards completeness to `KalenderGedaechtnis.abgleichen(..., vollstaendig=True)`.
  Readers that implement only `events(...)` keep their existing contract.
  Cancel-only sections cannot withdraw unlisted neighbors, and subsequent
  omission does not remove an already recorded cancellation. Source
  disconnection can still exclude all evidence for that source.
- Cancellation is an ordinary EVENT episode with an explicit cancelled title
  and body, source-scoped identity, original note and fields, and an existing
  source head. `track_source` invalidates old support and moves that head.
  The original episode remains available historically. A missing DTSTART has
  no fabricated occurrence time. DTSTAMP or LAST-MODIFIED can be the provenance
  capture time when supplied. This uses existing episode text and metadata
  storage, with no schema change or separate calendar version store.
- Explicit SEQUENCE and comparable LAST-MODIFIED distinguish older revisions
  from newer ones. An unordered replay cannot erase an already known
  revision, and equal explicitly ordered active/cancelled states cannot
  replace one another. With no comparable revision in either snapshot the
  existing replacement semantics apply. Replay of an identical cancellation
  keeps its ID. Restoring the previous unversioned active body reuses its
  original episode via the existing reopen path. Newer explicit restoration
  replaces cancellation evidence via the same source version path. A currently
  user-excluded head stays excluded.

## Scope and unresolved cases

Changed production files are `sidecar/icarus_memory/connectors/calendar.py`,
`sidecar/icarus_memory/connectors/collections.py`, and
`sidecar/icarus_memory/calendar_memory.py`. Added
`sidecar/tests/test_calendar_cancellation.py` and adapted two existing calendar
tests' injection points for the new reader path. No intake, frozen corpus,
schema, Google API, or Mac-provider implementation changes.

- A legacy local key such as `series#20260909T100000Z` has no stored raw UID.
  It can be a recurrence from raw UID `series` or a standalone event whose
  literal raw UID is `series#20260909T100000Z`. Where that legacy head is
  encountered, cancellation leaves its existing evidence and state unchanged
  and reports `ICS-Serienkennung nicht eindeutig`. The conflicted read cannot
  withdraw unrelated sources. New ambiguous-shaped identities carry a digest
  of the raw UID as metadata. This requires no new schema and leaves unchanged
  legacy content untouched.
- A series cancellation with a readable RRULE affects the exact normalized
  occurrences expanded in the read window and detached RECURRENCE-IDs supplied
  by the response. A sparse master cancellation without its recurrence rule,
  a vanished exception no longer identified by the rule or response, and
  `RANGE=THISANDFUTURE` do not authorize a guessed set of occurrences. The
  provider may also omit canceled resources altogether from a CalDAV time
  query. No explicit evidence can be recovered from that omission alone.
- A fully framed, unmarked subset returned as an apparently complete HTTP
  response has no signal that distinguishes it from a full snapshot. Detection
  covers explicit scheduling methods, observable truncation, per-resource or
  parser errors, and actual HTTP failures. Existing behavior for complete
  nonempty snapshot omission is retained.
- The synthetic independent deadline control uses a separate document source
  head. The test checks its continued eligibility and the old calendar claim's
  invalidation in real stores. It does not constitute end-to-end PDF admission,
  generated project-overview or answer validation. The dated source input was
  verified independently of any model. Live provider operation, native UI
  acceptance and recall quality remain open.

## Verification

Environment for all runs:

```sh
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:scripts:.
PY=/private/tmp/kf-core-20261104-env/bin/python
```

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short \
  sidecar/tests/test_calendar_cancellation.py
```

The initial broader run exposed stale test injection points. The unexpected
parser error test double did not accept the added memory keyword. The
disconnect route still patched the old display method, so its first run fell
through to the reserved synthetic `.example.test` URL and failed without
saving a calendar episode. It now uses the production reader with an
in-process HTTP mock, so the calendar socket path is never invoked. Another
intermediate run caught a UTF-8 BOM memory regression caused by copying the
byte buffer. The framing check now recognizes the BOM in place. The existing
BOM memory-budget case passed in isolation after that correction.

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short \
  sidecar/tests/test_calendar_cancellation.py sidecar/tests/test_ical_termine.py \
  sidecar/tests/test_kalendergedaechtnis.py sidecar/tests/test_calendar_copies.py \
  -k 'not test_caldav_klappt_serien_im_abgefragten_fenster_aus and not test_caldav_liest_den_kalender_aus_dem_xml_nicht_aus_dem_rohtext'
```

The three excluded existing cases use a real localhost TLS listener. The new
CalDAV multistatus case and the existing raw-response and subscription cases
exercise the connector code with in-process transports. No real provider,
private store, model, GUI, or deployment was used.

Final result was **224 passed, 3 deselected, 1 warning in 17.16 s**. This includes
all 18 new cancellation cases. The warning came from the existing Starlette
TestClient integration. `git diff --check` exited 0.

The frozen N05/N06 post-fix read used the originals as bytes in the production
`ICalendarSubscription` with an in-process `httpx.MockTransport`, then
`kalender_job` and fresh temporary SQLite stores. At 2026-11-05 UTC, N05
reported one new source, N06 reported one changed source, and an identical N06
replay reported one unchanged source. The old ID was excluded as current
support and retained its original body. The new head preserved the original
cancellation note and source-ref UID and was eligible as current evidence.
The live display reader returned an empty event list. This was a source-only
replay of two calendar originals and did not run the held-out answer benchmark.

## Review round 1 repair

Applied all six Important findings in `calendar-cancellation-review.md`.

1. **Retry and user exclusion.** Calendar intake encloses the episode record,
   existing `track_source` call, and restoration in one EpisodeStore
   transaction. Nested source-head writes join that transaction. A failed
   advance rolls back both the new episode and the old episode's ignored
   state. The next read can retry. If the user excludes the old head after
   that failure, the next read respects the exclusion. The claims database
   commits separately, so an affected claim can already be conservatively
   disputed during the interval before retry. Both retry branches verify this
   claim state. Shared `source_versions.py` is unchanged.
2. **Malformed detached occurrence.** The memory parser carries the
   malformed result far enough to mark the read incomplete. Memory skips its
   unusable times, keeps the previously saved occurrence, and processes the
   healthy positive update in the same feed. Legitimate out-of-window
   occurrences still use ordinary window filtering.
3. **Publication delta.** Any explicit METHOD, including PUBLISH, makes the
   section insufficient to infer absence. The listed publication still
   updates its own event.
4. **Unchanged upgrade.** Revision ordering is an internal
   `_calendar_revision` field in the existing episode JSON. The calendar-only
   setter checks that the episode is the current, nonignored calendar head.
   The update does not alter body, metadata digest, generation, or public
   Episode serialization. The normal EpisodeStore write path preserves the
   field. An identical legacy body keeps its episode ID and both snapshot
   fingerprints, and the accepted claim remains usable. A reopen of the
   SQLite store after an ordinary episode write still rejects a stale
   cancellation. A genuinely changed event still displaces the old support
   and disputes its claim. No schema change.
5. **Detached cancellation provenance.** A cancelled master no longer
   substitutes its own note and schedule for a detached VEVENT that supplies
   explicit cancellation evidence. The occurrence's note, DTSTART and
   DTSTAMP survive. A detached occurrence without its own cancellation
   continues to receive the master cancellation without copying the master's
   DTSTART as its occurrence time.
6. **Sparse master.** METHOD:CANCEL, or a sparse STATUS:CANCELLED master
   without DTSTART, can cancel existing occurrences only when the same
   source's current head has a verified raw-UID marker, the normalized
   recurrence reference matches, and the existing per-occurrence revision
   guard permits it. Explicit occurrences in the response keep their own
   projection. A newer detached occurrence, an independently literal UID,
   an unmarked legacy occurrence, unlisted neighbors and hypothetical
   occurrence keys all stay untouched. No recurrence is synthesized from a
   sparse master. The unresolved legacy identity boundary and provider
   omission limitations above still apply. The earlier limitation about all
   sparse masters is superseded by this verified-occurrence handling.

### RED and GREEN commands

With the same Python environment above, before implementing these fixes:

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short sidecar/tests/test_calendar_cancellation.py \
  -k 'failed_calendar_head or malformed_detached or publish_message or unchanged_legacy_upgrade or detached_explicit or sparse_master'
```

**7 failed, 18 deselected.** The retry test covered both a regular retry and
a user exclusion after the injected failure. A follow-up focused RED exposed
the STATUS-only sparse variant specifically, **1 failed, 4 passed, 21
deselected**. Both sparse formats then passed with the exact identity and
version controls.

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short sidecar/tests/test_calendar_cancellation.py
```

**26 passed in 2.21 s.**

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short \
  sidecar/tests/test_calendar_cancellation.py sidecar/tests/test_ical_termine.py \
  sidecar/tests/test_kalendergedaechtnis.py sidecar/tests/test_calendar_copies.py \
  sidecar/tests/test_episoden.py sidecar/tests/test_episode_support.py \
  sidecar/tests/test_episode_zugriffe.py sidecar/tests/test_source_versions.py \
  -k 'not test_caldav_klappt_serien_im_abgefragten_fenster_aus and not test_caldav_liest_den_kalender_aus_dem_xml_nicht_aus_dem_rohtext'
```

**337 passed, 3 deselected, 1 existing Starlette warning in 26.57 s.**
`git diff --check` exited 0. The frozen two-original in-process source replay
also returned new=1, changed=1, identical replay unchanged=1, with the
original preserved and excluded as current, the cancellation eligible, and
the live list empty. This round used no real-provider request or model.

### SHA-256 inventory

```text
8e4e25eca3e7d669ee03b590c19b1be232b54e29297be4eeee7b6c088ab3cc45  sidecar/icarus_memory/calendar_memory.py
0ab5461e57ba01354327f28e0cb4a1ac31bd97b24546ca27158a41438f36d4e0  sidecar/icarus_memory/connectors/calendar.py
d87f38b08a5223b0570f138682f429ed5848b5b4bbb055c4f85157a71503abbf  sidecar/icarus_memory/connectors/collections.py
573f4a36349c53271a3f002b7602c0b1813f9dd4d4aa53e5132d7f5af28f6076  sidecar/icarus_memory/episodes.py
f83ccdceecdbea49ee44705ca506477630045110abaed87b8ea550afa7b758c8  sidecar/tests/test_calendar_cancellation.py
fc84b6ad6efb20d1646e0f50462c2a3dc4a983459cb4ba84cc435d493c50d4f3  sidecar/tests/test_ical_termine.py
4d6bd815d40a1191913d5329fcbc7f6b459501693f99a8add3ddf357ce35b4b9  sidecar/tests/test_kalendergedaechtnis.py
```

The EpisodeStore change above was explicitly scoped to its calendar revision
field. The separate combined dated/undated workload-cap finding remains
deferred. No frozen fixture, intake script, workflow or public run artifact
was edited in this repair round.

## Review round 2 repair

Addressed both Important findings in `calendar-fix01-review.md`.

- A cancelled raw master without a recurrence rule or RECURRENCE-ID can
  match existing, verified occurrence keys whether it is delivered as
  METHOD:CANCEL or as STATUS:CANCELLED alone. The raw master keeps its own
  DTSTART and DTEND. A cancellation projected from that master onto an
  existing occurrence carries its content and source provenance without the
  master's schedule. An explicit detached cancellation retains its own
  time and content. A read that projects cancellations onto known occurrences
  does not use omission to withdraw other events. The tests check both
  timed sparse formats, two dated prior occurrences, the raw master time,
  undated occurrence evidence, a retained neighbor and no invented key.
- A partial replay with the same body, same cancellation status and tied
  revision order can fill gaps in the incoming order from the established
  revision. The reverse-direction check covers omitted SEQUENCE as well
  as omitted LAST-MODIFIED. An explicitly newer revision starts its own
  order without inheriting an omitted value from the preceding revision.
  These writes leave the evidence head and support fingerprint intact.

Only `calendar_memory.py`, `connectors/calendar.py`, and the dedicated
cancellation tests changed from the previous snapshot. The private
EpisodeStore metadata and its transaction behavior are unchanged.

### RED and GREEN commands

With the same Python environment above:

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short sidecar/tests/test_calendar_cancellation.py \
  -k 'timed_sparse or partial_revision_replay or higher_sequence_can_start'
```

Before the fix, **4 failed, 1 passed, 26 deselected**. The four failures
were the two timed-master cases and the two dropped ordering components.
The already-passing case guards the distinct higher-SEQUENCE behavior.
After the fix, **5 passed, 26 deselected in 0.65 s**.

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short \
  sidecar/tests/test_calendar_cancellation.py sidecar/tests/test_episode_support.py \
  sidecar/tests/test_source_versions.py

"$PY" -m pytest -q -p no:cacheprovider --tb=short \
  sidecar/tests/test_ical_termine.py sidecar/tests/test_kalendergedaechtnis.py \
  -k '(abgesagt or gedaechtnis or fassung or replay or wiederherstellt) and not test_caldav_klappt_serien_im_abgefragten_fenster_aus and not test_caldav_liest_den_kalender_aus_dem_xml_nicht_aus_dem_rohtext'
```

The first command returned **112 passed, 1 existing Starlette warning in
10.17 s**, including all 31 cancellation cases. The selected calendar
regressions returned **35 passed, 162 deselected, 1 existing Starlette
warning in 3.39 s**. `git diff --check` exited 0. Only synthetic in-process
transport and test databases were used in this round.

### SHA-256 inventory

```text
00a175f94e10cba041f264e30fe9f037559bc91516bbd5e80f7931fe9ced098c  sidecar/icarus_memory/calendar_memory.py
bd21d54296e57e333829a567ef0aa8cc8e4e3f4a544ed92c18e9c88660d5e449  sidecar/icarus_memory/connectors/calendar.py
d87f38b08a5223b0570f138682f429ed5848b5b4bbb055c4f85157a71503abbf  sidecar/icarus_memory/connectors/collections.py
573f4a36349c53271a3f002b7602c0b1813f9dd4d4aa53e5132d7f5af28f6076  sidecar/icarus_memory/episodes.py
285cac58debb94afb188cfeb7eed8e6bc3ba10f0e21ba93953f7a7a2469ef403  sidecar/tests/test_calendar_cancellation.py
fc84b6ad6efb20d1646e0f50462c2a3dc4a983459cb4ba84cc435d493c50d4f3  sidecar/tests/test_ical_termine.py
4d6bd815d40a1191913d5329fcbc7f6b459501693f99a8add3ddf357ce35b4b9  sidecar/tests/test_kalendergedaechtnis.py
```

## Review round 3 repair

Addressed both Important findings in `calendar-fix02-review.md`.

- A sparse cancellation candidate makes the read incomplete for omission,
  regardless of DTSTART, scheduling method, or the number of verified
  occurrence links. The framing decision is made in the parser before any
  reconciliation. Positive evidence from the raw master and other valid rows
  is still saved. A method-free timed master with only unmarked legacy
  occurrences preserves those heads and the unlisted neighbor. The reader
  neither infers a legacy raw UID nor creates an occurrence key.
- A revision that passes the existing stale/conflict checks keeps established
  ordering components that the input omits. A newer secondary timestamp
  can advance LAST-MODIFIED while retaining the known primary SEQUENCE.
  Only an explicit increase from a known SEQUENCE starts a new primary
  revision that can leave its secondary timestamp unset. This rule also
  protects a legitimate content change within the same SEQUENCE from a
  later stale same-sequence copy. The unchanged-content regression table
  covers omitted primary with equal and newer secondary, omitted secondary,
  both omitted, lower primary with a later secondary, and a separate higher
  primary case. The replay cases assert that the original public episode and
  evidence fingerprint remain intact.

### RED and GREEN commands

With the same Python environment above:

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short sidecar/tests/test_calendar_cancellation.py \
  -k 'without_verified_fanout or partial_revision_replay or higher_sequence_can_start or same_sequence_change'
```

RED was **3 failed, 5 passed, 28 deselected in 0.92 s**. The reproduced
failures were omission with zero verified fan-out, loss of the primary
revision when the secondary advanced, and loss of the secondary on a
same-primary content change. GREEN was **8 passed, 28 deselected in 0.82 s**.

```sh
"$PY" -m pytest -q -p no:cacheprovider --tb=short \
  sidecar/tests/test_calendar_cancellation.py sidecar/tests/test_episode_support.py \
  sidecar/tests/test_source_versions.py

"$PY" -m pytest -q -p no:cacheprovider --tb=short \
  sidecar/tests/test_ical_termine.py sidecar/tests/test_kalendergedaechtnis.py \
  -k '(abgesagt or gedaechtnis or fassung or replay or wiederherstellt) and not test_caldav_klappt_serien_im_abgefragten_fenster_aus and not test_caldav_liest_den_kalender_aus_dem_xml_nicht_aus_dem_rohtext'
```

The first command returned **117 passed, 1 existing Starlette warning in
10.33 s**, including all **36** dedicated cancellation cases. The selected
calendar regressions returned **35 passed, 162 deselected, 1 existing
Starlette warning in 3.52 s**. `git diff --check` exited 0.

Only `calendar_memory.py`, `connectors/calendar.py` and
`test_calendar_cancellation.py` changed from fix 02. The existing
legacy-identity, provider, UI and downstream acceptance boundaries carry
forward. This round used synthetic in-process transport and test databases.

### SHA-256 inventory

```text
b9368272a7674f61a9f41367fbf3fd1f15d2176e5b270ea2fd4e6af2c6d3ae65  sidecar/icarus_memory/calendar_memory.py
4a4530e825dae6c95a2db277c68b5a471a07ec80a3045a2477a9572293a0fd3e  sidecar/icarus_memory/connectors/calendar.py
d87f38b08a5223b0570f138682f429ed5848b5b4bbb055c4f85157a71503abbf  sidecar/icarus_memory/connectors/collections.py
573f4a36349c53271a3f002b7602c0b1813f9dd4d4aa53e5132d7f5af28f6076  sidecar/icarus_memory/episodes.py
8e10ccadaf0cb17805ded737519e32370c2fb52c6987f75d8467229a14cceea9  sidecar/tests/test_calendar_cancellation.py
fc84b6ad6efb20d1646e0f50462c2a3dc4a983459cb4ba84cc435d493c50d4f3  sidecar/tests/test_ical_termine.py
4d6bd815d40a1191913d5329fcbc7f6b459501693f99a8add3ddf357ce35b4b9  sidecar/tests/test_kalendergedaechtnis.py
```
