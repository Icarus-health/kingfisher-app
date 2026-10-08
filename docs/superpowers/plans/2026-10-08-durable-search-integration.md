# Dauerhafte Bedeutungssuche im Produkt: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline, TDD and one independent final review. User authorized autonomous implementation and routine review decisions. No new cloud costs or private uploads.

**Goal:** Replace product query-time source embedding with durable background indexing, a single local question vector and visible honest progress, then deliver data-preserving Mac update.

**Architecture:** App-scoped semantic service owns `DurableSemanticIndex` and a local embedding adapter configured from role `einbettung`. Existing scheduler performs one small batch, including during upload-triggered work; existing energy, pause, priority, model identity and restore gates apply. Queries read existing source vectors only. Direct legacy diagnostic adapters may remain explicit; product must not silently fall back to query-time indexing.

**Tech Stack:** Python, FastAPI, SQLite/sqlite-vec0.1.9, existing local Ollama adapter, React/TypeScript.

**Spec:** docs/superpowers/specs/2026-10-08-durable-memory-search.md. Storage implementation and evidence: docs/runs/2026-10-08-vector-store-fitness. Base storage branch: feat/durable-memory-search-20261008; storage is not activated yet.

## Constraints

Preserve originals, account/calendar/provider/model configuration, saved answers and existing warning contract. No new thread or unbounded source embedding. No cloud embedding or source disclosure. Status GET must never start a model. Do not claim complete corpus from cache counts if source classification is unfinished. No default model download, new cloud spend, CI rerun or public stable release without completed gates. Mac native check remains pending locked-screen access, not passed.

## Task 1: service and bounded worker

Files: new `sidecar/icarus_memory/working_memory_semantic_service.py`, tests; existing `local_embeddings.py` only if lifecycle transport abstraction requires it.

- [x] Read current `hintergrund.ModellAmpel`, `als_hintergrund`, `LocalEmbedder` and scheduler permission/restore boundaries before coding.
- [x] Tests RED: question sends only its own one-item input; no source embedding on query or saved reopening; restart consumes persisted vectors; one background batch processes <=8 refs and bounded total UTF-8 input; no network/model call while source/conversation locks held; malformed batch or transport failure preserves older vectors and exposes incomplete status.
- [x] Service is app/store-scoped, not endpoint-global. It validates exact local model name/digest, gates model loading and embedding through AMPEL, and rechecks permission/role before and after model calls. Intentional BackgroundInterrupted must not become failure cooldown. Model change invalidates handles and pending work; expose sanitized unavailable/partial status, no provider/source text in errors.
- [x] Tests RED/GREEN for local-only enforcement, changed model, pause/energy interruption, role replacement, retry cooldown and stale factory. Keep bounded stale-failure cleanup from storage review in this task's prune handling.

## Task 2: real product retrieval and scheduler wiring

Files: `server.py` `_build_agent`, `_wire_scheduler`, `_close_persistent_state`, `_reopen_persistent_state`; `agent.py` working-memory callsites; `working_memory_answers.py`; `working_memory_semantic.py` compatibility boundary; relevant scheduler/server tests.

- [x] RED HTTP/agent tests proving the configured `einbettung` role is used independently of answer/background provider; indexing requires existing schedule/with_model/local permission and active generation; prompt/source_ids work cannot starve the older global index batch.
- [x] App-scoped service closed before originals at restore/shutdown; recreate against new EpisodeStore only after restore boundary permits. No connection to replaced original inode; no stale cache revival after restore with reused IDs.
- [x] Replace the product's `for_provider(answer_provider)` lookup with explicit bound service injection. Both normal and meaning-scoped answers plus server routing use the same service. Keep a clear compatibility default for standalone existing tests/diagnostics; disabled product does not construct legacy query-time source index.
- [x] Avoid duplicate question embedding across router and final preparation with request-local evidence bound to exact query, model and current source signature. A changed lookup gets its own vector; no global query cache with stale cross-request evidence.
- [x] Replace capped `_semantic_inventory()` with a full eligible-key/source-version signature, streamed/bounded in memory. Include every eligible item, not only2048 or a collision-prone count/sum. Resolve remains final source-validity gate. Saved reopening checks signature without embeddings; changed old source or new old-ranked relevant item invalidates saved selection.
- [x] Tests cover >2048 relevant source through real question/selection path, partially indexed hit and empty result warnings, provider failure, ambiguous person/time/conflict, new/unclassified sources, offline reopening and withdrawal across history projections. Exact top-k limit may be partial even when structural indexing is complete.

## Task 3: understandable progress in the existing memory page

Files: `memory_routes.py` `/api/v1/memory/coverage`; `app/kingfisher/src/api.ts`; `MemoryStatus.tsx` and focused tests/styles only as necessary. Use frontend testing skill before rendered flow changes.

- [x] Backend tests first: `semantic_index` reports disabled/unavailable/partial/indexed with configured model, eligible sections, indexed/pending/failed, last progress and current pause reason. Distinguish this from `working_memory_progress` source classification. GET performs no tags/model call or embedding and does not certify stale model identity as freshly checked.
- [x] Add a compact automatically refreshed progress block using existing15-second coverage refresh. Explain “Für Bedeutungssuche vorbereitet” separately from “Quellen sortiert”; show paused/failed state and retry without extra required clicks. No fake ETA and no blanket perfect-memory promise.
- [x] Verify rendered states on isolated synthetic test app, empty/partial/full/failed/paused and refresh. Review usability in context, not only source-text assertions.

## Task 4: end-to-end review, GitHub and Mac

- [x] Run meaningful affected backend, saved-answer, restore, scheduler, API, UI build and actual synthetic query flows; record command/result and remaining real-model quality limitations. Frozen original and independent catalogs remain unchanged. A failed model runtime is a failed attempt, not an accuracy score.
- [x] One independent whole-feature review; important findings RED/GREEN; inspect final diff and clean committed tree. Complete draft feature PR, merge with skip ci after gates; no paid CI retry.
- [x] Build offline derivative from installed image using pinned local sqlite-vec Linux wheel and clean archive; rebuild changed UI from existing locked dependencies. Check package/module/license/UI hashes in finished image and exact database/query path netlessly.
- [x] Cold backup app/private env/data, verify original IDs/digests and SQLite integrity before/after, preserve integrations/roles/volume/port. Update local Mac build only after feature path works. Existing preview installer needs dependency/UI update rather than old code-only replacement.
- [ ] Native user flow when access available; report any unverified gate plainly. Public updater remains separate until release packaging/signing/publishing is actually completed.

## Review Focus

A raw LocalEmbedder bypasses AMPEL; same endpoint does not imply same model role; model tags may change externally; caches must be per store and close at restore. Source classification and semantic indexing have separate incompleteness. Full inventory hashing must notice old sources without reading/copying all plaintext on each query. One question must not trigger hidden source work or duplicate router embeddings. Background priority cannot starve index backfill. Cache failures never erase originals or allow saved withdrawn quotes. Mac delivery must include native wheel and changed UI, not just Python source.

## Ausführungsentscheidung

Die bestehende Vordergrund-Gesprächsserialisierung bleibt erhalten. Der neue Dienst erwirbt diesen nicht wiedereintrittsfähigen Lock bei Fragen nicht erneut; der Hintergrund gibt den Modellplatz vor dem Commit-Lock frei. Quellensperren und eigene Dienstsperren werden bei Transport nicht gehalten. Status-Polling ist modellfrei; noch nicht geprüfte Hintergrundbereitschaft bekommt einen eigenen ehrlichen Zustand. Nachweise: docs/runs/2026-10-08-durable-search-product/README.md.
