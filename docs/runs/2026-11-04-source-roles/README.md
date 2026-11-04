# Local source roles — regression and ongoing acceptance

The actual native Kingfisher 1.0.43 window was tested on 4 November with the
previously created **artificial** source `KF-Modulprobe43-20261103.txt`.
The user asked who must do what and by when, distinguishing the meeting.
The source says Vera König asks Sören Kube to deliver the Nordstern draft by
7 November 2026, 17:00; Matthias Braun delivers documents by 6 November, 12:00;
the meeting is 9 November, 10:00.

The real Qwen9B/Harness answer attributed the draft delivery to **Vera**, not
Sören. The other owner and both deadlines/meeting were correct. The output
was visibly an unverified draft, created no tasks and changed no source. The
source panel remained operable and retained the question after collapse and
reopening; this is an interaction observation, not a latency benchmark.

This is a failed semantic acceptance, despite successful transport and exact
source-read receipts. The bulk import remains paused. No paid calls occurred.

## Frozen expectations before the correction

| Artificial case | Required interpretation |
|---|---|
| requester-versus-owner | Vera requests; Sören delivers draft 7 Nov 17:00; Matthias delivers documents 6 Nov 12:00; meeting 9 Nov 10:00 |
| requester-owner-reversed | Sören requests; Vera delivers draft 7 Nov 17:00; Matthias delivers documents 6 Nov 12:00; Sören has no delivery |
| person-task-deadline | Vera requests Sören's draft by 7 Nov; do not attribute delivery to sender |
| appointment-versus-deadline | Matthias delivers documents 6 Nov 17:00; meeting 9 Nov 10:00; no Sören commitment |
| ambiguous-name | No Alexander selected, no deadline invented; direct question to choose the intended Alexander |
| ambiguous-other-name | Ask the user directly to choose Jana Neumann or Jana Peters; no deadline invented |
| meeting-as-deadline | Sören delivers draft by the explicitly stated meeting deadline 9 Nov 10:00; no attendance invented |
| three-name-candidates | Direct clarification includes Alexander Meier, Alexander Wolf and Alexander Braun; no one chosen |
| delegated-request | Sören is asked to inquire, with no stated deadline; Matthias has not committed; proposed delivery date is not a confirmed commitment |

The two role cases are added to the existing isolated real-model probe.
Its `completed_for_review` means completed execution only. Semantic results
must be assessed against the table, including false positive ownership.
No change to evidence validation or to model/provider permissions is proposed.

The first isolated repeat of `requester-versus-owner` with the old prompt was
correct (34.805 seconds, two model calls, maximum sampled memory pressure 2,
cleanup verified). This does not erase the native-window failure: the answer
is sensitive to its context. The proposed correction adds explicit requester,
performer and recipient distinctions to the source-worker instructions. It
must pass the role reversal and the other cases; a prompt is not a guarantee.


## Evidence-anchor correction

Two previously rejected private category proposals were inspected locally only:
one changed a nonbreaking space into an ordinary space; another proposed a
person absent from the nominated block and used metadata as a nonexistent
block. The existing generic retry repeated these errors. No private names,
bodies, metadata or provider keys are in this run record.

The correction keeps the exact-source validator unchanged. For remote extraction, JSON represents
NBSP and narrow NBSP explicitly as escapes; decoding yields the identical
original text. A repair request now identifies the zero-based rejected entity
indices and their validation reasons. It does not propose a substitute name or
block. Only the already opted-in, bounded remote repair can make its existing
second call; permissions are rechecked and uncorrected results still fail as a
whole. No new cloud work was started to validate this change.

Three new artificial regression tests failed before the correction and passed
after it. The full category/repair/intake-script subset passed 66 tests. These
prove encoding, feedback and validation behavior, not real-provider quality.
The actual artificial local `explicit-deadline` intake case separately passed
persons, task evidence, deadline and required category checks in 15.728 seconds
with three model calls; originals remained unchanged. This is one current
observation, not evidence that the earlier omission is impossible.

The first five-case role-prompt run completed all transports, but only four
semantic cases passed: `ambiguous-name` described the two candidates and missing
deadline without asking the user directly. The follow-up instruction requires
that clarification question first, and adds an unseen Jana ambiguity case.
Its result is recorded separately below when the run completes.


## Independent review and final candidate

A fresh reviewer independently confirmed the second run was **4/6** semantically
acceptable despite completed transport: it omitted Vera when asked who requests
the work and invented Matthias as performer of a meeting task. The direct Alex
and Jana clarification questions did work. That intermediate result was not
accepted or deployed.

The reviewed prompt removes the forced performer-first format, answers the
actual question and permits only explicit roles. A meeting alone is not a
deadline, but an explicit “by the meeting” can be one. Clarification covers all
named candidates rather than a fixed pair. Three review-derived cases extend
the frozen expectations above. This is one review correction pass, not an
assertion that prompt wording guarantees factual accuracy.

The reviewer also reproduced an 8K-input regression from escaping NBSP on the
local path. The correction is now remote-only. A regression uses the actual
local payload builder on a 7,039-character artificial source without network or
inference. Its first test draft incorrectly supplied a remote policy to a local
provider; after fixing the fixture, restoring the old escaping in memory made
the test fail with the intended `InputTooLarge`. With the guard it passes.
Duplicate-anchor indices are now included in repair feedback as well; the
all-or-nothing validator and single repair limit are unchanged.


## Final local run

The final nine artificial cases passed the frozen semantic criteria on actual
Qwen9B, including the three new review cases. See
[the sanitized answers and timings](local-model-results.json). Execution took
306.548 seconds overall, with 18 model calls and 27.651–38.404 seconds per case.
All sampled runtime-status calls stayed below three seconds. Sampled Mac
memory pressure peaked at level 2; this is an API-responsiveness observation,
not proof that all other Mac applications remain fluid. Test containers were
removed and artificial originals were unchanged. No paid calls occurred.

Results remain unverified drafts; no tasks were created. These nine cases do
not establish universal model correctness, private full-store retrieval,
cloud repair quality or acceptance of an updated native Mac application.
The large import remains paused. The product goal P0–P6 remains in progress.

Code regressions: 68 category/repair/intake tests; 429 module/Harness tests;
31 gateway tests plus 22 subtests; 22 Node service tests passed with one
pre-existing skipped test. Gateway/service tests required local test-port
permission after sandbox listen failures. No full backend-suite result is
claimed for this change.


The complete seven-case artificial intake rerun also passed all declared person,
task-evidence, deadline and category checks in 76.432 seconds with 19 actual
Qwen calls; see [intake results](intake-results.json). This exercises ingestion,
classification, extraction, task review and deterministic deadline parsing in
temporary stores. It does not assess all possible task owners or a personal
archive; the separate source-role cases address some of that gap.


## Retrieval gate still open

The existing artificial BGE-M3 comparison completed 20 attempts (10 cases ×
lexical/hybrid), with unchanged installed weights and no chat model calls.
Hybrid retrieval was exact in **8/10**, lexical in **4/10**. All expected evidence
was found by hybrid search, and withdrawn/expired evidence stayed excluded,
but two cases delivered extra evidence: the other Alex Winter despite the
explicit purchasing department, and unrelated claims for the message-sent
question. See [retrieval results](retrieval-results.json).

This is a failed precision gate, not a complete memory acceptance. No retrieval
ranking code is changed in this patch. Investigate identity/context-aware
selection and weak lexical overlaps next, against counterexamples before
changing filters. Do not resume the bulk import on the strength of the intake
or source-worker results alone.
