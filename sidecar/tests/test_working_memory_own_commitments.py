"""Own-promise questions must not present another sender's direct promise.

Frozen q08 source bodies and raw model outputs from the synthetic G run. The
selector/prose transport is scripted; stores, role metadata, Akten, source
checks and rendered fallback are the real product path.
"""
import copy
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import working_memory_answers as answers
from icarus_memory.akten import Akten
from icarus_memory.bezuege import Bezuege
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.frage import Anfrage
from icarus_memory.kontakte import fuer_mail
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_satzantwort import Skript

AT = datetime(2026, 10, 30, 14, tzinfo=timezone.utc)
OWN = 'Lea Hartmann <lea@beratung.example>'
OTHER = 'Nora Berger <nora@praxis.example>'
QUESTION = 'Bis wann habe ich Nora die Ceder-Kalkulation zugesagt?'
OWN_PROMISE = ('Ich werde dir die Kalkulation für Projekt Ceder bis zum '
               '3. November 2026 um 15:30 Uhr senden.')
OTHER_PROMISE = ('Ich werde dir die Unterlagen für Projekt Ceder bis zum 3. November 2026 senden. '
                 'Das ist meine Zusage, keine Bitte an dich.')
G_PROSE = {'status': 'antwort', 'saetze': [
    {'text': 'Du hast Nora die Ceder-Kalkulation bis zum 3. November 2026 um 15:30 Uhr zugesagt.',
     'belege': [2, 3]}]}


@pytest.fixture
def memory(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'claims.sqlite3')
    bezuege = Bezuege(episodes, eigene=lambda: ['lea@beratung.example'])
    akten = Akten(episodes, bezuege, claims=claims)
    episodes.akten_zugang = lambda: akten
    yield episodes, claims, akten
    claims.close()
    episodes.close()


def add(memory, text, *, own=False, kind='commitment', title='Unterlagen noch unterwegs', contacts=True,
        sender=None, source_type=SourceType.EMAIL):
    episodes, _, akten = memory
    sender = sender or (OWN if own else OTHER)
    recipient = OTHER if own else OWN
    metadata = fuer_mail(sender, [{'name': recipient.split(' <')[0],
                                  'adresse': recipient.split('<')[1][:-1], 'rolle': 'an'}],
                         eigene=['lea@beratung.example']) if contacts else []
    source, _ = episodes.record(
        EpisodeKind.MESSAGE, title, text, Provenance(source_type, source_ref='synthetic:' + title),
        occurred_at=AT - timedelta(days=1), participants=[sender], contacts=metadata)
    assert WorkingMemoryStore(episodes).commit(episodes.support_snapshot(source.id), [
        {'start': 0, 'end': len(text), 'kind': kind}], model='synthetic')
    akten.bezuege.aktualisieren()
    return source


def ask(memory, question=QUESTION, *, sentences=False, select=None):
    episodes, claims, _ = memory
    # G selected m11 and m10 (S2+S3). Preserve these sources independently of
    # candidate rank/UUID; the returned sentence is G's unchanged raw output.
    model = Skript(saetze=copy.deepcopy(G_PROSE), auswahl=select)
    answer = answers.prepare(question, episodes, claims, model, semantic_search=None,
                             saetze=sentences, anfrage=Anfrage(('Nora',), None, 'fakt', herkunft='modell'))
    return answer, answers.render(answer, episodes, claims), model


@pytest.mark.parametrize('sentences', [False, True])
def test_g_q08_other_direct_promise_cannot_survive_selection_or_quote_fallback(memory, sentences):
    episodes, claims, _ = memory
    own = add(memory, OWN_PROMISE, own=True, title='Projekt Ceder: meine Zusage')
    other = add(memory, OTHER_PROMISE)
    revision = claims.revision
    answer, (text, links, status), _ = ask(memory, sentences=sentences)
    assert status == 'working_reports'
    assert {ref['episode_id'] for ref in answer['refs']} == {own.id}
    assert {link['episode_id'] for link in links} == {own.id}
    if sentences:
        assert 'nicht verlässlich beantworten' in text
        assert episodes.get(links[0]['episode_id']).body == OWN_PROMISE
    else:
        assert OWN_PROMISE in text
    assert OTHER_PROMISE not in text
    # Exclusion is not attribution proof: raw G prose still cannot manufacture
    # 'du hast zugesagt' from an outgoing mail header.
    assert 'Du hast Nora' not in text
    assert claims.revision == revision
    assert episodes.get(other.id).body == OTHER_PROMISE
    assert episodes.get(own.id).body == OWN_PROMISE


def test_g_q08_other_promise_cannot_reenter_from_akten_sentence_evidence(memory):
    own = add(memory, OWN_PROMISE, own=True, title='Projekt Ceder: meine Zusage')
    add(memory, OTHER_PROMISE)
    # Even a corrected selector must not have the rejected other actor added
    # back by the Akte's deadlines/open-items block before prose generation.
    def select(data):
        return [row['id'] for row in data['sources'] if row['title'] == 'Projekt Ceder: meine Zusage']
    answer, (_, links, _), model = ask(memory, sentences=True, select=select)
    assert {ref['episode_id'] for ref in answer['refs']} == {own.id}
    assert {link['episode_id'] for link in links} == {own.id}
    assert all(OTHER_PROMISE not in beleg['text']
               for call in model.satzanfragen for beleg in call['belege'])


def test_legacy_saved_own_promise_answer_with_other_actor_is_unavailable(memory):
    episodes, claims, _ = memory
    own = add(memory, OWN_PROMISE, own=True, title='Projekt Ceder: meine Zusage')
    other = add(memory, OTHER_PROMISE)
    answer, _, _ = ask(memory)
    # A previously saved bad selection must fail the new re-opening guard,
    # even though original bytes and all source fingerprints are unchanged.
    legacy = copy.deepcopy(answer)
    legacy['refs'] = [ref for ref in legacy['basis'] if ref['episode_id'] in {own.id, other.id}]
    assert answers.render(legacy, episodes, claims)[2] == 'working_unavailable'


@pytest.mark.parametrize('question', [
    'Bis wann hat Nora die Unterlagen für Ceder zugesagt?',
    'Was haben Nora und ich für Ceder zugesagt?',
    'Vergleiche meine Zusage mit Noras Zusage für Ceder.',
    'Was hat nicht ich, sondern Nora für Ceder zugesagt?',
    'Was habe ich Nora für Ceder zugesagt? Was hat Nora mir für Ceder zugesagt?',
    'Welche Zusagen habe ich Nora für Ceder versprochen, welche stammen von Nora?',
    'Was habe ich Nora für Ceder zugesagt. Was hat Nora mir für Ceder zugesagt?',
    'Was habe ich Nora für Ceder zugesagt; was hat Nora mir für Ceder zugesagt?',
    'Was habe ich Nora für Ceder zugesagt\nWas hat Nora mir für Ceder zugesagt?',
    'Was habe ich Nora zugesagt was hat Nora mir zugesagt',
])
def test_other_actor_and_comparison_questions_keep_the_original(memory, question):
    other = add(memory, OTHER_PROMISE)
    answer, (text, links, status), _ = ask(memory, question)
    assert status == 'working_reports'
    assert {ref['episode_id'] for ref in answer['refs']} == {other.id}
    assert OTHER_PROMISE in text
    assert {link['episode_id'] for link in links} == {other.id}


@pytest.mark.parametrize('body', [
    'Lea hat die Ceder-Kalkulation bis zum 3. November zugesagt.',
    'Du hast mir die Ceder-Kalkulation bis zum 3. November zugesagt.',
    'Die Ceder-Kalkulation ist bis zum 3. November zugesagt.',
    'Ich werde dir die Unterlagen für Projekt Ceder senden. Du hast die Kalkulation zugesagt.',
    'Ich werde dir schreiben, dass du die Ceder-Kalkulation zugesagt hast.',
    'Ich werde die von Lea zugesagte Ceder-Kalkulation senden.',
    'Nora zitiert Lea: Ich werde dir die Ceder-Kalkulation senden.',
    'Weitergeleitete Nachricht\nIch werde dir die Ceder-Kalkulation senden.',
    '> Ich werde dir die Ceder-Kalkulation senden.',
    '„Ich werde dir die Ceder-Kalkulation senden.“',
    'Ich werde dir die Unterlagen für Ceder senden.\nVon: Lea\nIch werde die Kalkulation senden.',
])
def test_neutral_report_or_ambiguous_speaker_stays_visible(memory, body):
    source = add(memory, body)
    answer, (text, _, status), _ = ask(memory)
    assert status == 'working_reports'
    assert {ref['episode_id'] for ref in answer['refs']} == {source.id}
    assert body in text


@pytest.mark.parametrize('kwargs', [
    {'contacts': False},
    {'own': True},
    {'kind': 'status'},
    {'source_type': SourceType.DOCUMENT},
])
def test_unknown_sender_own_sender_non_commitment_or_document_is_not_pruned(memory, kwargs):
    source = add(memory, OWN_PROMISE, **kwargs)
    answer, (text, _, status), _ = ask(memory)
    assert status == 'working_reports'
    assert {ref['episode_id'] for ref in answer['refs']} == {source.id}
    assert OWN_PROMISE in text


def test_known_other_actor_alone_yields_unknown_without_promoting_own_promise(memory):
    add(memory, OTHER_PROMISE)
    answer, (text, links, status), _ = ask(memory)
    assert status == 'working_unknown'
    assert answer['refs'] == [] and not links
    assert OTHER_PROMISE not in text


def test_source_withdrawal_still_invalidates_filtered_own_promise(memory):
    episodes, claims, _ = memory
    own = add(memory, OWN_PROMISE, own=True, title='Projekt Ceder: meine Zusage')
    add(memory, OTHER_PROMISE)
    answer, _, _ = ask(memory)
    episodes.ignore(own.id)
    assert answers.render(answer, episodes, claims)[2] == 'working_unavailable'


@pytest.mark.parametrize('body', [
    'Ich werde Leas Zusage für die Ceder-Kalkulation bestätigen.',
    'Ich werde über die zugesagte Ceder-Kalkulation berichten.',
    "Ich werde dir 'Leas Zusage für Ceder' senden.",
    'Ich werde dir die Kalkulation, die Lea zusagt, senden.',
    'Ich werde dir Folgendes senden: Lea wird die Ceder-Kalkulation senden.',
])
def test_direct_future_about_another_promise_or_quote_is_not_pruned(memory, body):
    source = add(memory, body)
    answer, (text, _, status), _ = ask(memory)
    assert status == 'working_reports'
    assert {ref['episode_id'] for ref in answer['refs']} == {source.id}
    assert body in text


@pytest.mark.parametrize('title', ['Fwd: Kalkulation', 'WG: Kalkulation', 'Weitergeleitete Nachricht'])
def test_forwarding_subject_does_not_prove_the_body_speaker(memory, title):
    source = add(memory, OWN_PROMISE, title=title)
    answer, (text, _, status), _ = ask(memory)
    assert status == 'working_reports'
    assert {ref['episode_id'] for ref in answer['refs']} == {source.id}
    assert OWN_PROMISE in text


def test_other_actor_rule_is_not_tied_to_ceder_or_delivery_vocabulary(memory):
    body = 'Ich werde die Baupläne für Projekt Eichenhain bis Mittwoch prüfen.'
    add(memory, body)
    answer, (_, links, status), _ = ask(memory, 'Was habe ich Nora für Eichenhain versprochen?')
    assert status == 'working_unknown'
    assert not answer['refs'] and not links


def test_unreadable_saved_sentence_container_falls_back_without_crashing(memory):
    own = add(memory, OWN_PROMISE, own=True)
    answer, _, _ = ask(memory)
    answer['satzantwort'] = {'belege': None}
    text, links, status = answers.render(answer, memory[0], memory[1])
    assert status == 'working_reports' and OWN_PROMISE in text
    assert {link['episode_id'] for link in links} == {own.id}


def test_saved_additional_sentence_evidence_cannot_restore_foreign_promise(memory):
    episodes, claims, _ = memory
    add(memory, OWN_PROMISE, own=True, title='Projekt Ceder: meine Zusage')
    other = add(memory, OTHER_PROMISE)
    answer, _, _ = ask(memory)
    foreign_ref = next(ref for ref in answer['basis'] if ref['episode_id'] == other.id)
    answer['satzantwort'] = {'belege': [{'ref': foreign_ref}]}
    assert answers.render(answer, episodes, claims)[2] == 'working_unavailable'


def test_changing_source_roles_invalidates_old_selection(memory):
    episodes, claims, _ = memory
    own = add(memory, OWN_PROMISE, own=True)
    answer, _, _ = ask(memory)
    episodes.add_contacts(own.id, [
        {'adresse': 'unknown@example.test', 'name': 'Ungeklärt', 'rolle': 'von', 'ich': False}], [])
    assert answers.render(answer, episodes, claims)[2] == 'working_unavailable'
    assert episodes.get(own.id).body == OWN_PROMISE
