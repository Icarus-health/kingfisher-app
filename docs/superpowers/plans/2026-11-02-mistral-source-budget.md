# Explicit Mistral EU source packages with a persistent cost ceiling — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a connected Mistral source-package option for difficult intake, preserving local defaults, source evidence and an initially zero dollar allowance.

**Architecture:** Extend only existing explicit CloudMemoryJobs preview/start processing. Add a Small4-only EU adapter and an independent cumulative reservation ledger. Do not touch ordinary regional chat, scheduled background provider selection, local roles or import pause. Personal activation and the separate artificial seven-mail evaluation require their own actual approvals.

**Tech Stack:** Existing Python/FastAPI/SQLite/httpx/source-policy validators and React settings/package view.

**Spec:** docs/superpowers/specs/2026-11-02-modular-chief-of-staff-design.md, D/E. Public-only concrete design: `/private/tmp/kf-mistral-source-integration-design-20261102.md`; provider research `/private/tmp/kf-mistral-scoped-provider-research-20261102.md`.

## Fixed decisions

- Source model `mistral-small-2603`, endpoint `https://api.eu.mistral.ai/v1`; no other model/global endpoint/fallback. Source model is independent of saved ordinary-chat models. Reuse encrypted `MISTRAL_API_KEY` slot and active key, separate source revision salt; model-only chat edits do not rotate that salt.
- Exact caller schema and output cap64–1200, JSON Schema nesting, reasoning_effort=none, service_tier=standard_only, temperature0, n1, nonstreaming. No tools, SDK retries, proxy environment, redirects or schema weakening.
- No API call on key save, provider construction, status or preview. A Mistral source start requires explicit source consent and a nonzero durable allowance. Before its first inference POST, the adapter may perform an unbilled metadata GET `/models` on that same EU endpoint, with source/key permission checks; no source text is sent in it. Select the exact model once, verify numeric max_context_length and chat capability. Cache only within the job adapter; missing/ambiguous metadata blocks inference.
- Bundled immutable price manifest verified2026-11-02, expires2026-12-02: EU165000/660000 micro-USD per million input/output tokens. Metadata cannot extend pricing validity or change rates. Refreshing expired rates requires a new verified manifest. No invoice/tax/exchange guarantee; usage is valued at the pinned rates.
- Reserve the whole verified numeric input context ceiling plus full requested output, conservatively, before every POST. Do not invent a byte-to-token hard ceiling. Unknown model/usage, an explicitly nonstandard response tier, timeout or ambiguous dispatch remains fully reserved and blocks further Mistral traffic; increasing the cap/key changes/restart do not release it. The request always pins `service_tier=standard_only`; the documented response schema has no tier field, so its absence is expected rather than an unknown price. Primary sources: [Chat API](https://docs.mistral.ai/api/endpoint/chat), [official response model](https://raw.githubusercontent.com/mistralai/client-python/main/src/mistralai/client/models/chatcompletionresponse.py), checked2026-11-02.
- Global Mistral source ledger starts0; explicit authenticated CAS operation changes TOTAL cumulative ceiling only (0..1000USD), never resets spending. Same cap is idempotent. The pending1USD permission, if granted, applies ONLY to a separate artificial app/ledger, not personal main. No budget mutation or paid call during implementation.
- Ledger `mistral-source-budget.sqlite3` is deliberately outside BACKUP_DATA_FILES. Existing allowlisted restore preserves its current state; absent ledger means zero authority. Add a targeted restore-preservation test. No general accounting/export/reconciliation feature.
- Originals, exact quotes, source currentness, independent categories/tasks and existing confirmation rules remain authoritative. Technical completion is not quality acceptance and never resumes bulk import.

## Interfaces and ownership

New `cloud_import_budget.py` exports:

- `MistralBudgetError(ProviderError)` with closed safe `code` values.
- `MistralSourceBudget(path)` shared once per app. On reconstruction conservatively hold unfinished old reservations; never refund them automatically. Independent connections/transactions enforce admission, not only a Python lock.
- `status()` returns `{provider:'mistral',currency:'USD',budget_id,revision,price_id,price_valid_until,cap_microusd,spent_microusd,held_microusd,remaining_microusd,reconciliation_required,ready,blocked_reason}`. Normal reserved/dispatched amounts count as held; allow only one globally outstanding Mistral request in this first sequential source-package path.
- `set_total_cap(cap_microusd, expected_revision)` strict integers, no bool/float, preserves every reservation/spend; reject below settled+held. A changed cap increments revision and invalidates old package reviews.
- `matches(budget_id,revision,price_id)` checks pinned identity/rate validity, including unresolved held states; a request's own in-flight reservation must not invalidate its permission callback.
- `reserve(job_id,model,context_limit,max_tokens,*,budget_id,revision,price_id)` returns opaque reservation ID; `dispatch(id)`, `cancel_unsent(id)`, `hold(id)`, `settle(id,prompt_tokens,completion_tokens,total_tokens)` implement durable closed transitions. Cancel only known-unsent; settlement remains allowed after source/key/cap revocation because a billed response may not be usable memory. Preserve rows/history, no reset/delete/refund endpoint.

New `MistralImportProvider(model,api_key,credential_revision,current_revision,*,budget,job_id,budget_id,budget_revision,price_id)` exposes existing `available()` and `complete_json_guarded(messages,*,max_tokens,schema,before_send,still_permitted)`. `_client()` is injectable for tests only. Metadata and POST use a direct bounded client. Persist dispatch marker before POST; safe typed errors only. Settle valid observed usage even if output/schema/currentness later rejects the response; absent/invalid billing remains held. No secrets/prompts/provider bodies in ledger/status/log errors.

Cloud jobs add nullable budget_id/budget_revision/price_id to preview/job tables. Only new Mistral rows require them; legacy ChatGPT/Anthropic stay compatible. API provider factory accepts extra job/budget keyword arguments only for Mistral, preserving existing two-argument factories for Anthropic. Authenticated GET/PUT `/api/v1/memory/cloud/budget` exposes/sets Mistral-only cumulative cap with exact body `{provider:'mistral',cap_microusd:int,expected_revision:int,consent:true}`. No automatic cap creation other than0. Start/resume/per-request boundaries check the pinned budget identity and current source/credential.

## Task1 — Ledger and source transport

Own new modules plus `sidecar/tests/test_cloud_import_budget.py` and `test_mistral_import_provider.py`.

- [x] RED: cap0, CAS/same-cap, concurrency/last-cent, durable restart/unfinished holds, exact rounding, unknown usage/dispatch, terminal retry refusal, no secrets/data in ledger. Adapter exact EU/model/schema/caps, actual metadata, no hidden probes, no redirect/proxy/retry, permission/key/budget races, billed rejected output, coherent strict usage, missing/chunked/tool/truncated/duplicate output rejection, no send after stop.
- [x] Implement interfaces above and run focused tests, no real key/network.

## Task2 — Prepared credential and existing package integration

Own cloud_credentials.py, cloud_import_provider.py, cloud_access_routes.py, cloud_memory.py, cloud_memory_routes.py and related tests. Preserve existing Anthropic defaults/signatures; do not edit ordinary RegionalCloud/hintergrund/model roles/server.py.

- [x] RED: Mistral encrypted+active key/salt checks and fixed import_model independent of ordinary model; actual key save/delete/rollback; no remote call on preparation. Provider/source/budget/preview binding, zero/unavailable/held budget, resume after key/cap changes, category failure caching, no task/source write on rejected results, old job migration/readability and restore preserves ledger.
- [x] Wire the real preview/start/adapter/ledger path. GET budget/status never calls provider; PUT cap never starts processing. Route shared lazy ledger factory is single per app. Typed budget failures pause with safe reason, never automatic retry/fallback.
- [x] Run affected cloud/source/credential/restore suites; leave global import/roles unchanged.

## Task3 — Compact explicit UI and isolated evaluation preparation

Own api.ts, CloudMemory.tsx and focused UI tests; new artificial evaluation helper if necessary.

- [x] Add Mistral source choice/fixed import_model, cumulative used/reserved/remaining USD and explicit cap setter with no prefilled/submitted allowance. Parse decimal exactly to micro-USD; avoid float billing. Budget labels apply only to Mistral; job labels use stored provider. Source consent names EU/EFTA inference and separate account metadata qualification; no legal-compliance claim.
- [x] Missing key points directly to existing settings. Preserve current Anthropic/ChatGPT flow and local defaults, no model work while browsing. No automatic source selection beyond existing reviewed preview.
- [x] Prepare seven frozen artificial mails in an isolated app using exact IDs through the real preview/start path. Keep live evaluation disabled until actual key and explicit <=1USD permission exist; no personal budget/role/import activation.
- [x] Build/run relevant UI tests and source transport integration. Independent branch review, one important-fix wave, regression and precise evidence before GitHub delivery. Actual Mac/window/provider quality acceptance remains separate.
