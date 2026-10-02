# Everyday memory: implementation and acceptance, 20 September 2026

Code under final acceptance: `e8e3ffc448f68ef666bfac25dddf454615f041d8`.
Backend identical to independently reviewed and fully tested `4e98b41671a70350138dcc19f67e22ec5c10e508`; the last commit only reuses existing settings spacing classes. No production Rust or model prompt changes.

## Delivery and limitations

| Requested step | Implemented and observed | Remaining acceptance |
|---|---|---|
| Normal conversation | Conservative German memory-question routing and same-conversation clarification; explicit chat override and retries retained; real process restart passed | Broader natural-language coverage; legacy `/chat` retains existing behavior |
| Relevant retrieval | Local installed-model adapter; bounded live vectors; changed originals rebuilt, withdrawn rows removed, unchanged vectors reused; lexical fallback | Experimental, **off by default**. New 22-case development set: lexical 11 exact / 22; live 15 / 22, including one irrelevant negative-control hit. No relevance qualification |
| Meaning and attribution | Hypothesis/request/decision/completion/denial/unknown/quotation remain original source text; read-only answer cannot execute source requests or turn a third-party preference into a user rule | Prepared-claim probes do not evaluate extraction or broad semantic understanding; one lexical miss and one model-format fallback |
| Forgetting and restore | Historical marker before any operational bootstrap; old snapshot is inspection-only. Normal requests/workers drain before in-place replacement; scheduler/MCP stop; preflight validation preserves runtime on rejected snapshots. Old launchers/images refused | No physical erasure of retained backups. No blanket activation of an old snapshot because later revocations cannot be reconstructed |
| Working profile | Explicit closed length/address/emoji settings, global/task scope, current-turn override, conflict withholding, correction, expiry, retraction; changed profile clears model history | Scope recognizes bounded explicit task forms. Source answers preserve originals. Model obedience to styling is not guaranteed |
| Everyday acceptance | Full suites, independent review, real desktop settings, default question/clarification/restart/withdrawal/restore/restart flows | Multi-day private use, human holdout review, broader extraction and acceptable real-model latency remain open |

## Verification

- macOS Python 3.12: **1,993 tests plus four subtests passed**, two upstream deprecation warnings; `PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest -q sidecar/tests scripts`, isolated `ICARUS_DATA_DIR`.
- Docker Linux Python 3.10: **1,970 passed**, two upstream deprecation warnings; full sidecar plus CI diagnostic scripts including `test_probe_everyday_memory.py`, read-only clean clone at `4e98b41`.
- React TypeScript/Vite build, legacy JS syntax, schema/example and asset contract passed. Rust unchanged, not rerun on this Mac.
- Independent immutable review: two initial restore defects and two later P2 issues fixed; final review **no open blockers**, 135 targeted tests and independent reproductions. Full suite additionally found clock/expiry side effects in profile resolution; fixed by read-only filtering against the existing business clock.
- Real container on synthetic volume, `127.0.0.1:18998`: implicit memory routing, clarification after process restart, three persisted working rules, source withdrawal invalidation, old-backup inspection, blocked action routes and persistent inspection after another restart passed. The configured model endpoint was unreachable loopback, so no model could satisfy these source-only checks.
- Real Chromium desktop 1440×1100: settings → task-specific preference → reload → revoke → general rule visible; no page/console errors. Screenshot inspected. At 390×844 the pre-existing global `min-width:1280px` overflows: **mobile is not qualified**. Browser plugin unavailable; installed Playwright used.

## Local development model probes

Frozen new corpus/expectations were written before inference. Artifacts under `../evaluations/memory-quality/runs/2026-09-20-everyday/` retain manifest hashes, source data, outputs and failures.

- Retrieval: 22 new German questions, lexical/live-cold/live-warm (66 observations), actual Agent provider payloads, local installed `bge-m3`, no chat inference. Exact evidence sets: 11/22 lexical, 15/22 live. Live warm median about 27 ms; cold median about 246 ms on this small corpus. These runs overlapped other local validation and are not controlled latency benchmarks.
- Meaning: eight prepared-source cases, local installed `qwen3.5:4b`; six schema-valid source answers, one rejected model format with original-source fallback, one missing plural-form retrieval. All eight side-effect free. The quotation's `original_preserved=false` is a diagnostic raw-substring artifact: quotation marks are JSON-escaped in the visible original, and inspection confirms attribution and denial remain present. No generated completion assertion was published. Model calls took roughly 13–61 seconds under concurrent validation, **not an accepted everyday latency target**.
- Growth: local real embeddings with 32, 128 and 600 original claims. Cold roughly 0.66–2.44 seconds, warm 35–71 ms in this diagnostic. With 600 claims, canonical per-build validation limits the cache to 128 and reports **partial** coverage (inventory bounded to 512); this is not full-store recall. Initial harness attempts failed at catalog/claim consistency validation and remain recorded; the corrected 600-row run completed.
- Runtime semantic opt-in is `ICARUS_MEMORY_SEMANTIC=1`, local provider and already installed `bge-m3:latest` required. It does not download models. Leave unset in the private app until false positives, missing relevant evidence and coverage are independently qualified.

## Private everyday acceptance checklist

Use current documents/conversations chosen by the owner over at least three separate days; do not invent elapsed use from synthetic tests. Keep expected answers independently written before asking.

1. Record a fact, close/reopen the app and retrieve its original source on the next day.
2. Correct the fact; ask through another wording and a prior conversation. The old version must not silently win.
3. Distinguish two same-name people/projects; require the correct source context.
4. Contrast a plan, a decision and a completed action; record any unsupported inference.
5. Change a general preference, add an analysis-specific exception, ask “diesmal kurz”, then revoke the exception.
6. Withdraw a source, retry the old conversation and inspect an older synthetic backup separately. No old authority may resume.

Record usefulness, missing/irrelevant evidence, source correctness and cold/warm end-to-end latency for every case. Safety failures block release; semantic relevance and speed remain separate gates. Private data is not copied into the repository or these synthetic reports.
