# M3: evidence-bounded answer contract

**Decision: candidate rejected; original production prompt restored. No model or product qualification.**
User authorized continuing memory work.
Private application and model settings remain unchanged during diagnosis.

## Frozen experiment before inference

- Same installed `qwen2.5:14b`, production OpenAI-compatible adapter, loopback Ollama.
- Ten existing `countercases-v1` cases and the `-01` case of each of six original
  `development-v1` scenario families. These are development cases, not held-out data.
- Each in Agent and `reference_identity_context` mode, baseline and candidate:
  16 x 2 x 2 = **64 maximum attempts**, one repeat. The other 48 cells of the
  proposed 112-cell matrix are unrun, not selectively excluded after results.
- Exact case/hash/commit manifest persisted before first metadata/model request.
  First pair is the counted smoke; no additional uncounted smoke attempts.
- Alternate baseline/candidate and candidate/baseline by pair. Serial execution.
- 1,800-second launch budget, 60-second read timeout, no content retry; stop on
  input mismatch, metadata drift, unsafe request or two consecutive provider errors.
- Reserve each cell before inference. Exclusive output; interruptions remain
  incomplete and may not silently rerun the same cell.
- One closed synthetic SQLite fixture copied to distinct arm directories preserves
  physical IDs and ordering. Never use private app stores or shared histories.
- Capture exact production-adapter JSON. Only replace the complete first system
  prefix, retaining clock suffix, source content, all other messages and options.
- Zero-provider calendar controls compare the unchanged deterministic result;
  they do not count as prompt-effect evidence.

The prep commit keeps the old prompt. Its immediate child changes only the literal
`SYSTEM_PROMPT`. The runner checks both Git trees and requires a clean tracked tree.
No arbitrary prompt/file/ref CLI is exposed. Run at that candidate commit:

```sh
PYTHONPATH=sidecar:scripts .venv/bin/python scripts/probe_memory_answer_contract.py \
  --model qwen2.5:14b --output /tmp/new-exclusive-m3-comparison.json
```

## Verification and review

Baseline: 168 existing diagnostic tests passed. Catalog and comparison regressions
exercise real Agent/SQLite/adapter with only HTTP replaced by MockTransport.
Independent preflight review found two stop-rule gaps; three regression tests
reproduced them, fixes passed all 25 comparison tests. Scoped re-review found no
remaining Critical/Important issues. First four tool/approval clauses and context
separation sentence were mechanically checked unchanged. The four opening controls
are [reviewed separately](prompt-boundary-review.md); this is static semantic review,
not observed model compliance.

The initial bare pytest run had four calendar subtest failures because the worktree's
native test binary had not been built (all 1,839 other tests passed). After invoking
existing `scripts/build_calendar_reader.sh`, focused preparation verification passed
161 tests plus all four calendar subtests. No calendar permission/read was requested.
The candidate full suite had 1,842 passing tests and four passing calendar subtests,
plus one failing legacy wording check (`test_systemanweisung_verbietet_behaupten_von_altem`).
That test was not weakened. The original prompt was restored following the semantic
rejection; final delivery verification is recorded below.

Raw results retain `semantic_verdict=review_required`. Source-based Codex review must
be attributed and must distinguish missing/forbidden context, unsupported claims,
action state, user attribution, identity, time, provenance, clarification/refusal and
technical failure. No model confidence, keyword matching or source recall can grant
semantic qualification. Unseeded generation prevents a single paired observation
from proving causality. Human acceptance, held-out quality, extraction, robustness
and latency remain open.

## Completed paired run and decision

- Baseline preparation: `074211cbc00ec0f72248262225a8ecaa03d72e8e`.
- Prompt-only candidate: `adac787a111b0994dfdc5780e24372895d8728a7`.
- Revert: `29e2b09`; production answer behavior remains the baseline.
- 64/64 attempts completed, 32/32 pairs: 31 exact prompt-only model-input pairs
  (62 generations) and one unchanged deterministic calendar pair. No confounded
  pair, retry, missing cell or technical failure; installed weight/configuration
  and Ollama version stayed stable. No new downloads or cloud model calls.
- No forbidden source observed. The adversarial source S2 did **not** reach the
  Agent in either arm of `injected-source-01`; those two answers are not evidence
  of resisting a delivered injection. Reference mode supplied it in both arms.
- Wall-clock run: 2026-09-19 19:34:41–19:40:48 UTC. Concurrent offline tests mean
  these timings cannot qualify idle or loaded latency; no P95 claim.

All attempts and exact request payloads are preserved in [comparison.json](comparison.json).
Original raw semantic flags remain `review_required`. Separate manual, source-based
Codex judgments are in [semantic-review.json](semantic-review.json); these are not
human acceptance. Forty countercase answers were reviewed independently with variant
identities hidden; 24 original-case answers were reviewed by the root with identities
visible. Counts from these distinct reviewer procedures are kept separate:

| Group | Original: factually supported | Candidate: factually supported | Original: full answer contract | Candidate: full answer contract |
|---|---:|---:|---:|---:|
| Ten countercases, two model modes | 18/20 | 19/20 | 0/20 | 1/20 |
| Six original cases, model paths only | 7/11 | 8/11 | 0/11 | 0/11 |
| Deterministic calendar control | 1/1 | 1/1 | 1/1 | 1/1 |

These small unseeded development observations do not establish causal improvement,
general failure rates or adequate model quality. A factually correct answer can fail
the contract by omitting an identifiable source, necessary qualification or a useful
clarifying question. No automated keyword judge was used.

Specific blockers:

1. Reference answers for two unmerged Robin contact records still assign the records
   to one person with different roles or preferred addresses. The candidate does not
   establish reliable identity reasoning.
2. For the corrected Aurora date, the original Agent answer includes 22 September,
   14:00 and Europe/Berlin; the candidate says only 22 September. The same loss of
   required detail occurs in reference mode.
3. The candidate interprets Einkauf as a shopping occasion in an Alex contact answer
   and changes an unexpressed opinion into a not-yet-defined opinion in another case.
4. Most otherwise correct answers still omit an identifiable supplied source reference.

Positive controls remain useful: confirmed sent, explicitly not sent and unknown sent
status were correctly distinguished in both arms of these prepared countercases;
explicit goal versus exploratory thought was also distinguished. This does not prove
extraction from arbitrary messages or multiday retention.

**Release decision:** keep the tested diagnostic improvements; do not ship this
prompt candidate or switch the user's model. The next memory task needs a reviewed
answer format that preserves cited record identity, evidence and required fields,
plus separate evaluation of model interpretation. A longer general prompt alone
is not an accepted fix. Restore rollback protection remains a separate open task.

To reproduce this exact experiment, use the recorded candidate commit in a separate
checkout and a new exclusive output. The current branch intentionally restores the
original prompt, so its HEAD is not accepted by the prompt-only runner. The 48 omitted
proposed matrix cells and every broader holdout/human/robustness gate remain unrun.

## Final delivery checks

`ICARUS_DATA_DIR=<new temporary directory> PYTHONPATH=sidecar:scripts .venv/bin/python -m pytest -q`:
**1,843 passed, four calendar subtests passed**, two existing dependency deprecation
warnings, 122.75 seconds. The legacy prompt check passes unchanged after rejection.
`git diff --check` passed. No production module differs from the integrated baseline.
The two preexisting untracked M3 design/review drafts remain untouched.
