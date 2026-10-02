# Final whole-branch integration review

Reviewed branch range: `ebb2e63bc61f7bfcc867ffd3e03c28b5db3614c3..f52b910aa232928f012a57dca792307af2ffbf50`.
This is the separate integration gate following the accepted task review, using `requesting-code-review/code-reviewer.md`. The complete immutable diff was already read in the task review; this pass examines named interactions at changed contracts and the preserved release evidence. No code, index, branch or HEAD changes; no subagents.

## Strengths

- The new exact knowledge contract composes with the existing provider publication loop and M1d SelfModel checks: each pre-provider, post-provider, error and tool boundary reaches fresh knowledge validation while independent egress checks remain (`sidecar/icarus_memory/agent.py:486`, `:497`, `:501`, `:508`, `:533`, `:748`, `:892`).
- Scoped agents share both the actual Policy and approval-specific knowledge bindings. History reset clears model history while retaining each pending approval's captured inputs; Policy expiration/pruning removes obsolete bindings. Wrong confirmation still throws before consuming either the Policy approval or its input binding (`sidecar/icarus_memory/agent.py:182`, `:191`, `:774`, `:793`, `:834`, `:874`; `sidecar/icarus_memory/policy.py:268`, `:280`).
- Agent/store construction is coherent for native and injected paths: inconsistent injected knowledge stores are rejected, new/reopened stores provide their own bound snapshot callback, and ordinary rebuild creates a fresh Policy and Agent together (`sidecar/icarus_memory/server.py:714`, `:885`, `:958`, `:1034`).
- Current cards and historical transcripts retain distinct meanings. Read-back filters current items using fresh common builds, without rewriting the source/time values the old provider saw (`sidecar/icarus_memory/server.py:2477`, `:2500`; `sidecar/icarus_memory/agent.py:913`).
- Runtime documentation accurately distinguishes deterministic provider checks from model quality, and pre-recorder-fix full-suite evidence from later narrower checks. It explicitly preserves the open restore boundary and unchanged private app (`docs/evaluations/memory-quality/runtime/knowledge-time-20260919/README.md:35`, `:49`, `:62`, `:68`, `:93`).

## Issues

### Critical (Must Fix)

None found.

### Important (Should Fix)

1. **[P2] Rejected stale approvals are persisted and displayed as approved.**
   - **Location:** `sidecar/icarus_memory/server.py:2598`, in interaction with the newly added rejection return at `sidecar/icarus_memory/agent.py:823–831`.
   - **Trigger:** A conversation produces a pending action using a knowledge source; that source's metadata or validity changes; the user then grants the pending action through `/api/v1/conversations/{id}/approvals/{approval_id}`.
   - **Observed:** `Agent.resolve` correctly rejects the Policy request and suppresses the action. It returns a normal Turn with `context.invalidated=True`. The unchanged caller treats every normal return with `body.granted=True` as `approval_outcome="approved"`. `_conversation_actions` propagates that persisted outcome (`server.py:2470–2474`), and `ActionApprovalCard.tsx:5` displays “Freigegeben. Das Ergebnis steht im Gespräch.” This contradicts both the actual rejection and the assistant's message that the basis changed.
   - **Focused evidence:** A synthetic real FastAPI/TestClient invocation against this HEAD returned `http_status=200`, `sent=[]`, `card_state='approved'`, `persisted_outcome='approved'`, `invalidated=True`, and reply `Die Grundlage dieser Freigabe hat sich geändert. Bitte stelle die Anfrage erneut.` The reproduction used the existing canonical source fixture, `make_agent`, the real conversation send/resolve routes, and a source-ref mutation before resolve. No mocked resolve or fabricated API payload.
   - **Impact:** The durable action status and visible approval card claim that a request was approved even though the system rejected it. This is a product correctness regression at a newly changed return contract, although execution protection itself works.
   - **Fix:** Carry an explicit actual resolution outcome through `Turn`/the resolve return contract, and persist that value in the conversation route. Do not infer the outcome merely from the requested grant. Also do **not** use `turn.context.invalidated` alone: resolve can execute the action at `agent.py:839`, then replace its context with a follow-up Turn at `agent.py:859`; that follow-up may invalidate after execution has already succeeded. Preserve the original action outcome independently.
   - **Required regression:** Test the actual conversation route: stale grant causes no sink call and persists a non-approved outcome/card on immediate response and subsequent GET/reload. Retain a control where an action executes successfully but its model follow-up invalidates; that must not be relabeled as a rejected action. Ordinary grant, user refusal and wrong-confirmation retry must continue working.

### Minor (Nice to Have)

- **Deferred dependency warnings do not block merge.** The ledger's only deferred minor is two existing Starlette/httpx and anyio `BlockingPortal` deprecations (`.superpowers/sdd/2026-09-14-knowledge-semantic-time-context/progress.md:20`; `checks/full-final.log:27`, `:31`). They are baseline dependency maintenance, with no M2c behavioral regression. Keep them visible and address through a separate dependency change rather than suppressing warnings here.

## Named integration checks

- **Approval lifecycle and shared scoped-agent state:** read `Policy.request/pending/get/grant/reject/_expire` (`policy.py:234–314`), `Agent.scoped`, request capture, reset and resolve. Every production Agent request goes through `_handle` and captures a knowledge map, including explicit empty maps; scoped agents share the same map as the Policy. A new server-owned Agent rebuild replaces both. Existing routing regression covers a scoped chief's approval being resolved on the base agent (`sidecar/tests/test_routing_runtime.py:81`). Existing wrong-confirmation retry coverage checks that the approval remains pending (`sidecar/tests/test_agent.py:340`). No suites rerun.
- **Manual invoke/retry/resolve entrypoints:** inspected `Agent.invoke/_handle/_execute` (`agent.py:565–746`), legacy `/approvals` (`server.py:1573`), conversation resolve (`server.py:2574`) and retry (`server.py:2874`). Manual mail creation resets history and writes explicit empty lineage at creation. Conversation retry loads the relevant stored contexts then calls `send`, so fresh lineage validation remains active. This check found P2 above; no approval execution bypass was found.
- **Store and callback ownership:** inspected `create_app`, `_build_agent` and `_reopen_persistent_state` (`server.py:693`, `:885`, `:942`). The changed callback uses the same EpisodeStore as ClaimStore validation/application cards, and injected differing stores fail early. Fresh production rebuilds create a new empty Policy, so old pending requests are not silently recertified. Custom injected-tool closure/audit rebinding during a full restore is unchanged and not certified by this review; see declined behaviors below.
- **Reset/restart/current-card agreement:** reused the completed task review plus persisted native/Docker restart evidence; checked unchanged `_current_conversation_history`/retry loading and current-card extraction (`server.py:2477`, `:2604`, `:2874`). Stored roots are revalidated, reset boundaries are honored, and strict old v1 knowledge does not acquire current generations. The source-generation antirollback limitation remains explicit.
- **M1d and raw-memory boundaries:** inspected independent egress guard and SelfModel recall integration (`agent.py:217`, `:748`) and the unchanged raw episode tools (`tools.py:620–641`, `:674–699`). M2c knowledge data still enters only local context; SelfModel recall retains its resolver/sensitivity/history contract. Raw tools remain untrusted-data operations and do not become accepted knowledge or inherit the v3 projection guarantees. No claim of general raw-tool source authorization is made.
- **Documentation/evidence coherence:** read the final runtime README and previously preserved baseline/native/Docker/hash artifacts, plus new independent regression output. Counts remain distinct: 1,753 full-suite passes before the recorder-only fix; 168 probe passes after it; actual Python 3.10.21 with 224 passes; 17 native and 6 container checks; subsequent immutable-BASE/current 12-fail/12-pass reproduction. Original TDD ordering remains report-only, not retroactively reconstructed. The source hash manifest identifies the exact reviewed code HEAD.

## Test activity in this review

One new focused synthetic HTTP reproduction was run solely to resolve the previously uncovered approval outcome contract. Its output is quoted in the P2 finding. No existing suite, model invocation, private container, production data or private app was used. The normal pre-existing TestClient deprecation appeared during that probe. All previously reported suite/build/schema/runtime outcomes were read as existing evidence rather than rerun.

## Declined to judge

- **Full restore antirollback/source-generation continuity:** explicitly excluded from M2c, and the retained counterexample shows that an old backup restores an old generation. This review does not turn v3 signatures into restore authority (`README.md:53`; `restore-boundary-result.json:1`).
- **Injected custom tool closures and audit objects after full restore:** pre-existing `_reopen_persistent_state` injected-agent behavior does not rebuild arbitrary caller-supplied tools/audit. This task updates knowledge-store/snapshot bindings only; no full custom-agent restore guarantee is claimed (`server.py:931–939`).
- **General raw episode-tool authorization, raw-tool metadata chronology and lineage:** unchanged raw reads/search use their existing untrusted-data contract; this patch concerns accepted ClaimStore knowledge projection and must not be represented as qualifying every raw-tool result (`tools.py:620–641`).
- **General SelfModel approval provenance across resets:** M2c adds preserved bindings for ClaimStore knowledge; it does not redesign previously existing SelfModel approval capture. Existing M1d checking remains, but broader historical approval coverage was not silently certified (`agent.py:690`, `:798`).
- **Atomic model/source/action transactions:** the accepted contract is optimistic compare-and-revalidate. A source mutation after a check cannot retract already sent provider input, and this patch does not add cross-store/model locks or CAS transactions (`agent.py:486–509`; `m2c-design.md`, Actual Agent boundary and races).
- **Legacy raw `/chat`/`invoke` concurrency versus conversation-route serialization:** existing legacy routes lack the conversation lock used by durable conversations. No new concurrency framework was requested or introduced; this review assesses the changed input/outcome contracts, not a general multi-client Agent serialization rewrite (`server.py:1549`, `:1573`, `:2631`, `:4025`).
- **Real-model answer quality/M3:** synthetic provider evidence establishes bytes and guard behavior only. Wording quality and interpretation of planned/accepted/completed events remain outside this code task (`README.md:51`).
- **Private-app deployment and mainline integration:** private ports 8890/8891 are unchanged and parent PR #48 remains open. This review neither authorizes deployment nor claims the stacked change is already integrated (`README.md:3–5`, `:62`).
- **Published-head GitHub CI:** not established by local artifacts; coordinator must inspect it at the eventual final published revision (`README.md:91`).

## Recommendations

Fix P2 in one bounded wave, add the outcome regressions above, and perform a scoped re-review of the actual outcome contract and caller. Preserve the task gate's accepted projection/lineage behavior and all release qualifiers. The two deferred dependency warnings require no expansion of this patch.

## Assessment

**Ready to merge? No — with the P2 approval outcome fix.**

**Reasoning:** The projection, lineage, store ownership and existing publication boundaries integrate coherently, and the evidence is candid about its limits. One newly exposed caller-contract mismatch makes a rejected action appear approved in durable API/UI state; fix that before merge, then retain the separate final-head CI and stacked-PR integration gates.
