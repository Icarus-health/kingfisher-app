# Memory evidence validity repair implementation plan

> For agentic workers: use superpowers:subagent-driven-development, test concrete regressions first.

**Goal:** Correct four reproduced evidence/history defects without changing model authority.
**Architecture:** Shared bounded evidence validation plus versioned claim-input lineage for model history.
**Tech Stack:** Existing Python/SQLite/Agent APIs, no dependency or migration required.
**Spec:** [Memory Core contract](../../architecture/kingfisher-memory-sicherheitsvertrag-v0.1.md), M1 of [Memory-first roadmap](../../release/MEMORY-FIRST-ROADMAP.md).

## Steps

- [ ] Reproduce archive loss, invalid quote acceptance and deep traversal in digest API.
- [ ] Share bounded iterative evidence checks with explicit historical/current modes; preserve original archive and status labels.
- [ ] Reproduce time-only expiry through both ongoing and loaded conversations.
- [ ] Check accumulated claim lineage before/after model calls and before tool execution; preserve display and reset metadata.
- [ ] Test actual Agent payload, digest cache/API and persisted conversation paths, including unaffected valid history.
- [ ] Review, focused/full suites, isolated runtime test and authorized integration.

# M1 implementation decision: evidence and time boundaries

User authorized autonomous completion of memory functionality under existing contract.
Scope: reproduced archive/quote/recursion and time-expiry history defects. No new rights,
private-data imports, migrations or model qualification. Baseline M0 remains separate.

Evidence traversal: shared iterative check with current mode requiring every claim
usable at an explicit instant, historical mode permitting non-redacted historical
statuses but still requiring original evidence for all ancestors. Archive is retained
original, not exclusion. Budget 128 distinct claims, cycle/missing/badquote fail closed.
Preserve statuses in digest output. ClaimStore.is_usable uses iterative status-only
traversal so graph projection cannot crash before evidence validation. This does not
make graph source filtering equivalent to chat authorization.

History: store precise claim IDs of ALL prior context inputs, not only cited output.
At start of each Agent round check old context claims against current evidence/time.
If a previously supplied claim is no longer usable, clear model history and recorded
history dependencies, retaining displayed conversation. Preserve valid stable history.
On load_history rebuild dependencies from persisted assistant context.items and apply
same checks; revision filtering in server remains in place. Legacy metadata without
complete lineage cannot be certified; use existing revision/egress boundaries and
explicitly document remaining unknown history coverage. On invalidation persist a
context reset marker so later reload does not repeatedly erase new valid history.
Revalidate current input claims after provider returns (time-only expiration does not
change revision). Do not present expired factual answer; return brief retry notice.
Test parent expiry even when child has no end time, source mutations, same instance,
new Agent with stored metadata, API persistence and original UI message preservation.

Tradeoff: conservative invalidation drops conversational model context after evidence
changes; explicit metadata/reset makes this explainable. No claim of full arbitrary
source/old-backup deletion safety. The full M1 restore contract remains separately open.

Review refinements (apply, no open design questions):
- Check full accumulated input lineage after provider returns, before any returned tool executes; not only freshly selected claims.
- Versioned completeness marker for context lineage. Unknown/malformed legacy history is not verified-empty: conservatively omit from model context, explain/display preserved messages. No unsafe legacy exception merely for convenience.
- Apply most recent calendar or knowledge reset before rebuilding dependencies; retain triggering user question and later valid answer. Invalidated retry has empty lineage and reset marker.
- Propagate context+notices through Agent.approve follow-up, direct calendar answers and error returns.
- Every history clear also clears accumulated IDs (revision/cloud/calendar/reset). load_history rebuilds instead of unioning across conversations.
- Historical mode ignores status usability along all ancestors except redaction, but validates original evidence. Current mode uses one instant for every ancestor.

Marker scope must be named explicitly, e.g. knowledge_claim_lineage_version=1,
NOT 'all provenance complete': this first repair covers ClaimStore evidence and
its transitive dependencies, not arbitrary tools/self-model/mail text. Missing
knowledge lineage in old assistant metadata is conservatively omitted. Document
remaining source categories so no completeness claim hides them. Preserve fresh
current user input and displayed messages. Profile/self-model lineage is M4 follow-up.

## Implementation brief

# M1 bounded shared evidence fix (after baseline)
Read evidence-audit.md for reproducible findings.
Preserve retained ARCHIVED originals in person digests. Exclusion is IGNORED or source missing/invalid/generated SUMMARY, not ordinary archiving. Share bounded iterative evidence traversal between chat and digest, with explicit distinction current versus historical claims. Historical nonredacted claims can remain labeled historical; their current usability must not be implied. Check normalized nonempty quote, original digest match, source kind/state, every transitive dependency; distinct-node and cycle budgets. ClaimStore.is_usable must not recurse unboundedly before digest graph building. No migration or reclassification of existing claims. Tests need valid chain, deep chain, shared ancestors, cycle, archive positive control, excluded/invalid/missing/summary source, empty/fake quote, transitive exclusions and cache stale after source changes. Real Agent and digest API paths with synthetic data, no actual model. Document limited scope, not full memory qualification.

Additional confirmed priority finding: expired claim absent from new context yet previous assistant answer remains in provider history, because time change does not update ClaimStore.revision. Read /tmp/kingfisher-memory-work/repro-expiry.py and evidence-audit.md. Need actual input provenance/time validity check for same Agent and loaded histories, not only selected current claims. Preserve displayed conversation, discard model-history suffix/prefix conservatively when prior context validity cannot be established, don't grant permission from model text. Must record enough context metadata to verify claims' evidence chains and temporal bounds; full modelinput dependencies, not just quoted output, matter. Test dependency expiry, source revocation/digest change, same-agent, persistence/reload, unaffected stable history retained, cloud boundary, change DURING provider call. Keep changes isolated if large; do not claim all source types covered.
