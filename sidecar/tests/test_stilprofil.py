"""Stilprofil aus eigenen gesendeten Mails (Paket B5, Oktober 2026): Ton je Person und je Kreis.

Eigene gesendete Mails (Kontakt `von` mit `ich`, einziger Empfänger) sind die beste Quelle für den eigenen Ton. Aus
ihnen entsteht ein **Vorschlag** mit Belegen; erst der Klick macht ihn zur Regel. Nur Einstimmigkeit zählt; Mails an
mehrere Empfänger nicht; zitierter Verlauf wird abgeschnitten. Dazu Regeln `gruss`, `anrede_form`, `sprache` und der
Scope „Kreis“ aus bestätigten Kreisen. Alle Daten synthetisch (Lena Probe, Lea Muster, Max Beispiel).
"""
from __future__ import annotations

import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType

ICH = 'lena.probe@example.org'
LEA = 'lea@example.org'
MAX = 'max@example.org'
URL = '/api/v1/messages/a%3A1/style'
KREIS_URL = '/api/v1/stil/kreis'
START = datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)

DU_MAILS = ['Hallo Lea,\n\nkannst du mir bis Montag Bescheid geben?\n\nViele Grüße\nLena',
            'Hallo Lea,\n\ndanke dir, das passt gut.\n\nViele Grüße\nLena',
            'Hallo Lea,\n\nich bringe dir die Unterlagen morgen mit.\n\nViele Grüße\nLena']
DU_REGELN = {'address': 'du', 'length': 'short', 'emoji': 'no', 'gruss': 'Viele Grüße', 'anrede_form': 'vorname',
             'sprache': 'de'}


def client(tmp_path):
    from icarus_memory.mail_style import register_mail_style
    app = FastAPI()
    app.state.conversation_lock = threading.RLock()
    app.state.store = SelfModelStore(MemoryBackend(), subject_id='test')
    app.state.episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')

    class Mail:
        item = Message('a:1', 'Frage', f'Lea Muster <{LEA}>', None, 'Frage', True, account_id='a', reply_to=LEA)

        def message(self, uid):
            return replace(self.item, uid=uid)

    app.state.mail = Mail()

    def auth(token: str | None = Header(None, alias='X-Icarus-Token')):
        if token != 'ok':
            raise HTTPException(401)

    register_mail_style(app, [Depends(auth)])
    return app, TestClient(app, headers={'X-Icarus-Token': 'ok'})


_laufende = [0]


def gesendet(app, text, *, an=LEA, konto='a', weitere=(), minuten=None, ich=True, betreff='Rückmeldung'):
    """Eine eigene gesendete Mail im Bestand, wie die Aufnahme sie anlegt (Kontakte mit Rolle, Quellenschlüssel, Kopf)."""
    _laufende[0] += 1
    nummer = _laufende[0]
    contacts = [{'name': 'Lena Probe', 'adresse': ICH, 'rolle': 'von', 'ich': ich},
                {'name': '', 'adresse': an, 'rolle': 'an', 'ich': False}]
    contacts += [{'name': '', 'adresse': a, 'rolle': 'cc', 'ich': a == ICH} for a in weitere]
    zeit = START + timedelta(minutes=nummer if minuten is None else minuten)
    key = f'mail:{konto}:{nummer}'
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, betreff, text,
        Provenance(source_type=SourceType.EMAIL, source_ref=f'{konto}:<m{nummer}@example.org>', captured_at=zeit),
        occurred_at=zeit, participants=[f'Lena Probe <{ICH}>', an], contacts=contacts, source_key=key)
    app.state.episodes.advance_source_head(key, app.state.episodes.source_head(key), episode.id)
    return episode


def empfangen(app, text, *, von=LEA, konto='a'):
    """Eine Mail der anderen Seite: zählt nie als eigener Ton."""
    _laufende[0] += 1
    nummer = _laufende[0]
    contacts = [{'name': '', 'adresse': von, 'rolle': 'von', 'ich': False},
                {'name': 'Lena Probe', 'adresse': ICH, 'rolle': 'an', 'ich': True}]
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Frage', text,
        Provenance(source_type=SourceType.EMAIL, source_ref=f'{konto}:<e{nummer}@example.org>'),
        occurred_at=START + timedelta(minutes=nummer), participants=[von], contacts=contacts)
    return episode


def kreis_festlegen(app, adresse, kreis):
    with app.state.episodes.transaction():
        app.state.episodes._conn.execute(
            'INSERT INTO personen_kreis VALUES (?,?,?,?) ON CONFLICT(sache) DO UPDATE SET kreis=excluded.kreis',
            (f'person:a:{adresse}', kreis, kreis, time.time()))


def wirksam(app, adresse=LEA, konto='a'):
    from icarus_memory.mail_style import effective_style
    return effective_style(app, replace(app.state.mail.item, reply_to=adresse, account_id=konto))


# -- Vorschlag je Person ------------------------------------------------------------------------------------------------

def test_vorschlag_aus_drei_gesendeten_mails_mit_belegen_und_bestaetigung(tmp_path):
    app, c = client(tmp_path)
    ids = [gesendet(app, t).id for t in DU_MAILS]
    empfangen(app, 'Sehr geehrte Frau Probe, mit freundlichen Grüßen')  # ihre Mail zählt nicht
    stand = c.get(URL).json()
    vorschlag = stand['proposal']
    assert vorschlag is not None, stand
    assert vorschlag['rules'] == DU_REGELN
    assert vorschlag['gesendet'] == 3 and vorschlag['belege'] == 0
    assert sorted(vorschlag['evidence_ids']) == sorted(ids)
    # Die Belege sind die gesendeten Mails: Kennung, Betreff, Zeit, eigener Text.
    assert [b['id'] for b in stand['gesendete']] == ids[::-1]
    assert all(b['title'] == 'Rückmeldung' and b['occurred_at'] and 'Viele Grüße' in b['text'] for b in stand['gesendete'])
    assert wirksam(app) == {}, 'ein Vorschlag wirkt nirgends'
    assert c.put(URL, json={'scope': 'contact', **vorschlag}).status_code == 200
    assert wirksam(app) == DU_REGELN
    assert c.get(URL).json()['profiles']['contact']['evidence_ids'] == vorschlag['evidence_ids']


def test_zwei_gesendete_reichen_nicht_und_belege_ergaenzen(tmp_path):
    app, c = client(tmp_path)
    for t in DU_MAILS[:2]:
        gesendet(app, t)
    assert c.get(URL).json()['proposal'] is None
    c.post(URL + '/examples', json={'text': 'Hallo Lea,\n\nbis gleich, ich freue mich auf dich.\n\nViele Grüße\nLena',
                                     'own_text_confirmed': True})
    vorschlag = c.get(URL).json()['proposal']
    assert vorschlag and vorschlag['gesendet'] == 2 and vorschlag['belege'] == 1 and len(vorschlag['evidence_ids']) == 3
    assert vorschlag['rules']['address'] == 'du' and vorschlag['rules']['gruss'] == 'Viele Grüße'


def test_gemischt_du_sie_ergibt_keine_anrede_andere_regeln_bleiben(tmp_path):
    app, c = client(tmp_path)
    gesendet(app, 'Hallo Lea,\n\nkönnen Sie mir Bescheid geben?\n\nViele Grüße\nLena')
    for t in DU_MAILS[1:]:
        gesendet(app, t)
    regeln = c.get(URL).json()['proposal']['rules']
    assert regeln['address'] == 'default'
    assert regeln['gruss'] == 'Viele Grüße' and regeln['length'] == 'short' and regeln['sprache'] == 'de'


def test_mehrfachempfaenger_und_fremde_konten_zaehlen_nicht(tmp_path):
    app, c = client(tmp_path)
    gesendet(app, DU_MAILS[0])
    gesendet(app, DU_MAILS[1], weitere=(MAX,))                 # An Lea, Cc Max: kein Beleg für Lea allein
    gesendet(app, DU_MAILS[2], konto='b')                       # anderes Konto
    gesendet(app, 'Hallo Lea,\n\nbis morgen dann.\n\nViele Grüße\nLena', ich=False)  # Absender nicht als „ich“ bekannt
    gesendet(app, 'Hallo Max,\n\ndanke dir.\n\nViele Grüße\nLena', an=MAX)
    stand = c.get(URL).json()
    assert stand['proposal'] is None and len(stand['gesendete']) == 1
    # Die eigene Adresse im Cc macht aus einer Mail an Lea keine Mehrfachmail.
    gesendet(app, DU_MAILS[1], weitere=(ICH,))
    gesendet(app, DU_MAILS[2], weitere=(ICH,))
    assert c.get(URL).json()['proposal']['gesendet'] == 3


def test_zitierter_verlauf_wird_abgeschnitten(tmp_path):
    app, c = client(tmp_path)
    fremd = '\n\nAm 30.09.2026 um 10:00 schrieb Lea Muster:\n> Sehr geehrte Frau Probe,\n> könnten Sie mir helfen?\n> Mit freundlichen Grüßen\n> Lea Muster 🙂'
    for t in DU_MAILS:
        gesendet(app, t + fremd)
    stand = c.get(URL).json()
    assert stand['proposal']['rules'] == DU_REGELN, 'Fremdtext darf nicht in die Regel'
    assert all('Sehr geehrte' not in b['text'] for b in stand['gesendete'])


def test_gruss_woertlich_sprache_englisch_und_nachname_mit_titel(tmp_path):
    app, c = client(tmp_path)
    for t in ['Hi Lea,\n\ncould you send me the file by Monday?\n\nBest regards\nLena',
              'Hi Lea,\n\nthanks, that works for me.\n\nBest regards\nLena',
              'Hi Lea,\n\nI will bring the documents tomorrow.\n\nBest regards\nLena']:
        gesendet(app, t)
    regeln = c.get(URL).json()['proposal']['rules']
    assert regeln['sprache'] == 'en' and regeln['gruss'] == 'Best regards' and regeln['anrede_form'] == 'vorname'
    app.state.mail.item = replace(app.state.mail.item, reply_to=MAX)
    for t in ['Sehr geehrter Herr Dr. Beispiel,\n\nkönnten Sie mir den Bericht schicken?\n\nMit freundlichen Grüßen\nLena Probe',
              'Sehr geehrter Herr Dr. Beispiel,\n\nvielen Dank für Ihre Nachricht.\n\nMit freundlichen Grüßen\nLena Probe',
              'Sehr geehrter Herr Dr. Beispiel,\n\nanbei die Unterlagen, wie besprochen.\n\nMit freundlichen Grüßen\nLena Probe']:
        gesendet(app, t, an=MAX)
    regeln = c.get(URL).json()['proposal']['rules']
    assert regeln == {'address': 'sie', 'length': 'short', 'emoji': 'no', 'gruss': 'Mit freundlichen Grüßen',
                      'anrede_form': 'nachname', 'sprache': 'de'}


def test_unterschiedliche_gruesse_ergeben_keine_grussregel(tmp_path):
    app, c = client(tmp_path)
    gesendet(app, DU_MAILS[0])
    gesendet(app, DU_MAILS[1].replace('Viele Grüße', 'Liebe Grüße'))
    gesendet(app, DU_MAILS[2].replace('Viele Grüße', 'Bis bald'))
    regeln = c.get(URL).json()['proposal']['rules']
    assert regeln['gruss'] == '' and regeln['address'] == 'du'


# -- Widerruf und „Nicht übernehmen“ ----------------------------------------------------------------------------------

def test_widerruf_wenn_eine_gesendete_mail_zurueckgezogen_oder_ueberholt_ist(tmp_path):
    app, c = client(tmp_path)
    mails = [gesendet(app, t) for t in DU_MAILS]
    vorschlag = c.get(URL).json()['proposal']
    assert c.put(URL, json={'scope': 'contact', **vorschlag}).status_code == 200
    assert wirksam(app) == DU_REGELN
    # Die Mail wird ausgeschlossen (etwa vom Nutzer): die Regel fällt.
    app.state.episodes.ignore(mails[0].id)
    assert wirksam(app) == {}
    assert c.get(URL).json()['profiles']['contact'] is None
    # Neue Lage, neue Bestätigung; dann wird eine Mail durch eine neue Fassung überholt (nicht ignoriert).
    neu = gesendet(app, 'Hallo Lea,\n\nalles klar, danke dir.\n\nViele Grüße\nLena')
    vorschlag = c.get(URL).json()['proposal']
    assert neu.id in vorschlag['evidence_ids'] and mails[0].id not in vorschlag['evidence_ids']
    assert c.put(URL, json={'scope': 'contact', **vorschlag}).status_code == 200
    key = 'mail:a:%d' % _laufende[0]
    fassung, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Rückmeldung', neu.body + '\n(nachgereicht)', neu.provenance, occurred_at=neu.occurred_at,
        participants=neu.participants, contacts=neu.contacts, source_key=key)
    app.state.episodes.advance_source_head(key, neu.id, fassung.id)
    assert wirksam(app) == {}, 'eine überholte Fassung trägt keine Regel mehr'


def test_veralteter_vorschlag_wird_bei_bestaetigung_abgewiesen(tmp_path):
    app, c = client(tmp_path)
    for t in DU_MAILS:
        gesendet(app, t)
    vorschlag = c.get(URL).json()['proposal']
    gesendet(app, 'Hallo Lea,\n\nnoch eine Mail dazu.\n\nViele Grüße\nLena')
    assert c.put(URL, json={'scope': 'contact', **vorschlag}).status_code == 409
    assert wirksam(app) == {}


def test_nicht_uebernehmen_wird_gemerkt_bis_neue_belege_dazukommen(tmp_path):
    app, c = client(tmp_path)
    for t in DU_MAILS:
        gesendet(app, t)
    vorschlag = c.get(URL).json()['proposal']
    assert c.post(URL + '/ablehnen', json={'evidence_ids': vorschlag['evidence_ids'][:1]}).status_code == 409
    assert c.post(URL + '/ablehnen', json={'evidence_ids': vorschlag['evidence_ids']}).status_code == 200
    stand = c.get(URL).json()
    assert stand['proposal'] is None and stand['abgelehnt'] is True
    assert wirksam(app) == {}
    # Eine Bestätigung mit den abgelehnten Belegen ist nicht mehr möglich (kein Vorschlag mehr).
    assert c.put(URL, json={'scope': 'contact', **vorschlag}).status_code == 409
    # Ein neuer Beleg: der Vorschlag kommt wieder, mit vier Belegen.
    gesendet(app, 'Hallo Lea,\n\nbis morgen dann.\n\nViele Grüße\nLena')
    stand = c.get(URL).json()
    assert stand['proposal'] and len(stand['proposal']['evidence_ids']) == 4 and stand['abgelehnt'] is False


# -- Kreis -----------------------------------------------------------------------------------------------------------

def test_kreisregel_nur_fuer_bestaetigten_kreis_und_schichtung_global_kreis_kontakt(tmp_path):
    app, c = client(tmp_path)
    assert c.put(URL, json={'scope': 'global', 'rules': {'address': 'sie', 'length': 'detailed'}}).status_code == 200
    assert c.put(f'{KREIS_URL}/kollegen', json={'rules': {'address': 'du', 'emoji': 'no'}}).status_code == 200
    assert c.put(f'{KREIS_URL}/freunde', json={'rules': {'address': 'du'}}).status_code == 422
    # Lea ist keinem Kreis bestätigt zugeordnet: nur die allgemeine Regel.
    assert wirksam(app) == {'address': 'sie', 'length': 'detailed'}
    assert c.get(URL).json()['kreis'] is None
    kreis_festlegen(app, LEA, 'kollegen')
    assert wirksam(app) == {'address': 'du', 'length': 'detailed', 'emoji': 'no'}
    stand = c.get(URL).json()
    assert stand['kreis'] == {'kreis': 'kollegen', 'kreis_text': 'Kollegen'}
    assert stand['profiles']['kreis']['rules']['address'] == 'du'
    assert c.put(URL, json={'scope': 'contact', 'rules': {'length': 'short'}}).status_code == 200
    assert wirksam(app) == {'address': 'du', 'length': 'short', 'emoji': 'no'}
    # Ein anderer Kreis bekommt nichts davon.
    kreis_festlegen(app, LEA, 'kontakte')
    assert wirksam(app) == {'address': 'sie', 'length': 'short'}
    assert c.delete(f'{KREIS_URL}/kollegen').status_code == 200
    kreis_festlegen(app, LEA, 'kollegen')
    assert wirksam(app) == {'address': 'sie', 'length': 'short'}


def test_kreisvorschlag_einstimmig_ueber_die_kontakte_des_kreises(tmp_path):
    app, c = client(tmp_path)
    for t in DU_MAILS:
        gesendet(app, t)
    gesendet(app, 'Hallo Max,\n\nkommst du morgen?\n\nViele Grüße\nLena', an=MAX)
    gesendet(app, 'Hallo Max,\n\ndanke dir!\n\nViele Grüße\nLena', an=MAX)
    # Ein dritter Kontakt mit Sie, aber ohne bestätigten Kreis: zählt nicht.
    gesendet(app, 'Sehr geehrter Herr Fremd,\n\nkönnten Sie das prüfen?\n\nMit freundlichen Grüßen\nLena', an='fremd@example.org')
    assert all(k['proposal'] is None for k in c.get(f'{KREIS_URL}e').json()['kreise']), 'ohne bestätigten Kreis kein Vorschlag'
    kreis_festlegen(app, LEA, 'kollegen')
    kreis_festlegen(app, MAX, 'kollegen')
    kreise = {k['kreis']: k for k in c.get(f'{KREIS_URL}e').json()['kreise']}
    vorschlag = kreise['kollegen']['proposal']
    assert vorschlag['rules'] == DU_REGELN and len(vorschlag['evidence_ids']) == 5 and vorschlag['personen'] == 2
    assert kreise['kollegen']['personen'] == 2 and kreise['innerer_kreis']['proposal'] is None
    assert c.put(f'{KREIS_URL}/kollegen', json=vorschlag).status_code == 200
    assert wirksam(app) == DU_REGELN and wirksam(app, MAX) == DU_REGELN
    # Max wechselt zu Sie: Mehrheit reicht nicht, die Anrede fällt aus dem Vorschlag; die bestätigte Regel bleibt.
    gesendet(app, 'Hallo Max,\n\nkönnen Sie das bitte prüfen?\n\nViele Grüße\nLena', an=MAX)
    vorschlag = {k['kreis']: k for k in c.get(f'{KREIS_URL}e').json()['kreise']}['kollegen']['proposal']
    assert vorschlag['rules']['address'] == 'default' and vorschlag['rules']['gruss'] == 'Viele Grüße'
    assert wirksam(app, MAX)['address'] == 'du'
    # „Nicht übernehmen“ je Kreis und ein Beleg, der wegfällt.
    assert c.post(f'{KREIS_URL}/kollegen/ablehnen', json={'evidence_ids': vorschlag['evidence_ids']}).status_code == 200
    assert {k['kreis']: k for k in c.get(f'{KREIS_URL}e').json()['kreise']}['kollegen']['proposal'] is None


# -- Befund 1: Belege ohne überholte Fassungen, gezielt gelesen ------------------------------------------------------

def test_examples_lesen_keine_ueberholte_fassung(tmp_path):
    from icarus_memory.mail_style import _examples, contact
    app, c = client(tmp_path)
    key, _ = contact(app.state.mail.item)
    quelle = f'mail-style:{key}:probe'
    alt, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Eigener Schreibbeleg', 'Hallo Lea, kommst du  morgen?',
                                       Provenance(source_type=SourceType.USER_STATED, source_ref=quelle),
                                       tags=[f'mail-style:{key}'], source_key=quelle)
    app.state.episodes.advance_source_head(quelle, None, alt.id)
    neu, _ = app.state.episodes.record(EpisodeKind.MESSAGE, 'Eigener Schreibbeleg', 'Hallo Lea, kommst du morgen?',
                                       Provenance(source_type=SourceType.USER_STATED, source_ref=quelle),
                                       tags=[f'mail-style:{key}'], source_key=quelle)
    app.state.episodes.advance_source_head(quelle, alt.id, neu.id)
    assert [e.id for e in _examples(app, key)] == [neu.id]
    assert [e['id'] for e in c.get(URL).json()['examples']] == [neu.id]
    # Über die Route: dieselbe Zeichenkette mit anderem Leerraum ersetzt die Fassung, statt daneben zu stehen.
    c.post(URL + '/examples', json={'text': 'Danke dir, bis  Montag dann!', 'own_text_confirmed': True})
    c.post(URL + '/examples', json={'text': 'Danke dir, bis Montag dann!', 'own_text_confirmed': True})
    texte = [e['text'] for e in c.get(URL).json()['examples']]
    assert texte.count('Danke dir, bis Montag dann!') == 1 and 'Danke dir, bis  Montag dann!' not in texte


def test_vorschlag_bei_zehntausend_episoden_unter_einer_sekunde(tmp_path):
    app, c = client(tmp_path)
    episodes = app.state.episodes
    zeilen = []
    for n in range(10_000):
        an = f'kontakt{n % 200}@example.org'
        eigen = n % 2 == 0
        contacts = ([{'name': '', 'adresse': ICH, 'rolle': 'von', 'ich': True}, {'name': '', 'adresse': an, 'rolle': 'an', 'ich': False}]
                    if eigen else [{'name': '', 'adresse': an, 'rolle': 'von', 'ich': False}, {'name': '', 'adresse': ICH, 'rolle': 'an', 'ich': True}])
        zeit = (START + timedelta(minutes=n)).isoformat()
        doc = {'id': f'e-last{n:06d}', 'kind': 'message', 'state': 'new', 'title': f'Mail {n}', 'body': f'Hallo, Text Nummer {n}.\n\nViele Grüße',
               'provenance': {'source_type': 'email', 'source_ref': f'a:<last{n}@example.org>', 'captured_at': None,
                              'extracted_by': None, 'verbatim': None},
               'recorded_at': zeit, 'occurred_at': zeit, 'project_id': None, 'participants': [an], 'contacts': contacts,
               'produced': [], 'consolidated_at': None, 'tags': [], 'digest': f'sha256:last{n}', 'covers': [], 'period': ''}
        import json as _json
        zeilen.append((doc['id'], doc['digest'], 'message', 'new', zeit, zeit, None, doc['title'], doc['body'], _json.dumps(doc), '', ''))
    with episodes.transaction():
        episodes._conn.executemany(
            'INSERT INTO episodes (id,digest,kind,state,recorded_at,occurred_at,project_id,title,body,document,source_key,metadata_digest) '
            'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', zeilen)
    for t in DU_MAILS:
        gesendet(app, t)
    c.get(URL)  # warm
    start = time.perf_counter()
    stand = c.get(URL).json()
    dauer = time.perf_counter() - start
    assert stand['proposal']['rules'] == DU_REGELN and stand['proposal']['gesendet'] == 3
    assert dauer < 1.0, f'{dauer:.2f} s'
    print(f'\nLaufzeit Vorschlag bei 10.003 Episoden: {dauer * 1000:.0f} ms')
