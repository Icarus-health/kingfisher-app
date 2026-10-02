# Explicit evidence-bound memory answers

Implementation: `250fc8c` (based on PR #51, `c455140`). This adds an experimental Python entry point, `Agent.answer_memory(question)`. No HTTP/UI route, regular chat prompt, local model default, calendar behavior or private installation changed.

## Contract

The existing canonical claim retrieval supplies at most five currently permitted projections. A local model may select existing E1–E5 aliases using exact bounded JSON. It cannot supply rendered factual prose. The renderer preserves each selected original statement **and** value, assertion/person/target/scope references, primary source identity, separate occurrence/recording times and validity. Missing occurrence time remains `null`; recording time never becomes event time.

Different subject/target/scope tuples return a deterministic clarification containing all captured contexts. This does not assert that different records represent different real people. No candidates yield a bounded unknown. Malformed JSON, invented IDs, extra fields, tool requests and provider errors yield a visibly labeled original-evidence fallback. A fallback is not a successful model selection.

Revision, exact canonical projection and all transitive source generations are checked before sending and returning. Changes or expiry suppress the reply and clear evidence, lineage, selection IDs and retrieval metadata. No tools, approvals, profile inputs or old model conversation are used or modified. Remote/missing providers do not retrieve memory or call a model.

## What this does not establish

The validator proves structure and identifier membership, **not truth or relevance**. `semantic_validation` is always false. Initial extraction errors, lexical retrieval omissions, unrelated retrieved rows and unknown relations between records remain unresolved. The fixed clarification can be unnecessary for comparison questions or one person with different scopes. Output is deliberately verbose and technical; a usable conversational presentation and explicit application integration need separate qualification.

## Independent review

A separate reviewer inspected implementation, canonical helpers, tests and the synthetic driver. Two findings were corrected before inference: invalidation now removes stale semantic-search metadata, and decoder recursion errors become invalid selections. The reviewer confirmed 50 focused tests and reported no remaining blocking findings. This is Codex development review, not human product acceptance.

## Reproduction

From a clean tracked checkout at the implementation commit, with the already installed Ollama model:

```sh
PYTHONPATH=sidecar:scripts .venv/bin/python scripts/probe_memory_evidence_answers.py \
  --model qwen3.5:4b --output /tmp/kingfisher-evidence-new-run.json
```

The output must not exist. This reserves a manifest before inference, executes the same 16 development cases once, records full synthetic provider requests/replies, rendered turns, source manifests and model metadata, and stops on two consecutive cases with transport failures or a 20-minute budget. Requests are restricted to literal loopback, without proxies, redirects, content retries or downloads. At most one model request is allowed per case; deterministic outcomes use none. Test data is created in a temporary directory, with no application configuration or private databases opened.

This is a single-arm development experiment. The earlier prompt experiment used another model/path; their outcomes are not a controlled comparison. Prepared claims do not test extraction. No holdout, latency, full calendar, human acceptance or overall assistant qualification is claimed.

## Local validation

At implementation commit `250fc8c`, the complete isolated backend/diagnostic suite passed: **1,893 tests and four calendar subtests**, with two existing dependency deprecation warnings (Python 3.12, 284.58 seconds). The focused contract/integration suite passed **50 tests**. The full run used a fresh `ICARUS_DATA_DIR`; it did not open the private app store. No frontend changed.

```sh
ICARUS_DATA_DIR=$(mktemp -d /tmp/kingfisher-structured-check.XXXXXX) \
  PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest -q sidecar/tests scripts
```

Checks include original field preservation, strict JSON/duplicate/forged-ID rejection, invalid context, decoder recursion, local-only egress, time-only expiry, source metadata changes before/during inference and on provider error, read-only history/tool boundaries, empty evidence and identity ambiguity. These tests do not certify semantic selection.

## Completed local model run

`qwen35-4b.json`: all **16 planned cases** completed once, model weights/configuration/Ollama metadata unchanged. Of **11 generation requests**, nine returned valid selections and two hit the 60-second provider timeout. Five cases used no model. Outcomes:

| Outcome | Cases | Interpretation |
|---|---:|---|
| Evidence selection | 9 | Original supporting fields rendered; not a semantic certification |
| Deterministic clarification | 4 | Separate reference contexts retained; verbose technical wording |
| Labeled fallback | 2 | Provider timeout; originals shown, no successful model selection |
| Bounded unknown | 1 | No eligible claim context; no unsupported calendar availability assertion |

The independent field audit in `field-integrity.json` matches **22 rendered evidence rows** against the prepared canonical manifests, with zero changed/missing checked original fields. No forbidden source appears in the returned claim context. No action, approval or memory proposal was emitted. This does not test whether every originally stored claim is true.

The corrected Aurora example preserves `22.09.2026`, `14:00`, `Europe/Berlin` and S2. Two same-name examples retain separate records and sources. Confirmed delivery, explicit non-delivery and unknown delivery status retain their distinct original evidence. The injection example only renders the permitted preparation claim; the injected source is not eligible claim context, so this is not a broad adversarial prompt-injection qualification.

Practical limits remain visible. The Sam and Nordlicht timeouts return all original rows rather than a narrowed answer or recommendation. The calendar question yields bounded uncertainty but omits the stale coverage explanation because this explicit path does not invoke the existing calendar callback. Clarifications are much longer and more technical than the rubric requests. No conversational or production acceptance is claimed, and the installed app remains unchanged.
