# M1d Python 3.10 compatibility review addendum — final guarded normalization

**Approved for the final reviewed delta. No new finding or blocker.** This addendum supersedes the earlier review of the first normalization attempt.

Reviewed immutable `work/m1d-review-python310-final` against `work/m1d-review-python310` and previously approved `work/m1d-review-final-policy`. The final manifest matches every listed file. Only `sidecar/icarus_memory/source_snapshot.py` changes from the first compatibility attempt; the ten regression cases remain identical. Relative to the approved M1d production snapshot, the changed files are the source helper and its tests.

`canonical_instant` now handles terminal uppercase `Z` with explicit guards: it rejects another `Z` anywhere before that suffix and requires a preceding digit before translating the suffix to `+00:00`. This closes the coordinator-reported Python 3.10 case where naive suffix replacement turned `...ZZ` into a form its permissive parser accepted. Empty/standalone suffixes are also rejected safely. Existing parsing and timezone-awareness validation remain after normalization; valid UTC and offset inputs retain their instant, while naive inputs do not acquire a timezone.

The ten parameterized cases cover equivalent `Z`, explicit UTC and nonzero offsets, `None`, naive datetime/date-only input, empty/invalid input, doubled/interior `Z`, and an existing offset followed by `Z`.

Independent verification of the **final snapshot on Python 3.12.13**: the entire `test_episode_support.py` suite passed — **61 passed**, 2 existing Starlette/httpx deprecation warnings, 1.92 seconds. This includes the unchanged malformed/naive regression contracts and all M1d episode-support controls. No snapshot or production file was modified.

I did not independently execute Python 3.10 or GitHub CI in this review seat. The coordinator reports the final guarded code passed **93 focused tests on actual Python 3.10.21** (4.44 seconds), including double-Z rejection; that is backend-supplied evidence, not an independent run by this seat. Final whole-suite/CI gates remain coordinator-owned. The first attempt's 3.12 success is not presented as proof of its 3.10 correctness. Previously approved M1d findings remain closed, and deferred backup, M2c, and model-qualification boundaries remain unchanged.
