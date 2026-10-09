# Independent review: Today actionable questions

Reviewed branch `fix/today-actionable-questions-20261009` against `ec64e00`, limited to the requested MemoryQuestions, dashboard proposal count, and related tests. Review was read-only; no UI, Docker, network, model, or private-data access.

## Findings

No actionable defect found in the reviewed changes.

`MemoryQuestions` filters only the exact `(art="waise", unterart="ruhend")` pair before sorting and the five-row Today limit. Because `filter` returns a fresh array, its subsequent sort does not mutate API data. Both initial load and focus refresh use the same helper; retry routes through `laden`, so it shares that filter. The decision/status callbacks and source fields are preserved: the test checks `stand` and source episode ID on the visible row and confirms the status action receives the original ID, action, and stand. The full Review path remains on its existing unfiltered `api.lintBefunde()` list.

The dashboard now obtains the exact pending-state count from `ProposalStore.counts()` while retaining the bounded 20-item preview. The new backend test creates 23 distinct pending proposals, confirms `pending == 23` and 20 preview rows, and confirms the store counts were not mutated. The count uses the same pending state represented by `pending()`.

## Validation

- Node focused test: 3 passed (`memory-questions-today.test.mjs`).
- Python focused tests: 2 passed (existing dashboard count test and new bounded-preview/exact-count test); one Starlette/httpx deprecation warning.
- `git diff --check ec64e00`: passed.
- No live application or repository-wide suite was run.

## Reviewed file SHA-256

- `app/kingfisher/src/MemoryQuestions.tsx`: `bcbd3bc0680c48b634523b3d12113260d861c2bdb52c7fa08265466b7338ab9b`
- `sidecar/icarus_memory/server.py`: `8b99a31c9ec2f647a16175ae6568283c08a2d43a42a51f6ed33559e7b326e5a4`
- `sidecar/tests/test_verdichtung.py`: `1233fc9048e917fe9b7ccb939f223eae4bf45c2083c926e1bc86ec3b01697c06`
- `app/kingfisher/tests/memory-questions-today.test.mjs`: `7d63fbdbe5a66ad56a161af028ff0e79bc4862530b692bd8e74aea333bbd5f48`
