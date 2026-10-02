# Independent M1d final production review

**Verdict: approved from this independent code-review seat; no unresolved code blocker found in the final reviewed snapshot.** Integration remains subject to the coordinator's final whole-suite gate. This is not a deployment, raw-backup-safety, or model-qualification approval.

Final reviewed artifact: `work/m1d-review-final-policy`, against earlier immutable snapshots `work/m1d-review-snapshot` and `work/m1d-review-final`. Base reported by coordinator: `732ae59`. Verified the final SHA manifest: no mismatch. Its only differences from the immediately prior final snapshot are `policy.py`, `tools.py`, `test_episode_support.py`, and the tracked diff. All review and test execution was read-only on the snapshots and live repository.

## Finding dispositions

| Finding | Final disposition | Evidence |
| --- | --- | --- |
| P1: `gedaechtnis_suchen` reintroduced withdrawn episode-backed inferences and exposed local-only inferences to external providers | **Closed** | Agent now renders the marked tool through the shared frozen context assessment with actual provider scope, stores the exact returned lineage, and preserves historical qualifiers. The original real-Agent recording-provider reproduction no longer sends the statement in either withdrawn-local or valid-external mode, including follow-up history. New tests cover tool-only roots, reload, withdrawal during completion, and qualified historical decisions. |
| P1: policy denial quoted an unavailable episode-backed constraint into provider/tool output and notices | **Closed** | `policy.py:179` now emits a generic denial without the constraint quotation. Independent reproduction passes for withdrawn-local, valid-external, and direct-invoke output/notices. The restrictive decision still denies execution. Three new production-path regressions pass. |
| P2: ambiguous legacy source-head mappings were treated as ordinary untracked valid originals | **Closed** | `source_snapshot.py:39` captures reverse count/key in the same SQL read and rejects conflicting or legacy-linked empty-key mappings. A dedicated reverse index bounds that lookup. Acceptance/reassessment, existing-assertion invalidation, and legacy-upgrade tests pass. Genuine untracked originals remain supported. |
| P2: incomplete required-control evidence in initial snapshot | **Closed for the reviewed M1d paths** | Final tests add forged import/overwrite isolation, 5,001 unrelated proposals and duplicate producers, tracked metadata/head replacement and archive, three real second-connection CAS races, token bounds/expiry/pagination, stale root/producer/ancestor/scope bindings, outdated-root preservation, portable support/migration isolation, interrupted reassessment publication, actual provider/reload/scope changes, current-card invalidation, and the tool/denial regressions above. Final whole-suite verification belongs to the coordinator and was still running at this review's completion. |

No critical, important, or minor issue remains that I recommend changing before integration. I did not convert ordinary style preferences into findings.

## Strengths retained after fixes

- Local authorization remains a dedicated producer commitment, separate from portable JSON. Generic imports cannot create or replace it. Exact assertion identity, canonical producer correspondence, complete support, and current original-source state are checked together.
- Producer reservation precedes assertion/supersession side effects. Producer-first publication and the assertion transaction preserve existing reciprocal supersession on failure; tests cover both commit boundaries and competing real connections.
- Withdrawal generations are monotonic across reopening, and stale consolidation cannot reopen ignored sources. Every evidence quote is checked; ambiguous identity, missing or malformed proof, and oversized support fail closed.
- Every SelfModel ancestor participates in the frozen assessment. Actual-provider localness and privacy, scoped Agents, persisted history, current cards, and restore service/resolver rebind use the shared logic.
- Reassessment binds the exact root, producer, commitment, originals, generations, ancestry, and scope. It is single-use and bounded, preserves factual timestamps/domain content, and distinguishes durable authorization from a secondary audit warning.
- Tool results now participate in history revalidation instead of being an untracked side channel. Direct `Agent.invoke` uses conservative external recall scope rather than inheriting a local provider's permission.
- The Kingfisher review UI still exposes explicit factual dates and all bounded original quotations, discards stale tokens, and prevents ignore/reopen actions from the evidence viewer.

## Existing fixture changes reviewed

I inspected every existing-test diff, not just the new M1d suite. They reflect the tightened contract rather than hiding a regression:

- Parent-only inference fixtures now supply real empty proposal/episode stores through the resolver, proving absence of episode linkage. The old absence of a resolver could not prove that fact.
- Positive known-history fixtures move from SelfModel lineage version 2 to 3 so tests continue checking the intended valid-history path. Malformed knowledge-lineage cases still exercise missing/incomplete knowledge rather than accidentally passing solely because the SelfModel version was obsolete.
- Goal lifecycle fixtures use direct user provenance for roots intentionally stripped of all inference parents. They continue exercising lifecycle and near-match semantics, without manufacturing an unsupported inference as the positive baseline.
- Synthetic legacy-database fixtures remove new M1d triggers, projections, indexes, and columns before assigning an older schema version. Original row equality and proposal/source preservation assertions remain. Expected schema versions and appended-column comparisons were updated consistently.
- The supplied real `Agent` path still enforces coherent store identities. The server's compatibility branch for lightweight non-Agent test adapters does not weaken those checks on production Agent instances.
- The task-candidate producer insert change skips an already-existing deterministic proposal ID under its transaction before the new no-replace trigger fires; it preserves the existing proposal instead of overwriting its state.

The final schema reformat is semantically identical to the previously reviewed schema; I compared parsed JSON values.

## Independent verification

On `m1d-review-final`:

- **291 passed** across episode support, Agent, context, SelfModel basis, migrations, evidence validity, mail ingestion, source versions, and task detection (16.89 seconds).
- Original search-tool exploit reproduction now passes: no withdrawn or external-forbidden inference reaches the second provider invocation or follow-up history.
- Extra preview probes for expired, future, disputed, superseded, retracted and redacted roots all refuse a token without creating authorization.
- Extra ambiguous-existing-source probe invalidates the accepted assertion and rejects the inconsistent source snapshot.

On `m1d-review-final-policy`:

- **114 passed** across episode support, Agent, memory-agent boundary, and egress tests (2.32 seconds).
- Original policy-denial reproduction now returns a generic denial in provider payloads and direct invocation, including notices, while preserving the denial.
- Final SHA manifest matches every listed file. Exact narrow delta confirmed.

These test counts overlap; they are not a count of unique tests. Runs used the existing live-repository Python runtime, snapshot-only `PYTHONPATH`, `PYTHONDONTWRITEBYTECODE=1`, disabled pytest caching, and isolated test data. Only deprecation warnings from the existing Starlette/httpx test stack occurred.

## Declined to judge

- Raw old-backup withdrawal preservation, restore quarantine, cross-backup journals, and physical erasure: explicitly outside M1d. Reviewed store/resolver/service rebind does not solve those release gates.
- M2c time-bearing ClaimStore knowledge rendering/history and model-answer experiments: explicitly separate workstreams.
- Real-model truthfulness, instruction resistance, or model qualification: deterministic recording-provider tests do not establish these properties.
- Coordinator-reported native-browser 13-check acceptance, frontend build/assets, Docker rebuild, and final whole-suite results: not independently rerun by this review seat; the coordinator must retain their actual evidence.
- Broad redesign of constraint policy or permission decisions: the scoped fix deliberately preserves restrictive enforcement while preventing source quotations from escaping. This review does not authorize weakening safety constraints.
- Arbitrary trusted Python invoking private authority methods or arbitrary raw-database forgery: outside the ordinary JSON import/API authority boundary.
- Deferred M2c/M3 documents present in the copied working material: not evidence of implemented capability and not approved for integration by this report.

## Assessment

The reproduced evidence/privacy failures are fixed and have executable regressions. The final code is coherent with the binding M1d design and its three corrections. Proceed with integration once the final whole backend suite and coordinator-owned runtime/build gates pass on the exact reviewed production content; do not infer closure of the explicitly deferred release boundaries.
