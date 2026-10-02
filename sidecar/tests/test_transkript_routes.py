"""Transkript-Eingangsordner: Freigabe, Trennen, Auswahl, Zuordnung über die Routen (F3)."""
from __future__ import annotations

import base64
import io
import zipfile
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from icarus_memory.calendar_memory import KalenderGedaechtnis, fenster
from icarus_memory.connectors.calendar import Event
from icarus_memory.episodes import EpisodeState
from icarus_memory.server import create_app

JETZT = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)
TAG = datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)      # 28.9.2026, 14:30 Uhr in Berlin
ANNA = 'Anna Berg <anna.berg@winter.example>'
MEETING = 'Anna Berg: Guten Tag.\nBert Kraus: Hallo.\nAnna Berg: Das Budget steht.\nBert Kraus: Gut.\n'
WURZEL = '/api/v1/transcript-sync'


def termine(app, *eintraege):
    von, bis = fenster(JETZT)
    KalenderGedaechtnis(app.state.episodes, app.state.claims).abgleichen('k', 'Arbeit', list(eintraege), von, bis, at=JETZT)


def treffen(uid='a', titel='Jour fixe Winter', start=TAG, teilnehmer=(ANNA,)):
    return Event(uid=uid, summary=titel, start=start, end=start + timedelta(hours=1), attendees=list(teilnehmer))


def anmelden(client, *, gewaehlt=True, root='mit-root', ordner='/Users/test/Documents/Kingfisher/Transkripte'):
    """Der Mac-Helfer meldet seinen Ordner; `gewaehlt` = der Nutzer hat ihn im Dialog gewählt."""
    picked = None
    if gewaehlt:
        picked = client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'}).json()['pick_request']['id']
    antwort = client.post(f'{WURZEL}/worker', json={'root_id': root, 'folder': ordner, 'picked': picked})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()


def lauf(client, zustand):
    antwort = client.post(f'{WURZEL}/begin', json={'root_id': zustand['root_id'], 'generation': zustand['generation']})
    assert antwort.status_code == 200, antwort.text
    return {'root_id': zustand['root_id'], 'generation': zustand['generation'], 'run_id': antwort.json()['run_id']}


def hochladen(client, lauf_, name, inhalt, modified=None):
    daten = inhalt if isinstance(inhalt, bytes) else inhalt.encode()
    return client.post(f'{WURZEL}/files', json={**lauf_, 'filename': name, 'modified': modified,
                                                'content_base64': base64.b64encode(daten).decode()})


def docx(*absaetze):
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    inhalt = ''.join(f'<w:p><w:r><w:t>{a}</w:t></w:r></w:p>' for a in absaetze)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, 'w') as archiv:
        archiv.writestr('word/document.xml', f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{inhalt}</w:body></w:document>')
    return puffer.getvalue()


def test_ohne_ausdrueckliche_wahl_wird_nichts_gelesen():
    app = create_app()
    with TestClient(app) as client:
        zustand = anmelden(client, gewaehlt=False)
        assert zustand['enabled'] is False                       # ein gemeldeter Ordner ist noch kein freigegebener
        assert client.post(f'{WURZEL}/begin', json={'root_id': 'mit-root', 'generation': zustand['generation']}).status_code == 409
        fremd = {'root_id': 'mit-root', 'generation': zustand['generation'], 'run_id': 'x'}
        assert hochladen(client, fremd, 'a.txt', MEETING).status_code == 409
        assert app.state.episodes.tagged('transkript') == []


def test_die_wahl_im_dialog_ist_die_freigabe_genau_dieses_ordners():
    app = create_app()
    with TestClient(app) as client:
        anfrage = client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'}).json()['pick_request']
        # Ein falsches Kennzeichen (oder keines) gibt nichts frei.
        falsch = client.post(f'{WURZEL}/worker', json={'root_id': 'r1', 'folder': '/x', 'picked': 'nicht-die-anfrage'}).json()
        assert falsch['enabled'] is False
        richtig = client.post(f'{WURZEL}/worker', json={'root_id': 'r1', 'folder': '/x', 'picked': anfrage['id']}).json()
        assert richtig['enabled'] is True and richtig['folder'] == '/x' and richtig['pick_request'] is None
        # Ein anderer Ordner ohne neue Wahl: der alte wird entzogen, der neue ist nicht freigegeben.
        andere = client.post(f'{WURZEL}/worker', json={'root_id': 'r2', 'folder': '/y'}).json()
        assert andere['enabled'] is False and andere['folder'] == '/y'


def test_nur_mitschriftformate_werden_aufgenommen_und_zugeordnet():
    app = create_app()
    with TestClient(app) as client:
        termine(app, treffen())
        lauf_ = lauf(client, anmelden(client))
        vtt = 'WEBVTT\n\n00:00:01.000 --> 00:00:03.000\n<v Anna Berg>Hallo</v>\n\n00:00:04.000 --> 00:00:06.000\n<v Bert Kraus>Moin</v>\n'
        for name, inhalt in [('2026-09-28 14.30 Jour fixe Winter.txt', MEETING), ('b.vtt', vtt),
                             ('c.srt', '1\n00:00:01,000 --> 00:00:02,000\nAnna Berg: Hallo\n'), ('d.md', MEETING),
                             ('e.docx', docx(*MEETING.splitlines()))]:
            assert hochladen(client, lauf_, name, inhalt).status_code == 200, name
        for name in ('f.pdf', 'g.csv', 'h.exe'):
            assert hochladen(client, lauf_, name, 'x').status_code == 422, name
        assert hochladen(client, lauf_, '../draussen.txt', MEETING).status_code == 422
        uebersicht = client.get('/api/v1/transkripte').json()
        assert uebersicht['stand']['aufgenommen'] == 5
        erste = next(e for e in uebersicht['eintraege'] if e['titel'] == 'Jour fixe Winter')
        assert erste['status'] == 'zugeordnet' and erste['termin']['titel'] == 'Jour fixe Winter'
        assert uebersicht['stand']['zugeordnet'] >= 1
        assert uebersicht['vorgabe'] == 'Dokumente/Kingfisher/Transkripte'


def test_trennen_entzieht_alle_mitschriften_und_bietet_den_alten_ordner_nicht_wieder_an():
    app = create_app()
    with TestClient(app) as client:
        termine(app, treffen())
        lauf_ = lauf(client, anmelden(client))
        antwort = hochladen(client, lauf_, '2026-09-28 14.30 Jour fixe Winter.txt', MEETING)
        episode_id = antwort.json()['id']
        assert app.state.episodes.get(episode_id).state is not EpisodeState.IGNORED
        getrennt = client.delete('/api/v1/transkripte/ordner').json()
        assert getrennt['entzogen'] == 1 and getrennt['folder'] is None and getrennt['enabled'] is False
        assert app.state.episodes.get(episode_id).state is EpisodeState.IGNORED
        uebersicht = client.get('/api/v1/transkripte').json()
        assert uebersicht['stand']['aufgenommen'] == 0 and uebersicht['eintraege'] == []
        # Der Helfer meldet seinen alten Ordner erneut: ohne neue Wahl bleibt es getrennt.
        wieder = client.post(f'{WURZEL}/worker', json={'root_id': 'mit-root', 'folder': '/Users/test/Documents/Kingfisher/Transkripte'}).json()
        assert wieder['folder'] is None and wieder['enabled'] is False and wieder['getrennt'] is True
        assert client.post(f'{WURZEL}/begin', json={'root_id': 'mit-root', 'generation': wieder['generation']}).status_code == 409


def test_neu_freigeben_holt_unveraenderte_mitschriften_zurueck():
    app = create_app()
    with TestClient(app) as client:
        termine(app, treffen())
        lauf_ = lauf(client, anmelden(client))
        erste = hochladen(client, lauf_, '2026-09-28 14.30 Jour fixe Winter.txt', MEETING).json()
        client.delete('/api/v1/transkripte/ordner')
        lauf2 = lauf(client, anmelden(client))
        zweite = hochladen(client, lauf2, '2026-09-28 14.30 Jour fixe Winter.txt', MEETING).json()
        assert zweite['id'] == erste['id']
        assert app.state.episodes.get(erste['id']).state is not EpisodeState.IGNORED


def test_ordner_wechseln_entzieht_den_alten():
    app = create_app()
    with TestClient(app) as client:
        lauf_ = lauf(client, anmelden(client, root='r1', ordner='/a'))
        episode_id = hochladen(client, lauf_, 'x.txt', MEETING).json()['id']
        anmelden(client, root='r2', ordner='/b')
        assert app.state.episodes.get(episode_id).state is EpisodeState.IGNORED


def test_wahl_kann_abgebrochen_werden():
    with TestClient(create_app()) as client:
        anfrage = client.post('/api/v1/transkripte/ordner', json={'modus': 'vorgabe'}).json()['pick_request']
        assert anfrage['modus'] == 'vorgabe'
        assert client.delete('/api/v1/transkripte/ordner/auswahl').json()['pick_request'] is None
        # Der Helfer meldet: am Mac abgebrochen.
        neu = client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'}).json()['pick_request']
        stand = client.post(f'{WURZEL}/worker', json={'cancelled': neu['id']}).json()
        assert stand['pick_request'] is None


def test_zuordnung_per_klick_und_loesen_ueber_die_routen():
    app = create_app()
    with TestClient(app) as client:
        termine(app, treffen('a', 'Fokuszeit', teilnehmer=()), treffen('b', 'Abstimmung Lieferant', teilnehmer=()))
        lauf_ = lauf(client, anmelden(client))
        episode_id = hochladen(client, lauf_, '2026-09-28 14.30 Notizen.txt', 'Hallo\nWeiter\n').json()['id']
        eintrag = next(e for e in client.get('/api/v1/transkripte').json()['eintraege'] if e['id'] == episode_id)
        assert eintrag['status'] == 'vorschlag' and len(eintrag['kandidaten']) == 2
        schluessel = eintrag['kandidaten'][0]['key']
        gewaehlt = client.post(f'/api/v1/transkripte/{episode_id}/zuordnung', json={'termin': schluessel}).json()
        assert gewaehlt['status'] == 'zugeordnet' and gewaehlt['von'] == 'nutzer'
        am_termin = client.get('/api/v1/transkripte/termin', params={'key': schluessel}).json()
        assert [t['id'] for t in am_termin['transkripte']] == [episode_id]
        geloest = client.delete(f'/api/v1/transkripte/{episode_id}/zuordnung').json()
        assert geloest['status'] == 'allein'
        assert client.get('/api/v1/transkripte/termin', params={'key': schluessel}).json()['transkripte'] == []
        assert client.post('/api/v1/transkripte/e-unbekannt/zuordnung', json={'termin': schluessel}).status_code == 404
        assert client.post(f'/api/v1/transkripte/{episode_id}/zuordnung', json={'termin': 'x|2020-01-01T00:00:00+00:00'}).status_code == 409


def test_endpunkte_verlangen_das_token(monkeypatch):
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'test-only')
    with TestClient(create_app()) as client:
        for methode, pfad in [('get', '/api/v1/transkripte'), ('delete', '/api/v1/transkripte/ordner'),
                              ('get', '/api/v1/transcript-sync'), ('get', '/api/v1/transkripte/termin?key=abc')]:
            assert getattr(client, methode)(pfad).status_code == 401, pfad
        assert client.post('/api/v1/transkripte/ordner', json={'modus': 'waehlen'}).status_code == 401
