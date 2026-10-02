# Readable evidence answers and explicit calendar coverage

Implementation commit: `5bedbbc`. Based on merged PR #51/#52 (`main` at `0657c87`). This changes the existing explicit `Agent.answer_memory` path, not normal chat routing or application defaults.

## Behavior

The short display quotes original statements, retains distinct stored values, shows source references with German labels, and separates event time from recording time. Validity end is explicitly exclusive. Canonical assertion/person/target/scope identifiers, digests and lineage remain in returned context. The diagnostic `EvidenceAnswer.render` is unchanged; the agent now uses `render_readable`. Citation numbers correspond to the order of `answer_contract.selected_assertion_ids`; `presentation_version` is 2.

Clarifications show actual original text instead of opaque entity IDs. If different reference contexts have identical visible content, the response explicitly says the visible evidence cannot distinguish them and requests more context. It never invents a job title, person relationship or registry label. Provider errors get a clear explanation and original-evidence fallback, not an invented completed answer.

Exact existing calendar overview/availability questions use the established deterministic calendar renderer. Unavailable, disabled, stale and incomplete coverage never establish free time. A second canonical snapshot read checks the semantic fingerprint before returning. Harmless clock movement is allowed; freshness expiry, event boundary changes and withdrawal invalidate the response. These calls do not consult a model or change conversation history. Other topic questions remain in claim retrieval, so an unrelated calendar title cannot suppress memory ambiguity.

The calendar callback is expected to supply the existing canonical `calendar_context.snapshot` format. Callback errors/malformed display data become an unavailable snapshot without exposing exception details. Remote/missing-model restrictions of the explicit memory path remain unchanged.

## Frozen presentation comparison

`comparison.json` contains all 16 outcomes and originals. `replay.py` reads the previous committed synthetic run from Git, preserving its input hash. Fifteen cases reuse the exact historical model selections/clarifications/fallbacks and canonical context. One case executes the new real Agent calendar path against its prepared synthetic fixture; its provider raises if called. No inference was performed, and no model was substituted or retried.

All checked original statement/value/source/time fields remain visible. Technical identity and lineage fields stay in context. For the 15 renderer cases, total reply length changes from **15,517 to 6,579 characters (57.6% reduction)**. This is a text-length measurement, not a quality score. The calendar case now states the snapshot is stale and free time cannot be confirmed.

The two historical provider-timeout cases remain fallbacks. This replay does not prove better model selection, reduced timeouts, extraction quality, general calendar understanding, a natural multi-turn conversation or production acceptance. No normal-chat activation or private Mac installation update is claimed.

Reproduce from a clean tracked checkout with a fresh output path:

```sh
PYTHONPATH=sidecar:scripts .venv/bin/python \
  docs/evaluations/memory-quality/runtime/readable-evidence-20260920/replay.py \
  /tmp/readable-evidence-new.json
```

## Review

Independent Codex review passed 86 focused tests with no blocking findings after two presentation fixes: exclusive validity wording and visibly indistinguishable contexts. Additional tests exercise harmless canonical clock drift, stale transition and event-window expiry. JSON quoting escapes embedded newlines but is not Markdown sanitization. The current React chat displays message content as plain JSX text; any future rich-text consumer requires its own safe rendering contract.

## Final local validation

- macOS Python 3.12: **1,912 tests and four calendar subtests passed**, two existing dependency warnings, 129.03 seconds.
- Linux ARM64 Python 3.10: **1,889 tests passed**, using the exact backend/diagnostic test selection from CI, two existing dependency warnings, 159.95 seconds.
- Full Docker build from a clean archive of `5bedbbc`: image `kingfisher:readable-5bedbbc` (`1d9288fc5ab5`). The installed package reproduced all 15 readable responses exactly, plus an actual Agent stale-calendar response; no inference.
- Independent code review and all 86 focused regressions passed. `git diff --check` passed.

Local checks are the owner-authorized merge gate while GitHub Actions credits are exhausted. GitHub status is not asserted green. No UI source or Rust desktop source changed; no new browser-design acceptance, AMD64 build, native release, private-data evaluation or normal-chat activation is claimed.
