# Synthetic joined core flow — 28 September 2026

`sidecar/tests/test_pilot_core_flow.py` joins one isolated mail source to an
explicitly prepared task candidate, a project, the selected calendar and its
read-only preparation, a local calendar question, a visible action approval,
and a fresh-app restart. It verifies mail cursor/deduplication, a single task
after repeated candidate acceptance, exact confirmation, one action-sink
execution, and persisted task/source/conversation/approval state.

Run it with:

```sh
PYTHONPATH=sidecar:sidecar/tests:scripts /Users/example/Documents/Codex/2026-09-07/teilgespr-ch-f-higkeiten-erkl-ren-2/work/Kingfisher-memory-core/.venv/bin/python -m pytest -q sidecar/tests/test_pilot_core_flow.py
```

All data is synthetic (`example.invalid`) in pytest's temporary directory.
The mailbox, calendar, calendar-only provider, manually supplied task-analysis
candidate and outward action sink are test doubles. The test exercises the real
stores, HTTP routes, literal source-answer renderer, calendar answer renderer,
candidate acceptance, approval policy and restart loading. It does not exercise
IMAP, EventKit, model extraction, SMTP, an actual
external action, backups/restores, or multi-day personal use. The action
exactly-once claim is limited to a completed local approval and duplicate HTTP
retry; this does not establish exactly-once delivery across a crash at an
external service boundary.
