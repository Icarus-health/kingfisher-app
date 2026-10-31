# Independent read-only review of the source-boundary repair

Checkout: `/private/tmp/kf-answer-source-boundaries-20261031`, reviewed working diff against `47b3c17`. This is review of working changes, not an immutable committed artifact. The reviewer did not change product or repository tests.

## Verdict

The original HTML/DOCX excerpt failure is resolved in the independent reproduction. **The one important review counterexample R1 is now independently retested CLOSED. No important/critical finding remains open in this narrow review.** The historical R1 evidence is retained below, followed here by the exact repair retest. No new broad audit was opened.

## R1 closure retest

Reviewed final `_originalanzeige` now permits a changed line only if the existing `originalabschnitte` splitter already recognizes that exact trimmed line as a complete, single-line original unit ending in `.`, `!` or `?`. A whitespace change inside a multi-line original unit returns the original raw text; its existing >400 limit therefore produces the honest quotation fallback. This does not add a syntax list, new sentence parser or a relaxed raw visibility gate.

I extracted the exact original 685-character R1 script below from this report and executed it without changing its source text, question or ID-only selector. Result:

```text
rawchars 685 status zitate sentences [] reasons []
```

There was no offered normalized unit and no provider call. Source body remained raw. The permanent regression test `test_langes_unzitiertes_codeoriginal_wird_nicht_durch_indentverlust_zur_antwort` covers the same source.

Independent positive control used the full raw 686-character rate paragraph, including 620 indentation spaces, and an active synthetic second gate. `formulieren` returned `saetze` with both complete original statements; the actual judge payload contained the entire unchanged raw 686-character paragraph. A display-equivalent but raw-incomplete excerpt still returned `zitate` before any provider call.

```text
PASS: Rate620 status saetze; both original sentences, unchanged raw686, active judge sees whole raw unit
PASS: normalized-only visibility does not bypass raw complete-visibility gate

pytest -q -p no:cacheprovider sidecar/tests/test_answer_source_boundaries.py sidecar/tests/test_original_sentence_selection.py sidecar/tests/test_normative_paragraph_context.py sidecar/tests/test_absatzauswahl_saetze.py
72 passed in 3.86s
```

This includes the new R1 regression, real parser/store/prepare/render rate and Word controls, hidden unrelated rule, employment/return-date separation, person/date mutation, injection removal, normative context, and raw second-gate checks. Scoped `git diff --check 47b3c17` passed. No full-suite or real-model/Mac acceptance claim is made.

Retested file SHA-256:

```text
2119db2346442e625acd32f673191ceefda54116666192f85b9201787e6d4012  sidecar/icarus_memory/satzantwort.py
fbb974580f81e26d95689392cd1f6d5ae295b617d33dfdfb8ed18f317c0bdf91  sidecar/icarus_memory/absatzauswahl.py
424963314734aefc07ed6e877d0cbcbba2e5341b55c8c5ce49f0ecbc2980ce21  sidecar/icarus_memory/document_text.py
c70170b06015d9457a7b34ac59874a6796a0377e2077ce556f242b4a5007033c  sidecar/icarus_memory/connectors/mail.py
2e2a85d7ce308256badf0e20ba9d9941f3a80292ea6f23de849bfe9c23b6b34c  sidecar/tests/test_answer_source_boundaries.py
```

Review counterexample count stays 1: closed 1, open 0. The conclusion is limited to the explicit transformation contract and tested boundaries; it is not an arbitrary-code interpretation claim.

## Verified repairs

Executed the exact existing synthetic probe script from the repair checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python /private/tmp/kf-answer-boundary-probe-20261031.py
```

Results:

- HTML rate mail with 0, 120 or 620 indentation spaces: `saetze`, one answer-provider call, 191-character rendered answer; complete source is no longer dumped.
- Real DOCX form, privacy rule before the target or hidden at the end: employment-start field remains visible and produces `saetze`, rendered answer 250 characters. Date remains in its original employment-start field and its complete heading/neighbor source unit.
- Return-date question with a valid empty canned formulation remains empty (`nichts`) and uses the existing source fallback. No new claim that a return deadline was inferred, and no claim of real model comprehension.
- Raw-complete visibility remains mandatory: an excerpt that is only whitespace-normalized-equivalent to the original does not get an offered original unit and exits to `zitate` before provider invocation.
- Independent completion probe retained an exact source unit, retained a real omission marker and excluded `HIDDEN_SENTINEL`; accepted completed text stayed within its 2,500-character budget.

The completion code uses spans from the same raw `episode.body`, before `_bereinigt`; it unions raw ranges in source order and only bridges gaps containing whitespace. It does not introduce a new parser, and `_originalstellen`/existing answer completeness checks remain responsible for atomic rule context. A pre-existing excerpt already over budget can be returned unchanged; the helper's limit is a bound on accepted replacement projections, not an unconditional cap on every existing-return path. This contract caveat was sent to the implementer, and is not another important regression finding.

Independent test command:

```text
pytest -q -p no:cacheprovider sidecar/tests/test_answer_source_boundaries.py sidecar/tests/test_original_sentence_selection.py sidecar/tests/test_normative_paragraph_context.py sidecar/tests/test_absatzauswahl_saetze.py
71 passed in 3.66s
```

Scoped `git diff --check 47b3c17` passed.

## Historical R1 evidence: long code/preformatted source lost meaningful indentation

Relevant new code: `satzantwort.py:552-561` `_originalanzeige`, called after raw visibility checks at lines 583 and 593. The raw visibility check is correct, but the later text transformation is not semantics-neutral for indentation-sensitive material.

Fully visible synthetic source, 685 characters:

```python
raw = ('Regel: Die Ausgabe darf nur so lauten:\nif ready:\n'
       + ' ' * 620 + 'send()\nfinish().')
```

An ID-only synthetic selector requests offered `beleg=1, satz=1`. Actual offered and accepted text is:

```text
Regel: Die Ausgabe darf nur so lauten:
if ready:
send()
finish().
```

Observed output:

```text
rawchars 685 status saetze
sentences ['Regel: Die Ausgabe darf nur so lauten:\nif ready:\nsend()\nfinish().']
reasons []
```

This changes the source's code meaning/validity by removing `send()` indentation. The old >400 limit would have fallen back to quotations. The added short-code test only exercises raw text below 400 characters, where normalization is not entered. Backtick/quote guards do not protect this unquoted preformatted text. The existing `originaltext` comparison also folds whitespace, so it does not reject the change. Unchanged stored source and raw judge evidence do not make the displayed original faithful in this case.

Repro:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python - <<'PY'
import json
from datetime import datetime, timezone
from icarus_memory import satzantwort as sa
from icarus_memory.providers import Reply
raw = 'Regel: Die Ausgabe darf nur so lauten:\nif ready:\n' + ' ' * 620 + 'send()\nfinish().'
class Visible:
    is_local = True
    name = model = 'synthetic-code-layout'
    def complete_json(self, messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        print('offered', repr(payload['belege'][0]['originalsaetze']))
        return Reply(text=json.dumps({'status':'antwort','originalstellen':[{'beleg':1,'satz':1}]}))
beleg = sa.AntwortBeleg(1, {}, 'conditional', 'synthetic', 'Code', '', raw, None)
result = sa.formulieren('Wie lautet die Ausgabe?', [beleg], Visible(),
                       jetzt=datetime(2026,10,31,tzinfo=timezone.utc))
print('rawchars', len(raw), 'status', result.status,
      'sentences', [repr(s.text) for s in result.saetze],
      'reasons', [v.gruende for v in result.verworfen])
PY
```

Minimal safe boundary proposed at discovery: do not normalize an indentation-sensitive/preformatted original into an apparently literal answer; preserve the honest existing quotation fallback for such units. The closure section above records the resulting conservative existing-unit guard and independent exact retest.

## Limits

Synthetic saved providers only. No real model, network, private mail/data, Docker, Mac UI or deployed behavior was touched. The initial 71-test run did not cover R1; the later 72-test closure run does. No full backend-suite acceptance claim is made. The original diagnosis, frozen baseline and detailed stage payloads remain in `/private/tmp/kf-answer-boundary-diagnosis-20261031.md` and `/private/tmp/kf-answer-boundary-probe-20261031.baseline.json`.
