"""Mitteilungen auf dem Mac (Etappe 5, docs/24): was Kingfisher von sich aus meldet, und dass nichts doppelt kommt.

Die Regeln stehen in `mitteilungen.py`, die Verdrahtung in `mitteilungen_routes.py`. Geprüft wird mit eingesetzten
Quellen (Briefing, Termine, Fristen, Wegezeit) und einer gestellten Uhr; eine Probe geht über die Routen mit echten
Akten und einem Kalender aus der Attrappe. Nur synthetische Daten.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from icarus_memory import logbuch as logbuch_modul
from icarus_memory import mitteilungen
from icarus_memory.connectors.calendar import Event
from icarus_memory.fristlage import Frist
from icarus_memory.logbuch import Logbuch
from icarus_memory.mitteilungen import (MAX_ID, MAX_JE_ABRUF, MAX_PFAD, MAX_SATZ, MAX_TITEL, RUHE_AB, Dienst,
                                        Einstellung, uhrzeit_gueltig)

ZONE = ZoneInfo('Europe/Berlin')
TAG = datetime(2026, 10, 22, 7, 30, tzinfo=ZONE)
BRIEFING = {'tageslage': {'einleitung': 'Das zählt heute.',
                          'zeilen': [{'art': 'termin', 'text': 'Um 14:00 Uhr Gespräch Druckerei, Mainz.'}]}}
GEHEIM = 'Geheimprojekt Fuchsbau'


class Uhr:
    def __init__(self, zeit: datetime) -> None:
        self.zeit = zeit

    def __call__(self) -> datetime:
        return self.zeit


def termin(jetzt: datetime, minuten: int, *, titel='Gespräch Druckerei', ort='Werkstraße 4, Mainz', uid='t1',
           ganztaegig=False) -> dict:
    beginn = jetzt + timedelta(minutes=minuten)
    return {'uid': uid, 'summary': titel, 'start': beginn.isoformat(), 'end': (beginn + timedelta(hours=1)).isoformat(),
            'location': ort, 'attendees': [], 'all_day': ganztaegig}


def zusage(heute: date, tage: int = -1, *, richtung='von_mir', art='Zusage', text='Ich sende dir die Unterlagen bis gestern.',
           episode_id='ep-1', sache='person:anna') -> Frist:
    status = 'verstrichen' if tage < 0 else 'kommend'
    return Frist(datum=heute + timedelta(days=tage), text=text, ausdruck='bis gestern', episode_id=episode_id, titel='Unterlagen',
                 quelle_datum=None, quelle_art='Mail', art=art, richtung=richtung, status=status, tage=tage,
                 sache=sache, sache_name='Anna Keller', vermutlich=status == 'verstrichen')


def dienst(tmp_path, uhr: Uhr, *, an=True, morgens='07:30', briefing=None, termine=None, fristen=None, wegezeit=None) -> Dienst:
    quellen = {'briefing': briefing or (lambda: BRIEFING), 'termine': termine or (lambda jetzt: []),
               'fristen': fristen or (lambda jetzt: []), 'wegezeit': wegezeit or (lambda ort, beginn: None)}
    return Dienst(tmp_path / 'mitteilungen.sqlite3', einstellung=lambda: Einstellung(an=an, morgens=morgens), uhr=uhr, **quellen)


@pytest.fixture
def logbuch(tmp_path):
    buch = Logbuch(tmp_path / 'logbuch.sqlite3')
    logbuch_modul.verbinde(buch)
    try:
        yield buch
    finally:
        logbuch_modul.verbinde(None)
        buch.close()


# -- Morgenmitteilung ------------------------------------------------------------------------------


def test_morgenmitteilung_genau_einmal_je_tag_ab_der_uhrzeit_auch_nach_neustart(tmp_path):
    uhr = Uhr(TAG.replace(hour=7, minute=0))
    d = dienst(tmp_path, uhr)
    assert d.faellig() == [], 'vor der Uhrzeit nichts'
    uhr.zeit = TAG
    [m] = d.faellig()
    assert m['art'] == 'morgen' and m['pfad'] == '/today'
    assert m['titel'] == 'Das zählt heute.' and m['satz'] == 'Um 14:00 Uhr Gespräch Druckerei, Mainz.'
    uhr.zeit = TAG.replace(hour=9)
    assert d.faellig() == [], 'am selben Tag nicht noch einmal'
    neu = dienst(tmp_path, uhr)
    assert neu.faellig() == [], 'auch nicht nach einem Neustart (Merkliste in der Datei)'
    uhr.zeit = TAG + timedelta(days=1)
    [morgen] = neu.faellig()
    assert morgen['art'] == 'morgen' and morgen['id'] != m['id']


def test_morgenmitteilung_ohne_zeilen_sagt_das_ehrlich(tmp_path):
    leer = {'tageslage': {'einleitung': 'Heute liegt nichts an, das ich vorbereiten müsste.', 'zeilen': []}}
    [m] = dienst(tmp_path, Uhr(TAG), briefing=lambda: leer).faellig()
    assert m['titel'] == 'Guten Morgen' and m['satz'] == 'Heute liegt nichts an, das ich vorbereiten müsste.'


def test_die_eingestellte_morgenzeit_gilt(tmp_path):
    d = dienst(tmp_path, Uhr(TAG.replace(hour=8, minute=0)), morgens='08:15')
    assert d.faellig() == []
    d = dienst(tmp_path, Uhr(TAG.replace(hour=8, minute=15)), morgens='08:15')
    assert [m['art'] for m in d.faellig()] == ['morgen']


# -- Termin gleich ---------------------------------------------------------------------------------


@pytest.mark.parametrize('minuten, erwartet', [(20, 0), (29, 0), (30, 1), (45, 1), (60, 1), (61, 0), (90, 0)])
def test_termin_gleich_nur_im_fenster_von_30_bis_60_minuten(tmp_path, minuten, erwartet):
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    d = dienst(tmp_path, uhr, termine=lambda jetzt: [termin(jetzt, minuten)])
    treffer = [m for m in d.faellig() if m['art'] == 'termin']
    assert len(treffer) == erwartet


def test_termin_gleich_mit_ort_und_losfahren_einmal_je_termin(tmp_path):
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    los = uhr.zeit + timedelta(minutes=20)
    gefragt = []

    def wegezeit(ort, beginn):
        gefragt.append(ort)
        return {'status': 'berechnet', 'losfahren': los.isoformat()}
    fest = [termin(uhr.zeit, 45)]  # derselbe Termin bei jedem Abruf
    d = dienst(tmp_path, uhr, termine=lambda jetzt: fest, wegezeit=wegezeit)
    [m] = [m for m in d.faellig() if m['art'] == 'termin']
    assert m['titel'] == 'Gleich: Gespräch Druckerei' and m['pfad'] == '/calendar'
    assert m['satz'] == 'Um 12:45 Uhr, Werkstraße 4, Mainz. Losfahren um 12:20 Uhr.'
    assert gefragt == ['Werkstraße 4, Mainz']
    uhr.zeit += timedelta(minutes=5)
    assert [x for x in d.faellig() if x['art'] == 'termin'] == [], 'derselbe Termin kommt nicht noch einmal'


def test_termin_ohne_wegezeit_nennt_nur_zeit_und_ort(tmp_path):
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    d = dienst(tmp_path, uhr, termine=lambda jetzt: [termin(jetzt, 45)],
               wegezeit=lambda ort, beginn: {'status': 'wird_berechnet', 'losfahren': None})
    [m] = [m for m in d.faellig() if m['art'] == 'termin']
    assert m['satz'] == 'Um 12:45 Uhr, Werkstraße 4, Mainz.'
    d2 = dienst(tmp_path / 'b', uhr, termine=lambda jetzt: [termin(jetzt, 45, ort='')])
    [m2] = [m for m in d2.faellig() if m['art'] == 'termin']
    assert m2['satz'] == 'Um 12:45 Uhr.'


def test_ganztaegige_termine_sind_keine_termine_gleich(tmp_path):
    d = dienst(tmp_path, Uhr(TAG.replace(hour=12, minute=0)), termine=lambda jetzt: [termin(jetzt, 45, ganztaegig=True)])
    assert [m for m in d.faellig() if m['art'] == 'termin'] == []


# -- Verstrichene eigene Zusage --------------------------------------------------------------------


def test_verstrichene_eigene_zusage_einmal_mit_pfad_zur_akte(tmp_path):
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    d = dienst(tmp_path, uhr, fristen=lambda jetzt: [zusage(jetzt.date())])
    [m] = [m for m in d.faellig() if m['art'] == 'zusage']
    assert m['titel'] == 'Deine Zusage ist verstrichen' and m['pfad'] == '/memory/akte/person%3Aanna'
    assert m['satz'].startswith('Du hattest bis') and 'seit gestern' in m['satz']
    assert [x for x in d.faellig() if x['art'] == 'zusage'] == [], 'dieselbe Zusage nicht noch einmal'


@pytest.mark.parametrize('aenderung', [{'richtung': 'an_mich'}, {'art': 'Bitte'}, {'tage': -5}, {'tage': 0}, {'tage': 2}])
def test_nur_eigene_zusagen_deren_tag_gestern_war(tmp_path, aenderung):
    d = dienst(tmp_path, Uhr(TAG.replace(hour=12, minute=0)), fristen=lambda jetzt: [zusage(jetzt.date(), **aenderung)])
    assert [m for m in d.faellig() if m['art'] == 'zusage'] == []


# -- Grenzen je Abruf, Ruhezeit, Schalter ----------------------------------------------------------


def test_hoechstens_drei_je_abruf_und_je_art_eine(tmp_path):
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    termine = lambda jetzt: [termin(jetzt, 40, uid='a'), termin(jetzt, 50, uid='b'), termin(jetzt, 55, uid='c')]  # noqa: E731
    fristen = lambda jetzt: [zusage(jetzt.date(), episode_id='e1'), zusage(jetzt.date(), episode_id='e2', sache='person:ben')]  # noqa: E731
    d = dienst(tmp_path, uhr, termine=termine, fristen=fristen)
    erste = d.faellig()
    assert MAX_JE_ABRUF == 3 and len(erste) == 3
    assert [m['art'] for m in erste] == ['termin', 'zusage', 'morgen'], 'Dringendes zuerst, je Art eine'
    assert erste[0]['satz'].startswith('Um 12:40 Uhr'), 'der nächste Termin zuerst'
    zweite = d.faellig()
    assert [m['art'] for m in zweite] == ['termin', 'zusage'], 'beim nächsten Abruf die nächsten'
    assert {m['id'] for m in zweite}.isdisjoint({m['id'] for m in erste})


def test_in_der_ruhezeit_kommt_nur_ein_termin_gleich(tmp_path):
    assert RUHE_AB.hour == 21
    for stunde in (21, 23, 5):
        uhr = Uhr(TAG.replace(hour=stunde, minute=30))
        d = dienst(tmp_path / str(stunde), uhr, termine=lambda jetzt: [termin(jetzt, 45)],
                   fristen=lambda jetzt: [zusage(jetzt.date())])
        assert [m['art'] for m in d.faellig()] == ['termin'], stunde
    # Nach der Morgenzeit ist die Ruhe vorbei: Morgen und Zusage kommen nach.
    d = dienst(tmp_path / 'tag', Uhr(TAG.replace(hour=7, minute=31)), fristen=lambda jetzt: [zusage(jetzt.date())])
    assert sorted(m['art'] for m in d.faellig()) == ['morgen', 'zusage']


def test_ausgeschaltet_liefert_nichts_und_merkt_sich_nichts(tmp_path):
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    schalter = {'an': False}
    d = Dienst(tmp_path / 'm.sqlite3', einstellung=lambda: Einstellung(an=schalter['an'], morgens='07:30'), uhr=uhr,
               briefing=lambda: BRIEFING, termine=lambda jetzt: [termin(jetzt, 45)], fristen=lambda jetzt: [zusage(jetzt.date())],
               wegezeit=lambda ort, beginn: None)
    assert d.faellig() == []
    schalter['an'] = True
    assert len(d.faellig()) == 3, 'nach dem Einschalten kommt, was heute fällig ist'


def test_eine_kaputte_quelle_kostet_nur_ihren_teil(tmp_path):
    def kaputt(*a):
        raise RuntimeError(GEHEIM)
    d = dienst(tmp_path, Uhr(TAG.replace(hour=12, minute=0)), briefing=kaputt, termine=kaputt, fristen=lambda jetzt: [zusage(jetzt.date())])
    assert [m['art'] for m in d.faellig()] == ['zusage']


# -- Rückmeldung, Logbuch, Wochenzahl ----------------------------------------------------------------


def test_zugestellt_und_rueckmeldung_landen_im_logbuch_ohne_inhalt(tmp_path, logbuch):
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    d = dienst(tmp_path, uhr, termine=lambda jetzt: [termin(jetzt, 45, titel=GEHEIM)])
    ids = [m['id'] for m in d.faellig()]
    assert len(ids) == 2
    for kennung in ids:
        assert d.zugestellt(kennung) is True
    assert d.zugestellt('morgen:gibt-es-nicht') is False, 'unbekannte Kennung'
    assert d.rueckmeldung(ids[0], ueberfluessig=True) is True
    assert d.rueckmeldung(ids[0], ueberfluessig=True) is True, 'noch einmal ist in Ordnung'
    assert d.rueckmeldung('termin:fremd', ueberfluessig=True) is False
    ereignisse = logbuch.ereignisse(TAG - timedelta(days=1))
    assert [e.art for e in ereignisse] == ['mitteilung', 'mitteilung', 'mitteilung_ueberfluessig'], 'die zweite Rückmeldung zählt nicht doppelt'
    assert ereignisse[0].daten == {'sorte': 'termin'} and ereignisse[1].daten == {'sorte': 'morgen'}
    assert ereignisse[2].daten == {'sorte': 'termin'}
    gesamt = json.dumps([e.daten for e in ereignisse], ensure_ascii=False)
    assert GEHEIM not in gesamt and 'Druckerei' not in gesamt and 'Mainz' not in gesamt and ids[0] not in gesamt
    assert 'mitteilung' in logbuch_modul.ARTEN and 'mitteilung_ueberfluessig' in logbuch_modul.ARTEN


def test_wochenzahl_zaehlt_die_letzten_sieben_tage(tmp_path):
    jetzt = {'zeit': (TAG - timedelta(days=10)).timestamp()}
    buch = Logbuch(tmp_path / 'logbuch.sqlite3', uhr=lambda: jetzt['zeit'])
    logbuch_modul.verbinde(buch)
    try:
        buch.vermerke('mitteilung', sorte='morgen')            # vor zehn Tagen: zählt nicht
        buch.vermerke('mitteilung_ueberfluessig', sorte='morgen')
        jetzt['zeit'] = (TAG - timedelta(days=3)).timestamp()
        buch.vermerke('mitteilung', sorte='morgen')
        buch.vermerke('mitteilung', sorte='termin')
        buch.vermerke('mitteilung_ueberfluessig', sorte='termin')
        buch.vermerke('rueckmeldung', sorte='antwort')        # eine andere Art zählt nicht
        d = dienst(tmp_path, Uhr(TAG))
        assert d.woche() == {'gesendet': 2, 'ueberfluessig': 1}
    finally:
        logbuch_modul.verbinde(None)
        buch.close()


def test_ohne_logbuch_ist_die_wochenzahl_null(tmp_path):
    logbuch_modul.verbinde(None)
    assert dienst(tmp_path, Uhr(TAG)).woche() == {'gesendet': 0, 'ueberfluessig': 0}


# -- Antwortgröße und Protokoll --------------------------------------------------------------------


def test_antwort_bleibt_klein_auch_bei_langen_quellen(tmp_path):
    lang = 'Sehr ' * 200 + 'lang.'
    briefing = {'tageslage': {'einleitung': lang, 'zeilen': [{'art': 'termin', 'text': lang}]}}
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    d = dienst(tmp_path, uhr, briefing=lambda: briefing, termine=lambda jetzt: [termin(jetzt, 45, titel=lang, ort=lang, uid=lang)],
               fristen=lambda jetzt: [zusage(jetzt.date(), text=lang, sache='person:' + 'x' * 400)])
    antwort = d.faellig()
    assert len(antwort) == 3
    for m in antwort:
        assert len(m['titel']) <= MAX_TITEL and len(m['satz']) <= MAX_SATZ and len(m['id']) <= MAX_ID and len(m['pfad']) <= MAX_PFAD
        assert set(m) == {'id', 'art', 'titel', 'satz', 'pfad'}
    assert (MAX_TITEL, MAX_SATZ) == (60, 140)
    assert len(json.dumps({'mitteilungen': antwort}, ensure_ascii=False).encode()) < 1500


def test_nichts_inhaltliches_im_protokoll(tmp_path, caplog, logbuch):
    def kaputt(*a):
        raise RuntimeError(GEHEIM + ' Werkstraße 4')
    uhr = Uhr(TAG.replace(hour=12, minute=0))
    d = dienst(tmp_path, uhr, briefing=kaputt, termine=lambda jetzt: [termin(jetzt, 45, titel=GEHEIM, ort='Werkstraße 4, Mainz')],
               fristen=lambda jetzt: [zusage(jetzt.date(), text=GEHEIM)])
    with caplog.at_level(logging.DEBUG):
        antwort = d.faellig()
        for m in antwort:
            d.zugestellt(m['id'])
            d.rueckmeldung(m['id'], ueberfluessig=True)
        d.zugestellt('morgen:unbekannt')
    assert len(antwort) == 2
    for wort in (GEHEIM, 'Fuchsbau', 'Werkstraße', 'Mainz', 'Unterlagen', 'Anna'):
        assert wort not in caplog.text, wort
    assert 'RuntimeError' in caplog.text, 'der Fehler wird mit seiner Art vermerkt, nie mit seinem Text'


# -- Einstellung -----------------------------------------------------------------------------------


@pytest.mark.parametrize('text, gueltig', [('07:30', True), ('00:00', True), ('20:59', True), ('7:30', False), ('21:00', False),
                                           ('25:00', False), ('07:60', False), ('0730', False), ('', False), ('07:30 Uhr', False)])
def test_uhrzeit_hh_mm_vor_der_ruhezeit(text, gueltig):
    assert uhrzeit_gueltig(text) is gueltig


def test_einstellung_vorgaben_aus_und_sieben_uhr_dreissig_und_unbrauchbares_faellt_auf_die_vorgabe():
    assert Einstellung.aus(None) == Einstellung(an=False, morgens='07:30')
    assert Einstellung.aus({}).to_dict() == {'an': False, 'morgens': '07:30'}
    assert Einstellung.aus({'an': 'ja', 'morgens': '8:00'}) == Einstellung(an=False, morgens='07:30')
    assert Einstellung.aus({'an': True, 'morgens': '08:15'}) == Einstellung(an=True, morgens='08:15')


# -- Über die Routen -------------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    from icarus_memory.server import TOKEN_ENV, create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path / 'daten'))
    monkeypatch.setenv(TOKEN_ENV, 'synthetischer-token')
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Berlin')
    app = create_app()
    client = TestClient(app, headers={'x-icarus-token': 'synthetischer-token'})
    with client:
        yield app, client


def test_routen_einstellung_faellig_zugestellt_rueckmeldung_woche_erlaubnis(api, tmp_path):
    app, client = api
    stand = client.get('/api/v1/mitteilungen/einstellung').json()
    assert stand == {'an': False, 'morgens': '07:30', 'erlaubnis': 'unbekannt', 'woche': {'gesendet': 0, 'ueberfluessig': 0}}
    assert client.get('/api/v1/mitteilungen/faellig').json() == {'mitteilungen': []}
    for falsch in ('7:30', '25:00', '21:00', 'abends'):
        assert client.put('/api/v1/mitteilungen/einstellung', json={'morgens': falsch}).status_code == 422, falsch
    assert client.put('/api/v1/mitteilungen/einstellung', json={'an': 'ja'}).status_code == 422
    assert client.put('/api/v1/mitteilungen/einstellung', json={'fremd': 1}).status_code == 422
    neu = client.put('/api/v1/mitteilungen/einstellung', json={'an': True, 'morgens': '08:15'}).json()
    assert (neu['an'], neu['morgens']) == (True, '08:15')
    gespeichert = json.loads((tmp_path / 'daten' / 'einstellungen.json').read_text(encoding='utf-8'))
    assert gespeichert['mitteilungen'] == {'an': True, 'morgens': '08:15'}
    assert client.post('/api/v1/mitteilungen/morgen%3Agibt-es-nicht/zugestellt').status_code == 404
    assert client.post('/api/v1/mitteilungen/morgen%3Agibt-es-nicht/rueckmeldung', json={'ueberfluessig': True}).status_code == 404
    assert client.post('/api/v1/mitteilungen/x/rueckmeldung', json={}).status_code == 422
    assert client.post('/api/v1/mitteilungen/x/rueckmeldung', json={'ueberfluessig': 'ja'}).status_code == 422
    assert client.get('/api/v1/mitteilungen/woche').json() == {'gesendet': 0, 'ueberfluessig': 0}
    assert client.post('/api/v1/mitteilungen/erlaubnis', json={'status': 'abgelehnt'}).json()['erlaubnis'] == 'abgelehnt'
    assert client.post('/api/v1/mitteilungen/erlaubnis', json={'status': 'vielleicht'}).status_code == 422
    assert client.get('/api/v1/mitteilungen/einstellung').json()['erlaubnis'] == 'abgelehnt'
    # Ohne Ausweis nichts: Die Routen stehen hinter demselben Guard wie der Rest.
    assert client.get('/api/v1/mitteilungen/faellig', headers={'x-icarus-token': ''}).status_code in (401, 403)


def test_ueber_die_routen_mit_kalender_und_akten(api, monkeypatch):
    from icarus_memory.mitteilungen_routes import dienst as mitteilungen_dienst
    from tests.test_terminvorbereitung import ANNA, ICH, _mail, kalender
    app, client = api
    app.state.settings.mail.user = 'lea@hartmann-beratung.example'
    zone = ZONE
    jetzt = datetime.now(zone).replace(hour=12, minute=0, second=0, microsecond=0)
    d = mitteilungen_dienst(app)
    d.uhr = lambda: jetzt
    beginn = jetzt + timedelta(minutes=45)
    kalender(app, Event('t-1', 'Gespräch Druckerei', beginn.astimezone(timezone.utc), (beginn + timedelta(hours=1)).astimezone(timezone.utc),
                        location='Werkstraße 4, Mainz', attendees=[ANNA, ICH]))
    gestern = (jetzt.date() - timedelta(days=1)).strftime('%d.%m.%Y')
    _mail(app, 'Unterlagen', [(f'Ich sende dir die Unterlagen bis zum {gestern}.', 'commitment')], [ICH, ANNA], tage=6)
    client.put('/api/v1/mitteilungen/einstellung', json={'an': True})
    antwort = client.get('/api/v1/mitteilungen/faellig')
    assert antwort.status_code == 200
    assert len(antwort.content) < 4096
    nach_art = {m['art']: m for m in antwort.json()['mitteilungen']}
    assert set(nach_art) == {'morgen', 'termin', 'zusage'}
    assert nach_art['termin']['satz'].startswith('Um 12:45 Uhr, Werkstraße 4, Mainz.') and nach_art['termin']['pfad'] == '/calendar'
    assert nach_art['zusage']['pfad'].startswith('/memory/akte/person%3A') and 'seit gestern' in nach_art['zusage']['satz']
    assert nach_art['morgen']['pfad'] == '/today'
    kennung = nach_art['termin']['id']
    assert client.post(f'/api/v1/mitteilungen/{kennung}/zugestellt').json() == {'ok': True}
    assert client.post(f'/api/v1/mitteilungen/{kennung}/rueckmeldung', json={'ueberfluessig': True}).json() == {'ok': True}
    assert client.get('/api/v1/mitteilungen/woche').json() == {'gesendet': 1, 'ueberfluessig': 1}
    assert client.get('/api/v1/mitteilungen/faellig').json() == {'mitteilungen': []}, 'nichts doppelt'


def test_die_app_liest_die_wegezeit_nur_aus_dem_zwischenspeicher():
    """`nur_lesen`: keine Anfrage an einen Kartendienst für eine Mitteilung; was da ist, wird genommen."""
    from tests.test_wegezeit import BEGINN, ORT, Fake, dienst as wegdienst
    fake = Fake(minuten=35)
    w = wegdienst(fake)
    still = w.auskunft(ORT, beginn=BEGINN, nur_lesen=True)
    assert still.status == 'nicht_berechnet' and still.losfahren is None and fake.aufrufe == [], 'nur lesen fragt nicht'
    voll = w.auskunft(ORT, beginn=BEGINN)
    assert voll.status == 'berechnet' and len(fake.aufrufe) == 1
    wieder = w.auskunft(ORT, beginn=BEGINN, nur_lesen=True)
    assert wieder.status == 'berechnet' and wieder.losfahren == voll.losfahren and len(fake.aufrufe) == 1


def test_das_modul_kennt_kein_modell():
    import inspect
    quelle = inspect.getsource(mitteilungen)
    for wort in ('provider', 'complete_json', 'ollama', 'model_roles', 'Modellaufruf'):
        assert wort not in quelle, wort
