# Independent review: paginated clarification and unsuccessful-answer display

Initial reviewed patch: `22025ec5615cbfb5eac5a5fea0c53392934fb0ea`, based on `9fd6aefa59467e53bfa65d6c7720311052b8c6ac`.
Final repair reviewed and retested: **`258428ce81454bc1b9655a9cd7214f4027748092`**, directly following the initial patch.
Isolated checkout: `/private/tmp/kf-selection-clarification-20261031`.

**Verdict: approved for the requested scope as the series ending at 258428ce. One important review finding was reproduced on 22025ec and independently closed on 258428ce; no important/critical finding remains open. Do not treat 22025ec alone as the approved final state.**

Only synthetic sources, disposable stores, canned providers and local TestClient APIs were used. No root-checkout changes, private files, real model/provider, network or product/test-repository edits by the reviewer. This is not a full-suite, private-model, application or deployment acceptance claim.

## C1 — Single positive unclear page bypassed the uncertainty guard; now CLOSED

On 22025ec, `source_selection_pages.select` returned `positive[0]` immediately when only one of several pages had relevant IDs. The new `_page_uncertainty` marker was only attached after a multi-positive-page final comparison. This left one paginated uncertainty path outside the downstream guard.

Exact synthetic counterexample:

- Six real indexed sources from `seed(ep)` in `test_answer_clarification_projection.py`; all source dates are known.
- Question `Welche Angaben gelten?`.
- First page returns `needs_missing_time_reference` plus its last source ID.
- Second page returns `no_relevant_sources` plus no IDs.
- No additional model comparison is needed or made.

The initial real `select → prepare → render` path returned:

```json
{"case":"single_positive_time_page","calls":2,"page_decisions":["time","unknown"],"answer_status":"reports","uncertainty":"none","render_status":"working_reports","links":1,"invented_time_question":false}
```

Direct selection was `{'status':'time','ids':['S3']}` without the internal marker. The known-time helper promoted it to reports, and the new guard did not run. This was a real uncertainty-status loss rather than an invented time question.

258428ce adds only the missing `_UNCLEAR` marker on that early-return path; a single clear positive page remains unchanged. The owner froze this commit with a clean tree. I repeated the exact original counterexample without changing sources, question, response script or pipeline:

```json
{"case":"single_positive_time_page","calls":2,"page_decisions":["time","unknown"],"answer_status":"selection_failed","uncertainty":"none","render_status":"working_selection_failed","links":0,"invented_time_question":false}
```

Direct selection is now `{'status':'time','ids':['S3'],'_page_uncertainty':True}`. The existing downstream status/type/ID-set guard therefore closes the source instead of promoting it. No model call was added. Permanent tests cover the real known-date counterexample plus all four unclear types on the single-positive-page path.

## Selection/control-flow review

- Every planned page is validated using its actual page IDs; the final comparison is validated against the ordered relevant union when multiple pages have positive results.
- Exactly one uncertainty type from all positive page decisions and the valid final result preserves the whole union and gets an internal marker. Conflicting types, malformed responses, invalid IDs, incomplete/budget/freshness errors stay closed. The model schema cannot inject the internal marker.
- The marker binds uncertainty type and ID set through identity, time, project, focus, allowed-source, omitted-change and own-commitment helpers. Source/type loss or addition fails closed rather than silently returning a partial factual answer.
- The repaired single-positive-page path now has the same binding. Known source time cannot become an invented date question or an unguarded report under this path.
- The four-page cap and existing 60-second selection deadline are unchanged; there is no additional model loop. Independently observed two-page cases used two calls when there was a single positive page, and three calls with two positive pages plus comparison.

## Changed old assertions and explicit selection fixtures

I read all changed old inline assertions in `test_satzantwort`, `test_zweites_tor`, `test_partial_answer_source_loss`, `test_working_memory_identity` and `test_working_memory_own_commitments`.

The intentional display contract is represented consistently: failed generated content remains excluded; rejection counts/reasons, second-gate calls, source-set exclusions, negative statements, unknown original dates, own/foreign authorship and withdrawal assertions remain checked. Complete originals are checked behind an **exact equality of linked source IDs to selected refs**, using unchanged stored bodies. The changes do not weaken the factual/sentence gates or turn rejected partial prose into accepted prose. Rejected legacy saved `saetze` that fail revalidation still retain the prior explicit-original fallback.

The two selection fixture wrappers in `test_working_memory_flow` and `test_working_memory_selection_decisions` set only their own local agent instance to `saetze=False`. Their classification/selection fakes do not supply valid sentence-generation responses; the old inline fallback came from an unsuccessful incidental sentence attempt. These tests now explicitly exercise the unattempted original path. The product default is unchanged, and the new real HTTP tests separately exercise attempted prose with `saetze=True`.

The compact display is confined to automatic `reports` with no confirmed claim basis and a current-version unsuccessful sentence attempt. `nichts` is restored/validated; current-version `zitate` is an explicit failed attempt. Successful sentences, unattempted originals, obsolete versions, unclear selection and confirmed-claim basis keep their prior paths. The code still revalidates full source refs before and after rendering.

## Independent API and source-access probes

Reusable external synthetic tests, with no repository test edits:

`/private/tmp/kf-clarification-independent-probes-20261031.py`

The following were independently run on the frozen final SHA:

1. The exact C1 single-positive time-page counterexample, now closed after two calls.
2. Two relevant source pages with page uncertainty and a final narrowed reports decision: `prepare → render` retains both original links and the person question. Persisted conversation GET returns the same full link set without new calls. Actual clarification POST returns HTTP 201 and the explicit chosen subset. Each original GET returns its complete unchanged body. Revoking one source makes the stored whole answer `working_unavailable` and removes all answer links. Provider calls stay at three.
3. Actual HTTP question with a valid `zitate` sentence attempt over a 6,792-character source containing the unchanged negative statement `Die Freigabe liegt noch NICHT vor.`: response is a 140-character honest uncertainty note with one complete original link. Original GET returns the full body. Saved GET adds no provider work. Source withdrawal removes the whole answer basis. Claim revision and original source body stay unchanged.

Observed probe log:

```json
{"probe":"single-positive-time","calls":2,"answer":"selection_failed","render":"working_selection_failed","uncertainty":"none","links":0}
{"probe":"person-union-api","calls":3,"links":2,"choice_http":201,"get_originals":"complete","withdrawal":"working_unavailable"}
{"probe":"compact-http","original_chars":6792,"render_chars":140,"links":1,"get_model_calls":0,"withdrawal":"working_unavailable"}
```

## Test evidence

Initial patch regression review, before the one-path repair: **243 passed, one existing Starlette/httpx deprecation warning, 33.54 seconds**. This included all changed old test modules and did not cover C1, which was found by the independent counterexample.

Final frozen-SHA command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python -m pytest -q -s -p no:cacheprovider /private/tmp/kf-clarification-independent-probes-20261031.py sidecar/tests/test_answer_clarification_projection.py sidecar/tests/test_source_selection_pages.py
```

**50 passed, one existing Starlette/httpx deprecation warning, 9.85 seconds.** Includes all projection/pages tests and the three external probes; the counts are not added to the earlier 243 as though they were unique tests. The owner separately reports larger targeted runs; this report claims only the commands personally executed.

`git diff --check 9fd6aef 258428ce81454bc1b9655a9cd7214f4027748092` passed. HEAD matched the final SHA and the tree was clean when inspected after freeze.

## Limits

An uncertainty question may still display full original text; compactness was deliberately scoped to automatic reports after an unsuccessful sentence attempt. The compact notice does not claim that information is absent, resolve a factual conflict or establish authorship/responsibility. Sources remain complete behind freshly revalidated links. No private-source result, real model usefulness or root cherry-pick state is inferred from this synthetic review.
