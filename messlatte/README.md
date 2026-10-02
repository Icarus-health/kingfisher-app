# Messlatte

A measuring instrument for Kingfisher's memory. Every future change to memory,
retrieval or answering is meant to be measured against it.

The goal it measures: **never a false statement**, put things in the right
context, find them precisely (also "contact three years ago", and ambiguous
questions such as "What is going on with Mainz?").

The Messlatte plays an invented, coherent world (three years of mail,
appointments, call transcripts and notes, format: [FORMAT.md](FORMAT.md)) through
the **real product paths** and asks its questions through the **real answer
path**. It changes no product code and no product setting.

## Stages

Each stage is one module with one job; stages exchange only data classes
(`daten.py`, `ergebnisse.py`). A stage can be replaced without touching the
others.

| Stage | Module | Question | Needs a model |
|---|---|---|---|
| Load | `welt.py` | Is the world valid against FORMAT.md? (unique IDs, evidence IDs exist, times before the cut-off date, only `.example` domains, categories, Sent mails from the user) | no |
| Noise | `rauschen.py` | N unremarkable everyday sources over three years, sharing words with the scenarios, never answering a question (seeded, deterministic) | no |
| Ingest | `aufnahme.py` | Does every source arrive through the product path? counts: ingested, duplicated, failed; mapping world ID to episode ID | no |
| Retrieval | `abruf.py` | Does the product's search deliver the expected evidence (recall, rank) and no forbidden evidence? Are all meanings of an ambiguous term offered? | **no** |
| Answer | `antwort.py` | What does the user read? Through the conversation API, cold and warm latency reported separately | yes |
| Rating | `bewertung.py` | Pure functions: required statements, forbidden statements, behaviour, result class | no |
| Report | `bericht.py` | JSON (complete) and Markdown (for people) | no |
| Local | `lokal.py` | The same rating against the running instance with your own questions; report without contents | the instance's model |
| Cases | `faelle.py` | Reports "Stimmt nicht?" become a questions file for Local (one rule, shared with the product's `GET /api/v1/rueckmeldungen/faelle`) | no |
| User actions | `handlungen.py` | Projects, source-to-project assignments and accepted statements of the world (`projekte`, `projekt`, `angenommen` in FORMAT.md), played through the UI's routes | no |
| Lint | `lint.py` | Does the lint across all case files (`docs/42-lint.md`) find every finding the world expects (`lint` in FORMAT.md), with no false alarm, and without writing a fact? | no |
| Private | `privat.py` | Does Kingfisher suggest the expected circle per person (with the expected features named in the reason), the expected private case-file kinds and every termination or payment deadline (`kreise`, `akten_arten`, `fristen` in FORMAT.md)? Counts every person suggested as inner circle without that expectation (world and noise) as a false inner circle, and every number in a deadline suggestion that no source contains. Runs inside `lauf` when the world has such expectations (`--nur privat` for this stage only) | no |

If no model is given (`--modell keins`) the answer stage is skipped and shown
as **"not measured"** in the report, never as "passed". The retrieval stage still
measures something meaningful: it runs the product's search with a stand-in that
selects every candidate.

## Commands

```sh
# Full measurement, no model: ingest + retrieval
python -m messlatte lauf --welt messlatte/welt --modell keins --ausgabe /tmp/messlatte

# With a local model (answers through the conversation API)
python -m messlatte lauf --welt messlatte/welt --modell ollama:qwen2.5:14b --ausgabe /tmp/messlatte
python -m messlatte lauf --welt messlatte/welt --modell kompatibel:http://127.0.0.1:1234/v1:mein-modell

# Scale: 10 000 / 50 000 everyday sources between the scenarios
python -m messlatte lauf --welt messlatte/welt --rauschen 10000 --seed 1

# One category only
python -m messlatte lauf --welt messlatte/welt --nur mehrdeutigkeit

# Long sources: every mail padded to 3,000 and every transcript to 30,000 characters
# (signature, disclaimer, quoted earlier mail, small talk; required statements unchanged)
python -m messlatte lauf --welt messlatte/welt --lange-quellen
python -m messlatte lauf --welt messlatte/welt --lange-quellen --lange-transkript-zeichen 11000

# Private stage only (circles, private case-file kinds, deadlines; docs/49-kreis-und-privat.md)
python -m messlatte lauf --welt messlatte/welt --modell keins --einordnung regel --nur privat

# Validate a world (also useful while writing one)
python -m messlatte pruefen --welt messlatte/welt

# Lint across all case files: expected findings found, false alarms, facts unchanged (no model)
python -m messlatte lint --welt messlatte/welt [--rauschen 10000] [--ausgabe DIR]

# Your own questions against your running instance
python -m messlatte lokal --fragen messlatte/beispiel-eigene-fragen.json

# Turn the "Stimmt nicht?" reports (docs/38-rueckkanal.md) into such a file, then measure it
python -m messlatte faelle --aus <data folder>/rueckmeldungen.sqlite3 --ausgabe rueckmeldungen-faelle.json
python -m messlatte lokal --fragen rueckmeldungen-faelle.json
```

`faelle` reads the reports store read-only (or the JSON of `GET /api/v1/rueckmeldungen`) and writes a
questions file in the format below. **That file contains your question and answer texts**: it is a
local file for this machine, not for the repository, a report or a pull request. The terminal shows
counters only, and the `lokal` report stays free of texts. A reported answer becomes a forbidden
statement, "Richtig wäre …" a required one; resolved reports stay in the file as regression cases.

`--modell` is `keins`, `ollama:NAME`, `kompatibel:URL:NAME` (the URL needs a
path) or `anthropic:NAME` (only with `ANTHROPIC_API_KEY` in the environment; keys
are never written to a report). Whether a provider counts as local is decided by
the product (`is_local_endpoint`), not by the Messlatte: a cloud provider goes
through the path the product provides for it, and its answers to memory
questions are then usually "local only", which is rated as *refused*.

`--modell-pruefung SPEC` (same forms) assigns a model to the role "pruefung", the second gate of the sentence check (`satzpruefung_modell.py`, `docs/35-belegte-antworten.md`): every sentence that passed the rule-based check is sent, with the full text of its evidence, to this model, which answers yes, no or unclear; only yes keeps the sentence. Without it the gate is off, as in the product without an assignment. The report counts rejected sentences per gate ("Zwei Tore der Satzprüfung").

`--modell skript:sorgfaeltig|unaufmerksam` and `--modell-pruefung skript:pruefung` are scripted stand-ins driven by the `skript` field of a question (FORMAT.md): a careful script writes the correct sentence, a careless one adds a false sentence that uses the same words; the scripted checker rejects exactly the false sentences of the world. They measure the mechanics (are false sentences rejected and counted, is no correct sentence lost), not a real model. Use them with `--nur inhalt --einordnung regel`.

`--modell-frage SPEC` (same forms as `--modell`) assigns a model to the product's role "frage", which turns a question into a structured request (things, period, intent, search words, paraphrases; `docs/31-frageverstaendnis.md`). Without it, as in the product without an assignment, the deterministic fallback understands every question, even if `--modell` is running. The report names the model of the role and counts how many questions were understood by the model and how many by the fallback (with the reason).

A local model also classifies the world's sources itself (like the product does);
noise is always classified by a constant stand-in (`--einordnung konstant` turns
the model classification off for everything).

Run the tests with `python -m pytest messlatte/tests` (they use their own small
world under `messlatte/tests/mini_welt`, never `messlatte/welt`).

## Long sources and "context cut off"

The world's sources are short (mails under 300, transcripts under 900 characters), so the
context budget (32,000 characters) never bites. Real mails have 2 to 4 KB, transcripts 20 to
100 KB. `--lange-quellen` (`lange.py`) pads every mail (world and noise) to `--lange-mail-zeichen`
(default 3,000) and every transcript to `--lange-transkript-zeichen` (default 30,000): the original text
stays verbatim (mail: on top, transcript: in the middle), the rest is synthetic filler from the noise
vocabulary, checked against every required and forbidden statement, name and address of the world,
so the sets of sources containing a required or forbidden statement do not change. Deterministic per
`--seed`. The working memory classifies a long source in sections (`abschnitte.py`,
`docs/35-belegte-antworten.md`, "Lange Quellen in Abschnitten"), so 30,000-character transcripts can become
evidence; only sources over the upper limit of 200,000 characters are never classified, and the report counts
those separately (before the sections existed the limit was 12,000 characters: 5 expected sources, see the
measurement of 2026-09-30).

Three numbers keep the reasons apart: **"nicht gefunden"** (the search never delivered the source),
**"Kontext abgeschnitten"** (found, but the character budget was full: expected sources missing from the
context, `search.abgeschnitten` of the product) and **"ohne tragende Textstelle"** (the source is in the
context, but none of the required statements its full text carries is visible any more). The second
and third are what the two-stage selection (`absatzauswahl.py`, `docs/35-belegte-antworten.md`) is
measured by.

## Reading the report

The top of every report shows the same three numbers, always as "x of n" (there
are no percentages: on small numbers they promise more than is there):

* **False statements** – answers that contain a forbidden text (outdated date,
  wrong person, followed foreign instruction). The most important number. It is
  never hidden in an average and blocks a change regardless of the rest.
* **Correct** – answers of result class `richtig`.
* **Not measured** – questions the run could not judge, and why.

Result classes per question: `richtig`, `unvollstaendig` (only part of the
required statements/evidence), `falsch` (a forbidden statement or citation, no
required statement at all, an invented answer to a `nicht_bekannt` question, or
one meaning picked arbitrarily instead of asking), `unnoetige_rueckfrage`,
`verweigert` (says "not available" or is refused although an answer is
possible), `fehler` (technical failure, no usable answer). Aggregates per
category, per severity and per origin (`welt`, `holdout`), each with its case
count, followed by the list of failures (question ID, expectation, actual answer
truncated).

Behaviour is recognised structurally first (`answer_contract.status`, offered
choices) and by wording only where the product gives no status; the recognised
"not available" phrasings are in `bewertung.NICHT_BEKANNT_FORMULIERUNGEN`.

## Writing your own questions

The question format is the one from FORMAT.md (a `fragen` list, or a bare list):

```json
{"fragen": [{
  "id": "eigene-01",
  "frage": "Bis wann muss ich das Angebot für die Firma Muster schicken?",
  "kategorie": "frist", "schwere": "kritisch",
  "erwartet": {"verhalten": "antworten", "aussagen": [["15. November", "15.11."]]},
  "verboten": {"aussagen": ["31. Oktober"]}
}]}
```

* `erwartet.aussagen`: a list of **alternative groups**. Every group must appear
  in the answer; within a group one spelling is enough. Comparison ignores case
  and whitespace.
* `verboten.aussagen`: any appearance is a **false statement**. Put the outdated
  or wrong value here, not a paraphrase of the right one.
* `verhalten`: `antworten`, `rueckfrage` (`erwartet.bedeutungen` lists the groups
  of words by which each meaning is recognised in the offered choice) or
  `nicht_bekannt` (nothing is available; inventing something is `falsch`).
* In `lokal` mode `belege` are ignored (there is no world to check them
  against), `kategorie`/`schwere` are optional, and every `antworten` question
  needs at least one required statement **or** one forbidden statement ("never say
  this again", as in cases from reports). See `beispiel-eigene-fragen.json`.

## The `lokal` mode: your own data

`python -m messlatte lokal --fragen DATEI.json [--adresse http://127.0.0.1:8890]`
asks the **running** instance over HTTP, through the same conversation API as the
UI. The token comes from the environment (`ICARUS_SIDECAR_TOKEN`) or from
`.kingfisher.env` in the repository root (the file `make start` writes).

* **Privacy:** the report contains only IDs, categories, result classes,
  counters and timings. No question, no answer, no source content, no expected or
  forbidden statement is written to any file. Sharing it shares nothing personal.
  `--zeigen` prints the answers to the terminal only, never to a file.
* **Side effect:** each question creates a conversation titled "Messlatte" in the
  instance and is captured as a conversation source, like any question in normal
  use. The API offers no way to delete conversations.
* This module does not import the product; it needs only `httpx`.

## Answer time

Both `lauf` and `lokal` report, per stage, the median and the 90th percentile (`zeiten.py`, no percentages of
cases, only seconds): retrieval per question (`lauf` only), the whole answer through the API (warm, the first
cold answer is left out), and the sections the product itself attaches to every answer (`context.zeiten`, see
`sidecar/icarus_memory/zeitmessung.py`): understanding the question, search and context, the answer model
(source selection), the sentence model (second call) and the sentence check. A section that did not run
(no model, sentences switched off) is absent, never zero.

The report carries one line, **"Antwortzeit im Ziel: ≤ 8 s Median"**, with *bestanden* or *nicht bestanden*
when a model ran, and *nicht gemessen* when none did. The goal is judged on the warm end-to-end median. In
`lokal` the numbers stay content-free.

## Holdout rule

The holdout is a second world in the same format that lives **outside the
repository**. It is written by someone other than the agent that optimises the
product, and that agent must never write, read or run it. It is loaded with an
additional `--welt`, given a name so it stays separate in the report:

```sh
python -m messlatte lauf --welt messlatte/welt --welt holdout=/pfad/zum/holdout --modell ...
```

It must share the cut-off date and time zone with the main world and use
globally unique IDs (the validator checks both); all worlds go into **one**
store so the system must find the right place among all of them. The report
shows origin `holdout` in its own row. A holdout whose contents were seen by the
optimising agent is a development set from then on and must be replaced.

## Where the Messlatte deliberately follows the product, and where it does not

| Source | Product path used | Boundary |
|---|---|---|
| Mail | `mail_intake.Intake.step` with the real `connectors/mail.py::MailConnector` as reader, then `mail_ingestion.remember` (folders INBOX and Sent, cursor, retry via `Intake.retry`) | only `imaplib.IMAP4_SSL` and the TLS context are replaced (`postfach.py`); no TLS, login, provider quirks, attachments or HTML; plain `text/plain` messages |
| Notes, transcripts | `scheduler.ingest_job` with adapter `markdown`, files with front matter (`title`, `date`, `participants`) | the product's folder adapter stops at 5000 files per folder; noise notes are capped at 4000 |
| Appointments | `mac_calendar.MacCalendar` (enable, select, live snapshot of the current year) and then the worker's memory sections sent to `POST /api/v1/mac-calendar/memory` | the product stores every appointment as an `event` episode (`calendar_memory.py`, window 3 years back, 1 year ahead); the UID is the world ID. Appointments outside the window are counted as "outside the memory window" and reported as not arrived; the live calendar keeps its ±30 days / current year |
| Classification | `working_memory_worker.run` (real `interpret` and `WorkingMemoryStore.commit`) | without a model a constant provider labels every paragraph `fact`: retrieval is measured, classification quality is not |
| Retrieval | `Agent.answer_memory` with a candidate-capturing stand-in for the model | reads two private agent helpers (`_project_directory`, `_calendar_entries`); the model's own selection is missing by construction |
| Answer | `POST /api/v1/conversations/{id}/messages` (`answer_mode: auto`), a new conversation per question | model calls are not wrapped in the product's local-model verification |
| Clock | frozen at the world's cut-off date in every `icarus_memory` module (`uhr.py`) | `time.time()`/`time.monotonic()` stay real (retry waits, time budgets); one instance per process |

Environment variables: `ICARUS_*`, `KINGFISHER_*` and the provider key variables
are removed for the duration of a measurement and restored afterwards
(`umgebung.py`); credentials from the machine cannot reach the measurement
instance.

## Tests and sabotage probes

`python -m pytest messlatte/tests` covers the validator (broken worlds are
rejected with file and ID), the rating (many small cases: alternative groups,
forbidden statements beat everything, all six classes), ingest through the
product paths (episodes found again, retry after a server error, permanent
failures counted), retrieval (recall, rank), the answer stage end to end with a
scriptable model (`tests/skriptmodell.py`), the report (three numbers on top,
no percentages, cold and warm time separate, holdout separate), the CLI, and the
local mode against a `TestClient` app instead of real HTTP (the report must not
contain any answer text).

Sabotage probes, done when the rating and the ingest were written and reverted
afterwards:

* `bewertung.gefundene_verbotene` made to return `()` (forbidden statements never
  found): seven tests fail, among them the forbidden-statement cases of the
  rating, the end-to-end case in `test_antwort.py` (an outdated deadline in the
  context) and the privacy-safe counter in `test_lokal.py`.
* the folder `Sent` left out of the mail ingest in `aufnahme._mails`: ten tests
  fail (missing episodes, counters per source type, retry and failure counting,
  the meaning question, the model classification count).

Repeat such a probe after every new assertion: break it on purpose and check
that the right tests fail.

## What it does not measure

* Quality on the real mailbox. This is an invented world; for real data use `lokal`.
* An error probability. Zero observed errors are no proof of zero; every number
  carries its case count.
* The quality of the model's classification when run without a model, the
  quality of any cloud path, attachments, HTML mail, real provider behaviour,
  speed on the target Mac, actions (sending, calendar writes), the UI.
* Multi-turn conversations: each question stands alone in a new conversation.
