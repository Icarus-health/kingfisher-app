# Source-bound person choice — 4 November 2026

This repairs actual `Agent.answer_memory` person selection, not merely the
order of retrieved candidates. Two artificial mails belong to two different
Alex Winter mailboxes. No personal source, application setting or import was
changed; no cloud API was called.

## What changed

Previously any matching word/address anywhere in a question could select a
namesake. `Wo erreiche ich Alex Winter, aber nicht aus dem Einkauf?` therefore
selected the purchasing contact the user had just excluded. A question asking
for evidence of a person's affiliation could similarly assume that very
affiliation while selecting the person.

Only positively attached identity/context qualifications in supported question
forms now narrow the person. Negated, disputed or alternative qualifications
ask which person the user means before question understanding, semantic search
or answer generation. Source-bound choices remain available. Unknown complex
forms may require an extra clarification; this is not a general language parser.

Explicit email/domain choices and existing positive project/organization/location
questions remain supported. Negation of a task (`noch nicht erledigt`) can coexist
with an unambiguous person qualification. No source, stored index or identity is
rewritten. Existing confirmation/merge/revocation controls stay authoritative.
An answer saved under the former silent selection becomes stale under the
existing identity freshness check.

## Test and independent review evidence

- Initial reproduction: six wrong-choice cases failed, six controls passed.
- Extended tests caught three usability regressions in the prototype; corrected.
- Independent review found trailing disputed clauses and alternative separators
  (including two email addresses separated by `/`) still caused silent selection.
  It also found an explicit-address imperative unnecessarily clarified.
- Eight review regression cases failed before one bounded correction pass.
- Actual model probe then exposed `Bis wann soll Alex ... liefern?` unnecessarily
  clarifying; two new tests reproduced it, and the missing positive form was added.
- **162 affected tests passed** in 40.52 seconds, including identity merges, undo,
  source revocation, mail-header names, transliterations, answer labels and stale
  selections. [Exact test set and code hash](tests.json). This is not a full-suite run.
- The independent reviewer rechecked both reported important issues and the
  explicit-address imperative, ran all 25 new cases successfully, verified the
  live artifact's source hashes, and read the five completed replies against
  the artificial sources. No semantic error was found in those completed replies.

## Actual Qwen probe: development and interrupted runs

The [six frozen questions and synthetic source text](resource-stop.json) use the
installed `kingfisher-qwen3.5:9b-8k`, digest
`8a5919e3ddda74b7729b65ca0bad9896d36615d872756ca98b17ec8a80374b17`.
The diagnostic runs the real answer path with model question understanding,
selection, sentence generation and same-model sentence verification. Indexing
is deterministic, so this does not test ingestion. Semantic search is disabled;
the separate BGE run is [documented independently](../2026-11-04-retrieval-precision/).

The [first run](first.json) correctly clarified the three ambiguous cases and
answered the contact question, but incorrectly asked for clarification on two
explicitly qualified deadline questions. That failed evidence remains recorded.

After the positive-form correction, the same questions produced:

| Case | Observed result | Model calls | Elapsed |
|---|---|---:|---:|
| Bare namesake | Two source-bound choices, no guess | 0 | 0.016 s |
| Negative affiliation | Two source-bound choices, no guess | 0 | 0.002 s |
| Disputed affiliation | Two source-bound choices, no guess | 0 | 0.002 s |
| Purchasing contact | Correct address, only purchasing source | 4 | 21.264 s |
| Purchasing deadline | Alex's offer comparison due 6 November 2026 to Sören, correct source | 4 | 14.294 s |
| School deadline via explicit address | Interrupted after question-understanding call; **no completed answer** | 1 | — |

The second run stopped at **24% free memory**, below its unchanged 25% reserve
gate. Pressure remained level 2. Its overall `live_model_verified` remains false
because final verification/withdrawal checks were not reached; completed transport
calls independently verified the installed local weights before and after each
request. Nine calls finished, but only two generative answers completed. Do not
describe this as six passed cases or a fluid-Mac acceptance. The first run did
verify original-source preservation and withdrawal; the interrupted final run
does not inherit those checks as if it completed them.

## Completed run after resource recovery

A later read-only preflight measured **63% free memory**, pressure level 1 and
no loaded model. This material reserve change justified repeating the exact
six cases under the same limits, with no production code, fixture or expected
answer changes. No user application was closed and no memory threshold lowered.

The [completed run](completed.json) passed all six case checks in **50.163 s**:
three source-bound clarifications without model calls, and three correct
source-backed answers with four model calls each (12 total). The contact answer
took 21.452 s; purchasing deadline 14.021 s; school deadline 14.248 s.

The last answer correctly states that the school contact promised the timetable
to Sören by **13 November 2026**, citing only the school source. The purchasing
contact instead promised the offer comparison by **6 November 2026**. An
independent reviewer read all six final replies against both artificial sources:
no person mixing, unsupported statement or wrong date was found in this run.
Final installed-model verification, original preservation and source-withdrawal
invalidation also passed.

Free memory reached a minimum of **25%**, pressure at most 2. This stayed within
the gate but leaves limited margin and is not a native UI responsiveness or
endurance measurement. The earlier failed and interrupted reports remain in the
record; the completed evidence does not turn them into successful runs. This is
one frozen synthetic development set, not universal quality or a held-out test.

## Reproduction and remaining gates

With repository dependencies installed and sufficient Mac memory, run:

```sh
python docs/runs/2026-11-04-person-choice/probe.py /private/tmp/kingfisher-person-probe-new.json
```

The output must not exist. The driver uses temporary artificial stores, literal
loopback Ollama, no proxy/download/cloud, an 8K context, 15-second keep-alive,
20-call/240-second limits, and resource/competing-model checks before/after calls.
It saves checkpoints. Do not close other applications, relax the reserve gate or
repeat expensive runs solely to obtain a green report.

Still required: local-model acceptance in the updated installed app, native
interaction, representative source acceptance and the broader P0–P6
product plan. The large import remains paused; this branch is not installed yet.
