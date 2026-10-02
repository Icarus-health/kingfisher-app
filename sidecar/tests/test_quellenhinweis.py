"""Der Quellenhinweis der belegten Gedächtnisantwort: Alltagssprache im Text, Kennungen als Datenfeld.

Vorher stand im Gespräch `Quelle [1]: Gespräch · "conversation:c-…:message:m-…"` und
`Ereigniszeit: 2026-10-01T10:25:07.79…+00:00`. Jetzt „Gespräch vom 1. Oktober 2026, 12:25 Uhr“,
in der Zeitzone des Nutzers; womit die Oberfläche die Quelle öffnet, steht in `context.quellen`.
"""
import json
import re
from types import SimpleNamespace

import pytest

from icarus_memory import quellenhinweis
from icarus_memory.datumstext import tag_text, zeitpunkt_text
from icarus_memory.evidence_answer import EvidenceAnswer
from icarus_memory.knowledge_render import signature
from icarus_memory.providers import Reply
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_evidence_answer import item
from tests.test_memory_clarification import api, conversation, post  # noqa: F401 - Fixture

#: Was nie im sichtbaren Text stehen darf: ISO-Zeiten, Kennungen von Quellen, Gesprächen, Claims.
ROH = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}|conversation:|:message:|claim:|episode:|mail:|e-[0-9a-f]{8}')


def zeile(art='email', *, ref='mail:one', occurred_at=None, recorded_at='2026-10-01T10:25:07.790000+00:00'):
    row = item(source_ref=ref, occurred_at=occurred_at)
    row['knowledge_projection']['primary_evidence'].update(source_type=art, recorded_at=recorded_at)
    row['source_type'] = art
    row['knowledge_input'] = signature(row['knowledge_projection'], {'episode:one': 0})
    return row


def test_zeiten_in_der_zeitzone_des_nutzers(monkeypatch):
    monkeypatch.delenv('KINGFISHER_TIMEZONE', raising=False)
    assert zeitpunkt_text('2026-10-01T10:25:07.790000+00:00') == '1. Oktober 2026, 12:25 Uhr'
    assert zeitpunkt_text('2026-09-30T22:00:00+00:00') == '1. Oktober 2026'
    assert tag_text('2026-09-30T22:30:00Z') == '1. Oktober 2026'
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'America/New_York')
    assert zeitpunkt_text('2026-10-01T10:25:07.790000+00:00') == '1. Oktober 2026, 06:25 Uhr'
    assert zeitpunkt_text('kein Datum') == '' and zeitpunkt_text(None) == ''


def test_gespraech_heisst_gespraech_vom_mit_der_nachricht_als_datenfeld():
    ref = 'conversation:c-1a2b:message:m-9f8e'
    envelope = EvidenceAnswer([zeile('chat', ref=ref, occurred_at='2026-10-01T10:25:07.790000+00:00')])
    text = envelope.render_readable('evidence', ['E1'])
    assert 'Quelle [1]: Gespräch vom 1. Oktober 2026, 12:25 Uhr' in text
    assert not ROH.search(text), text
    quelle, = envelope.quellen('evidence', ['E1'])
    assert quelle['conversation_id'] == 'c-1a2b' and quelle['message_id'] == 'm-9f8e'
    assert quelle['source_ref'] == ref and quelle['assertion_id'] == 'claim:one'
    assert quelle['text'] == 'Gespräch vom 1. Oktober 2026, 12:25 Uhr'


def test_mail_mit_betreff_und_absender_termin_mit_titel_und_tag():
    mail = SimpleNamespace(title='Angebot\nProjekt Atlas', participants=['Lena Probe <lena.probe@example.org>'],
                           contacts=[{'name': '', 'adresse': 'lena.probe@example.org', 'rolle': 'von'}],
                           provenance=SimpleNamespace(source_type=SimpleNamespace(value='email')))
    assert quellenhinweis.angaben(mail) == {'titel': 'Angebot Projekt Atlas', 'absender': 'lena.probe@example.org'}
    mail.contacts = []
    assert quellenhinweis.angaben(mail)['absender'] == 'Lena Probe'
    beleg = {'source_type': 'email', 'occurred_at': '2026-09-29T07:00:00+00:00', 'recorded_at': '2026-09-29T08:00:00+00:00'}
    assert quellenhinweis.text(beleg, quellenhinweis.angaben(mail)) == \
        'E-Mail „Angebot Projekt Atlas“ von Lena Probe vom 29. September 2026, 09:00 Uhr'
    termin = {'source_type': 'calendar', 'occurred_at': '2026-10-02T08:30:00+00:00', 'recorded_at': '2026-09-29T08:00:00+00:00'}
    assert quellenhinweis.text(termin, {'titel': 'Abstimmung Atlas'}) == 'Termin „Abstimmung Atlas“ am 2. Oktober 2026, 10:30 Uhr'
    ohne_zeit = {'source_type': 'document', 'occurred_at': None, 'recorded_at': '2026-09-29T08:00:00+00:00'}
    assert quellenhinweis.text(ohne_zeit, {'titel': 'Protokoll'}) == 'Dokument „Protokoll“, aufgenommen am 29. September 2026, 10:00 Uhr'
    # Ein Gesprächsausschnitt heißt nur so; der Titel sagt nichts und entfällt.
    chat = SimpleNamespace(title='Gesprächsausschnitt', participants=[], contacts=[],
                           provenance=SimpleNamespace(source_type=SimpleNamespace(value='chat')))
    assert quellenhinweis.angaben(chat) == {'titel': '', 'absender': ''}


@pytest.mark.parametrize('art', ['email', 'chat', 'calendar', 'document', 'user_stated', 'web', 'inference'])
@pytest.mark.parametrize('kind,ids', [('evidence', ['E1']), ('clarify', []), ('fallback', [])])
def test_kein_antwortweg_zeigt_rohkennungen_oder_iso_zeiten(art, kind, ids):
    envelope = EvidenceAnswer([zeile(art, ref='conversation:c-1:message:m-1' if art == 'chat' else 'mail:one',
                                     occurred_at='2026-10-01T10:25:07+00:00')])
    text = envelope.render_readable(kind, ids, angaben={'episode:one': {'titel': 'Titel', 'absender': 'Lena Probe'}})
    assert not ROH.search(text), text
    assert [q['nummer'] for q in envelope.quellen(kind, ids)] == [1]


def test_belegte_antwort_im_gespraech_zeigt_den_hinweis_und_fuehrt_zur_nachricht(core, api, monkeypatch):
    agent, provider, *_ = core
    app, client = api
    cid = conversation(client)
    gesendet = client.post(f'/api/v1/conversations/{cid}/messages',
                           json={'message': 'Dr. Kranz leitet Projekt Atlas.'}).json()
    quelle_id = gesendet['messages'][0]['id']
    karte = client.post(f'/api/v1/conversations/{cid}/memory-candidates', json={
        'source_message_id': quelle_id, 'subject_ref': 'person:kranz', 'predicate': 'leads',
        'value': 'Projekt Atlas', 'statement': 'Dr. Kranz leitet Projekt Atlas.'}).json()
    vorschlag = karte['memory_candidates'][-1]['candidate']['id']
    assert client.post(f'/api/v1/conversations/{cid}/memory-candidates/{vorschlag}/accept',
                       json={'replace_conflicts': False}).status_code == 200
    monkeypatch.setattr(provider, 'complete', lambda messages, tools: Reply(
        text=json.dumps({'version': 1, 'kind': 'evidence', 'evidence_ids': ['E1']})))
    antwort = post(client, cid, 'Wer leitet Projekt Atlas?')
    kontext = antwort['metadata']['context']
    assert kontext['answer_contract']['status'] == 'evidence'
    assert re.search(r'Quelle \[1\]: Gespräch vom \d{1,2}\. \w+ \d{4}, \d{2}:\d{2} Uhr', antwort['content'])
    assert not ROH.search(antwort['content']), antwort['content']
    quelle, = kontext['quellen']
    assert (quelle['conversation_id'], quelle['message_id']) == (cid, quelle_id)
    assert quelle['assertion_id'] == kontext['answer_contract']['selected_assertion_ids'][0]
    # Beim Wiederöffnen bleibt das Datenfeld, mit dem die Oberfläche die Quelle anspringt.
    wieder = client.get(f'/api/v1/conversations/{cid}').json()['messages'][-1]
    assert wieder['metadata']['context']['quellen'] == kontext['quellen']
