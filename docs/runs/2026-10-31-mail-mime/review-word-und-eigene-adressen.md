# Independent review: mail DOCX integration and own Gmail spelling

Reviewed checkout: `/private/tmp/kf-skill-categories-20261031`, branch `fix/mail-attachment-wire-20261031`.
Base and HEAD at inspection: `ef8e02cf313a16f56810552b1500b01e8075301d` (`official1.0.36`); reviewed changes were in the working tree.

## Verdict and frozen count

**One important integration finding (F1), now independently retested CLOSED; no open important/critical findings in this review. The substantive finding count stays frozen at 1.** F1 was an existing attachment actor-boundary gap which the new DOCX path also reached. The original evidence below is historical; the narrow repair and exact counterexample retest are recorded immediately below. This is not evidence that a real model made the error: a deliberately positive, saved synthetic judge response proved that the deterministic path allowed automatic task creation without attachment authorship evidence.

The bounded DOCX dispatcher and own Gmail comparison passed the focused tests below. The reviewer did not change source files, repository tests, Git refs, runtime data, providers, credentials, Docker state, or personal data. This report is the only requested artifact. Network and real models were not used.

## Narrow repair retest — F1 CLOSED

The implementer limited the production F1 repair to `task_detection.py` and `aufgaben_von_selbst.py`:

- `TaskDetector` now sets `own_source` only for `EpisodeKind.MESSAGE` (`task_detection.py:154-160`). An attachment keeps its transport contacts, but these no longer supply document authorship.
- `person_der_quelle` returns `(None, None)` for non-message sources (`aufgaben_von_selbst.py:134-136`).
- Automatic `pruefen` refuses non-message sources before considering any positive judge/review marker (`aufgaben_von_selbst.py:216-218`).

I extracted and executed the exact original F1 script from this report, without changing its synthetic input or saved judge response. The repaired result was:

```text
docx detector DetectionReport(analyzed=1, proposed=0, failed=0, superseded=0, available=True, cancelled=False) candidates 0
pdf detector DetectionReport(analyzed=1, proposed=0, failed=0, superseded=0, available=True, cancelled=False) candidates 0
```

An additional independent positive control stored an actual `EpisodeKind.MESSAGE` mail with `body='Ich werde dir die Kalkulation senden.'`, the dotted own Gmail sender, and Nora under `An`. The same positive own-commitment judge still produced a proposal and an actual automatic task.

For both DOCX and PDF, I also repeated the attachment test with an incorrect positive `request_to_recipient` judge. The candidate remains pending for manual handling, has no actor/person inferred by `person_der_quelle`, and cannot create an automatic task even though it has the positive `/task-review-v1` marker:

```text
actual-mail proposed 1 verdict angelegt automatic 1 original_and_roles_unchanged True
docx-request proposed 1 verdict keine_mail automatic 0 original_and_roles_unchanged True
pdf-request proposed 1 verdict keine_mail automatic 0 original_and_roles_unchanged True
```

Before/after checks covered source body, digest, title, occurred/recorded times, provenance, contacts, participants and tags. All were identical. Attachment transport roles still equal the parent's roles, the parent's `ich=True` transport flag remains, `mail-parent:<parent-id>` remains, literal document text remains, and the child still has current support. The repair changes interpretation/automation rather than erasing source evidence. The manual request candidate intentionally still exists; this is not a claim that its judge result establishes responsibility.

Independent repair-focused pytest rerun:

```text
pytest -q -p no:cacheprovider sidecar/tests/test_attachment_task_authorship.py sidecar/tests/test_own_gmail_spelling.py sidecar/tests/test_aufgaben_von_selbst.py sidecar/tests/test_own_promise_retention.py
89 passed, 1 warning in 5.95s
```

The warning is the same existing Starlette/httpx test-client deprecation. The four new DOCX/PDF authorship cases pass; reviewed production diff is limited to the stated guards. Scoped `git diff --check` passed. No new broad audit or full backend/Mac/private-source test was performed. Finding count remains 1, closed count 1, open count 0.

Retested repair SHA-256:

```text
0ba7fccee478ae851dc001bf10882975fa7c4625f85d83911963ed9041fdd03a  sidecar/icarus_memory/task_detection.py
a354b98da21ff017588e74c3925c7367630291384ba92f85e39bd80851ee40cb  sidecar/icarus_memory/aufgaben_von_selbst.py
fd6a3407e265197d71276a6ec4f631bf2f3975d287ad6d7ae09f16e6144d4686  sidecar/icarus_memory/kontakte.py
483e536c2d2a9def3f6e9d619cac53828b39ac847fbbecc2f42ba9645b843934  sidecar/tests/test_attachment_task_authorship.py
```

The Gmail helper docstring was also clarified to state that existing parser normalization remains and arbitrary SMTPUTF8 addresses are not validated. The earlier non-blocking Unicode observation below remains a precise behavior note, not a new important finding or a claimed collision of valid Gmail users.

## Original F1 evidence — An attachment's inherited mail sender could become its alleged author and an automatic own commitment

Severity: important; concrete automatic behavior, reproduced for both new DOCX and existing PDF attachments.

`anhaenge.aufnehmen` stores the child as `EpisodeKind.DOCUMENT`, `SourceType.EMAIL`, and copies the parent mail's contacts unchanged (`anhaenge.py:337-343`). These are transport participants, not proof of who wrote the attached document.

The positive task path ignores that distinction:

1. `task_detection.py:154-157` derives `own_source=True` only from the inherited sender's `ich` flag.
2. `task_review.py:221-224` accepts a positive `own_commitment` judge verdict with that flag. The separate `_direct_own_delivery` fallback correctly checks `kind == 'message'`, but the positive verdict does not go through that fallback.
3. `aufgaben_von_selbst.py:215-245` checks `SourceType.EMAIL` and inherited recipients, not `EpisodeKind.MESSAGE`. A document therefore qualifies as a new own mail promise.

Synthetic original:

- Current dated mail from `Lea <lea.hartmann@gmail.com>`, configured own address `leahartmann@gmail.com`, recipient Nora under `An`.
- Parent subject: `Fremder Entwurf zur Prüfung`.
- Parent body: `Anbei ein fremder Entwurf zur Prüfung, keine eigene Zusage.`
- Attachment `Fremder-Entwurf.docx`, parsed through the real existing DOCX reader, containing only `Ich werde dir die Kalkulation senden.`
- Saved extractor returns that exact quote/title; saved semantic judge returns `own_commitment`, `title_supported=True`.

Observed end to end:

```text
docx detector DetectionReport(analyzed=1, proposed=1, failed=0, superseded=0, available=True, cancelled=False) candidates 1
docx deterministic_verdict Urteil(eindeutig=True, kuerzel='angelegt', satz='Deine Zusage an Nora, aus einer neuen Mail.', richtung='zusage', person={'adresse': 'nora@example.invalid', 'name': 'Nora'})
docx auto_result {'geprueft': 1, 'angelegt': 1, 'vorschlaege': 0} tasks 1
pdf detector DetectionReport(analyzed=1, proposed=1, failed=0, superseded=0, available=True, cancelled=False) candidates 1
pdf deterministic_verdict Urteil(eindeutig=True, kuerzel='angelegt', satz='Deine Zusage an Nora, aus einer neuen Mail.', richtung='zusage', person={'adresse': 'nora@example.invalid', 'name': 'Nora'})
pdf auto_result {'geprueft': 1, 'angelegt': 1, 'vorschlaege': 0} tasks 1
```

The PDF control uses an in-memory already-read PDF `Anhang` with exactly the same text; no external PDF parser/model was involved in this particular actor test. The DOCX case uses `aus_mail` plus a synthetic OOXML archive.

Minimal reproduction command, run from the checkout with the existing synthetic helpers:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:. /private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python - <<'PY'
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from icarus_memory import anhaenge
from icarus_memory.aufgaben_von_selbst import Durchlauf, pruefen
from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_ingestion import remember
from icarus_memory.proposals import ProposalStore, ProposalKind
from icarus_memory.task_detection import TaskDetector
from icarus_memory.tasks import TaskStore
from tests.test_mail_docx_attachments import word, message, DOCX_MIME
from tests.test_own_promise_retention import SavedReplies
quote = 'Ich werde dir die Kalkulation senden.'
now = datetime.now(timezone.utc)
for kind in ('docx', 'pdf'):
    with TemporaryDirectory(prefix='kf-attachment-actor-review-') as folder:
        folder = Path(folder)
        episodes = EpisodeStore(folder/'episodes.sqlite3')
        proposals = ProposalStore(folder/'proposals.sqlite3')
        tasks = TaskStore(folder/'tasks.sqlite3')
        try:
            if kind == 'docx':
                attachment, = anhaenge.aus_mail(message(('Fremder-Entwurf.docx', word(text=quote), DOCX_MIME)))
            else:
                attachment = anhaenge.Anhang('Fremder-Entwurf.pdf', 'pdf', anhaenge.GELESEN, (quote,), 1)
            item = Message(uid='a:7.1', subject='Fremder Entwurf zur Prüfung',
                sender='Lea <lea.hartmann@gmail.com>', date=now, preview='', unread=False,
                body='Anbei ein fremder Entwurf zur Prüfung, keine eigene Zusage.', account_id='a',
                message_id='<actor-probe@example.invalid>', own_addresses=('leahartmann@gmail.com',),
                recipients=({'name':'Nora','adresse':'nora@example.invalid','rolle':'an'},), anhaenge=(attachment,))
            child_id, = remember(episodes, item)['anhaenge']
            provider = SavedReplies({'title':quote,'quote':quote}, kind='own_commitment', supported=True)
            report = TaskDetector(episodes, proposals, provider, RLock()).run(
                with_model=True, quellenfilter=lambda e: e.id == child_id)
            candidates = proposals.pending(ProposalKind.TASK)
            print(kind, 'detector', report, 'candidates', len(candidates))
            if candidates:
                print(kind, 'deterministic_verdict', pruefen(candidates[0], episodes.get(child_id),
                    eigene=['leahartmann@gmail.com'], jetzt=now, zeitstatus='recent',
                    aus_bestand=False, dublette=False, zurueckgenommen=False))
                runner = Durchlauf(tasks, episodes, proposals,
                    eigene=lambda:['leahartmann@gmail.com'], jetzt=lambda:now)
                print(kind, 'auto_result', runner.schritt(), 'tasks', len(tasks.open_tasks(limit=None)))
        finally:
            tasks.close(); proposals.close(); episodes.close()
PY
```

Expected repair boundary: preserve attachment text and parent/source links, but do not infer attachment authorship or allow automatic own mail commitments from copied transport contacts. This report does not implement a fix or widen the audit to unrelated automatic paths.

## Verified behavior in the two requested domains

DOCX:

- Dispatcher uses unchanged `document_text.docx_text`; no new OOXML parser.
- Literal paragraphs, table cell text, tabs, line breaks and inserted changes are retained. Deleted/moved-from text is excluded by the existing reader.
- Separate `haupttext` with empty `seiten`; report `seiten`/`gesamt` are null, `textumfang='Word-Haupttext'`. A literal `Seite 7` in the original does not invent pagination.
- Allowed DOCX name/MIME combinations and conflicting old/macro/template/image formats are covered.
- Existing 5 MiB file, 2 MiB main XML and 512 KiB UTF-8 text limits are exercised. Attachment source payload has a 60,000 character budget including the `Word-Haupttext` marker; over-budget text is explicitly partial. Five attachment maximum, duplicate suppression and unnamed attachment uncertainty are exercised.
- Empty, corrupt, encrypted, duplicate-main-part and unsupported XML result in an explicit unread/error source, never OCR waiting.
- Tests cover source versions, incomplete refresh preservation, complete removal, original retention and withdrawal through parent permission.
- Independent additional OOXML probe retained `A\tB\nCINSERTED` literally, excluded deleted text plus separate footer/footnote sentinels, and returned no page attribution.
- PDF/image regression tests pass; their report and source shapes remain unchanged in the inspected diff.

Own Gmail:

- ASCII private `gmail.com` dot spellings identify the configured own mailbox; custom/work domains, other domains, distinct usernames, plus aliases, leading/trailing/repeated dots are not expanded by the new rule.
- Stored address strings and foreign Gmail person anchors remain literal. Task/deadline direction consumers reuse the helper.
- Complete reread of unchanged source promotes the derived `ich` flag through explicit `promote_self`; test confirms unchanged source ID, body, digest, title, occurred/recorded times and provenance, changed analysis context, then idempotent repeated reread.
- Incomplete refresh cannot promote an existing contact. Independent probes also checked an incomplete attachment report, ignored source, and `add_contacts` without opt-in.
- Read-only old person projection follows the configured own address without rewriting the old record.
- Scope precision: the independent incomplete-report probe changed the task context because a new attachment coverage report was stored; the `ich` flag stayed false. No claim that every incomplete refresh is a metadata no-op.

Non-blocking guard detail, not another critical/important finding: the helper calls existing `mail_address.casefold` before checking ASCII syntax. Thus `lea.ſmith@gmail.com` becomes `leasmith@gmail.com`, and `lea.Keller@gmail.com` becomes `leakeller@gmail.com`. These are not valid private Gmail usernames. Root was told the exact counterexample and clarified the helper's docstring during repair; it now explicitly preserves existing parser normalization without claiming arbitrary SMTPUTF8 validation. No genuine foreign valid Gmail mailbox collision was established.

## Test evidence

Environment: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=sidecar:.`; interpreter `/private/tmp/kf-person-context-20261030-4cjo275h/env/bin/python`; pytest cache disabled.

```text
pytest -q -p no:cacheprovider sidecar/tests/test_mail_docx_attachments.py sidecar/tests/test_own_gmail_spelling.py
50 passed in 1.13s

pytest -q -p no:cacheprovider sidecar/tests/test_anhaenge.py sidecar/tests/test_attachment_coverage.py sidecar/tests/test_attachment_lifecycle.py sidecar/tests/test_mail_ingestion.py sidecar/tests/test_kontakte_identitaet.py sidecar/tests/test_identitaet_graph.py sidecar/tests/test_aufgaben_von_selbst.py sidecar/tests/test_fristlage.py sidecar/tests/test_own_promise_retention.py
147 passed, 1 warning in 17.53s
```

The warning was the existing Starlette/httpx test-client deprecation. Scoped `git diff --check ef8e02c` passed. These 197 passing tests do not cover F1; the independent actor counterprobe above does.

## Initial review snapshot and limits

SHA-256 at reviewed snapshot:

```text
50c1e223da0ba415e6223b06fe467b2fc4b945f5ff09aadf709305575d554a92  sidecar/icarus_memory/anhaenge.py
635cea07763ec679033c445c5cb9d35ad0bbce9595952602681f5b14943ae23b  sidecar/tests/test_mail_docx_attachments.py
1ea0d4c895d232702da2bb5e7fcd82c519ee83c7a3867eea3dc60630f4b8c161  sidecar/icarus_memory/kontakte.py
d5617c397de6aa834baf52e8d4bfd74acae5e208eaea62591b04763b9f5cca7a  sidecar/icarus_memory/identitaet.py
bf5aac810be1025ef07ce8fba8ab5804ffe04420f651de361ca798a2df71cb8a  sidecar/icarus_memory/mail_intake.py
2419322061137b6e25c1f88ac3cf1c3b007fb1a4de440b5fbf1c09bfe2c20033  sidecar/icarus_memory/mail_ingestion.py
2ca5b60275eb3bd5700cbd8765ab6611bd3f74a739689e634caf1250ec46562b  sidecar/icarus_memory/episodes.py
6ae28c1e007eeb8d369a5eebf5b8b593cd1c315b09cf3310bea60ebe546470aa  sidecar/icarus_memory/aufgaben_von_selbst.py
4ac72c3ab87cc45bc8669612a86bc13cfb7684c9671ebb4844e83fed6928a46e  sidecar/icarus_memory/fristlage.py
823c758442525b7c29ec55ffb208437a54df1faa35cabfe98b0a386c2b007408  sidecar/tests/test_own_gmail_spelling.py
```

No full backend run, actual Mac application, private mailbox/runtime probe, deployed artifact, real judge behavior, provider/network call or acceptance claim is included. Connector MIME changes were outside the assigned review; new tests exercise their synthetic integration but this is not an independent connector audit. The existing DOCX reader was inspected only as the reused bounded dependency and left unchanged. Google's rule was supplied as confirmed scope; it was not re-researched over the network in this read-only local review.
