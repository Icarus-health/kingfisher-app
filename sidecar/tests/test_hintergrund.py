"""Hintergrund ohne Nacht: Reihenfolge nach Nutzen, Rücksicht, Drosselung, Neustart, Ampel, Schätzung.

Alles mit synthetischen Quellen. Die Regel steht in `docs/46-hintergrund.md`.
"""
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import hintergrund
from icarus_memory.backends import MemoryBackend
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.hintergrund import (
    ANLAUF_S, AMPEL, Aktivitaet, ModellAmpel, Steuerung, als_hintergrund, ist_antwort, ordnen, rate,
    speicher_reicht, wann_text, zaehlen, zaehlt_als_eingabe,
)
from icarus_memory.model import Provenance, SourceType
from icarus_memory.scheduler import JobResult, Scheduler
from icarus_memory.server import create_app
from icarus_memory.store import SelfModelStore

JETZT = datetime(2026, 9, 30, 10, 0, tzinfo=timezone.utc)


class Uhr:
    def __init__(self, wert=1000.0):
        self.wert = wert

    def __call__(self):
        return self.wert


def quelle(ep, art, titel, wann, text=None):
    text = text or f'Synthetischer Text ohne Datum: {titel}.'  # je Quelle verschieden, sonst entdoppelt der Bestand
    typ = {EpisodeKind.MESSAGE: SourceType.EMAIL, EpisodeKind.EVENT: SourceType.CALENDAR}.get(art, SourceType.DOCUMENT)
    episode, _ = ep.record(art, titel, text, Provenance(typ, source_ref=f'synth:{titel}'), occurred_at=wann)
    return episode.id


@pytest.fixture
def bestand(tmp_path):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    ids = {
        'alt_2019': quelle(ep, EpisodeKind.MESSAGE, 'Alte Mail Eins', datetime(2019, 3, 1, tzinfo=timezone.utc)),
        'vor_60_tagen': quelle(ep, EpisodeKind.MESSAGE, 'Mail Zwei', JETZT - timedelta(days=60)),
        'dokument_5_tage': quelle(ep, EpisodeKind.DOCUMENT, 'Notiz Drei', JETZT - timedelta(days=5)),
        'termin_in_10_tagen': quelle(ep, EpisodeKind.EVENT, 'Termin Vier', JETZT + timedelta(days=10)),
        'post_gestern': quelle(ep, EpisodeKind.MESSAGE, 'Post Fünf', JETZT - timedelta(days=1)),
        'termin_uebermorgen': quelle(ep, EpisodeKind.EVENT, 'Termin Sechs', JETZT + timedelta(days=2)),
        'frist': quelle(ep, EpisodeKind.MESSAGE, 'Rechnung mit Frist', JETZT - timedelta(days=40),
                        text='Bitte begleichen Sie den Betrag bis zum 20.10.2026.'),
        'teilnehmerin_alt': quelle(ep, EpisodeKind.MESSAGE, 'Alte Mail von Frau Beispiel',
                                   datetime(2021, 5, 4, tzinfo=timezone.utc)),
    }
    # Bezüge der Akten: Frau Beispiel nimmt am Termin übermorgen teil und schrieb 2021 eine Mail.
    for kennung in (ids['termin_uebermorgen'], ids['teilnehmerin_alt']):
        ep._conn.execute("INSERT OR IGNORE INTO sach_bezuege(episode_id,fingerprint,sache,art,grundlage) VALUES(?,?,?,?,?)",
                         (kennung, 'f', 'person:a:beispiel@example.org', 'person', 'anker'))
    ep._conn.commit()
    yield ep, ids
    ep.close()


def test_reihenfolge_erst_was_morgen_zaehlt_dann_neues_dann_rueckstand_neu_nach_alt(bestand):
    ep, ids = bestand
    plan = ordnen(ep, JETZT)
    namen = {v: k for k, v in ids.items()}
    assert [(namen[e.episode_id], e.stufe) for e in plan] == [
        ('termin_uebermorgen', 'morgen'),
        ('post_gestern', 'morgen'),
        ('frist', 'morgen'),
        ('teilnehmerin_alt', 'morgen'),
        ('termin_in_10_tagen', 'neu'),
        ('dokument_5_tage', 'neu'),
        ('vor_60_tagen', 'rueckstand'),
        ('alt_2019', 'rueckstand'),
    ]


def test_erledigte_quellen_fallen_aus_der_schlange_und_der_fortschritt_zaehlt_sie(bestand):
    ep, ids = bestand
    ep._conn.execute("INSERT INTO working_memory_sources(episode_id,fingerprint,status) VALUES(?,?,?)",
                     (ids['termin_uebermorgen'], 'f', 'complete'))
    ep._conn.execute("INSERT INTO working_memory_sources(episode_id,fingerprint,status,retry_after) VALUES(?,?,?,?)",
                     (ids['post_gestern'], 'f', 'failed', time.time() + 3600))
    ep._conn.commit()
    plan = [e.episode_id for e in ordnen(ep, JETZT)]
    assert ids['termin_uebermorgen'] not in plan
    assert ids['post_gestern'] not in plan  # gescheitert und noch in der Wartezeit
    assert zaehlen(ep) == {'gesamt': 8, 'fertig': 1}


def test_veraltete_einordnung_bleibt_in_der_priorisierten_warteschlange(bestand):
    ep, ids = bestand
    ep._conn.execute("INSERT INTO working_memory_sources(episode_id,fingerprint,status) VALUES(?,?,?)",
                     (ids['termin_uebermorgen'], 'f', 'complete'))
    ep._conn.execute(
        "UPDATE working_memory_sources SET analysis_version=0 WHERE episode_id=?",
        (ids['termin_uebermorgen'],))
    ep._conn.commit()

    plan = [item.episode_id for item in ordnen(ep, JETZT)]
    assert ids['termin_uebermorgen'] in plan
    assert zaehlen(ep) == {'gesamt': 8, 'fertig': 0}

    ep._conn.execute(
        "UPDATE working_memory_sources SET retry_after=? WHERE episode_id=?",
        (time.time() + 3600, ids['termin_uebermorgen']))
    ep._conn.commit()
    assert ids['termin_uebermorgen'] not in [item.episode_id for item in ordnen(ep, JETZT)]
    assert zaehlen(ep) == {'gesamt': 8, 'fertig': 0}


def test_steuerung_gibt_quellen_in_reihenfolge_aus_und_stellt_ausgegebene_zurueck(bestand):
    ep, ids = bestand
    steuerung = Steuerung(None, lambda: ep, uhr=Uhr(), wanduhr=lambda: JETZT)
    assert steuerung.dringend_offen()
    erste = steuerung.naechste_quellen(2)
    assert erste == [ids['termin_uebermorgen'], ids['post_gestern']]
    assert steuerung.naechste_quellen(5, nur='morgen') == [ids['frist'], ids['teilnehmerin_alt']]
    assert not steuerung.dringend_offen()
    assert steuerung.naechste_quellen(1) == [ids['termin_in_10_tagen']]
    stufen = {s['stufe']: s['offen'] for s in steuerung.schlange()}
    assert stufen == {'morgen': 4, 'neu': 2, 'rueckstand': 2}


def test_pause_bei_eingabe_antwort_und_durch_den_menschen():
    uhr = Uhr()
    steuerung = Steuerung(None, lambda: None, uhr=uhr, ruhe_s=20)
    assert steuerung.sperre() is None
    steuerung.aktivitaet.eingabe()
    uhr.wert += 19
    assert steuerung.sperre() == 'nutzer'
    assert 0 < steuerung.wartezeit() <= 30
    uhr.wert += 2
    assert steuerung.sperre() is None
    with steuerung.aktivitaet.antwort():
        uhr.wert += 60  # eine lange Antwort: solange sie läuft, ruht der Hintergrund
        assert steuerung.sperre() == 'antwort'
    assert steuerung.sperre() == 'nutzer'  # und noch 20 s danach
    uhr.wert += 21
    steuerung.pausieren(True)
    assert steuerung.sperre() == 'pausiert'
    steuerung.pausieren(False)
    assert steuerung.sperre() is None


def test_drosselung_ruht_nach_jedem_haeppchen():
    assert Steuerung.pause_nach(0.1) == hintergrund.PAUSE_MIN_S
    assert Steuerung.pause_nach(10) == pytest.approx(10 * (1 - hintergrund.ARBEITSANTEIL) / hintergrund.ARBEITSANTEIL)
    assert Steuerung.pause_nach(600) == hintergrund.PAUSE_MAX_S


def test_welche_anfragen_als_eingabe_zaehlen():
    assert zaehlt_als_eingabe('POST', '/api/v1/hintergrund/aktiv', {})
    assert zaehlt_als_eingabe('PUT', '/api/v1/einrichtung', {})
    assert not zaehlt_als_eingabe('GET', '/api/v1/einrichtung/lernt', {})  # Abfragen im Takt
    assert not zaehlt_als_eingabe('POST', '/api/v1/mac-calendar/worker', {b'x-icarus-token': b't'})  # Helfer
    assert ist_antwort('POST', '/api/v1/conversations/abc/messages')
    assert ist_antwort('POST', '/api/v1/conversations/abc/messages/m1/retry')
    assert ist_antwort('POST', '/chat')
    assert not ist_antwort('GET', '/api/v1/conversations/abc')
    assert not ist_antwort('POST', '/api/v1/conversations/abc/approvals/x')


def _zeitplan(steuerung, aufrufe, *, dauer=0.0):
    scheduler = Scheduler()

    def einordnen(with_model, *, source_ids=None, prompt=False):
        aufrufe.append(list(source_ids or []))
        time.sleep(dauer)
        return JobResult('gedaechtnis')

    scheduler._run_working_memory = einordnen
    scheduler.configure(enabled=True, with_model=True)
    scheduler.anschliessen(steuerung)
    scheduler._last_at = datetime.now().astimezone()  # kein voller Durchgang in diesem Test
    return scheduler


def warten(bedingung, sekunden=3.0):
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if bedingung():
            return True
        time.sleep(0.01)
    return bedingung()


def test_zeitplan_arbeitet_nicht_waehrend_der_mensch_aktiv_ist(bestand, monkeypatch):
    ep, ids = bestand
    monkeypatch.setattr('icarus_memory.scheduler.TICK_SECONDS', 0.05)
    uhr = Uhr()
    steuerung = Steuerung(None, lambda: ep, uhr=uhr, wanduhr=lambda: JETZT, ruhe_s=20)
    steuerung.aktivitaet.eingabe()
    aufrufe = []
    scheduler = _zeitplan(steuerung, aufrufe)
    monkeypatch.setattr(steuerung, 'wartezeit', lambda: 0.05)
    scheduler.start()
    try:
        time.sleep(0.4)
        assert aufrufe == []  # jemand tippt: kein Häppchen
        uhr.wert += 21
        scheduler.wecken()
        assert warten(lambda: len(aufrufe) >= 1)
        # und dann in der Reihenfolge nach Nutzen
        assert aufrufe[0][:2] == [ids['termin_uebermorgen'], ids['post_gestern']]
    finally:
        scheduler.stop()


def test_zeitplan_ruht_nach_jedem_haeppchen(bestand, monkeypatch):
    ep, _ = bestand
    monkeypatch.setattr('icarus_memory.scheduler.TICK_SECONDS', 30)
    steuerung = Steuerung(None, lambda: ep, uhr=Uhr(), wanduhr=lambda: JETZT, ruhe_s=0)
    pausen = []

    def pause_nach(dauer):
        pausen.append(dauer)
        return 0.05  # im Test kurz; die Bemessung selbst prüft test_drosselung_ruht_nach_jedem_haeppchen

    monkeypatch.setattr(steuerung, 'pause_nach', pause_nach)
    aufrufe = []
    scheduler = _zeitplan(steuerung, aufrufe, dauer=0.6)
    scheduler.start()
    try:
        scheduler.wecken()
        assert warten(lambda: len(aufrufe) >= 2)
        assert pausen and all(d >= 0.5 for d in pausen)  # nach jedem Häppchen eine Pause, bemessen an seiner Dauer
    finally:
        scheduler.stop()


def test_zustand_ueberdauert_den_neustart(bestand, tmp_path):
    ep, ids = bestand
    datei = tmp_path / 'hintergrund.json'
    erste = Steuerung(datei, lambda: ep, uhr=Uhr(), wanduhr=lambda: JETZT)
    erste.pausieren(True)
    erste.voller_lauf_fertig(JETZT - timedelta(hours=1))
    assert erste.naechste_quellen(2) == [ids['termin_uebermorgen'], ids['post_gestern']]
    # Die ersten beiden sind eingeordnet; dann geht der Rechner aus.
    for kennung in (ids['termin_uebermorgen'], ids['post_gestern']):
        ep._conn.execute("INSERT INTO working_memory_sources(episode_id,fingerprint,status) VALUES(?,?,?)",
                         (kennung, 'f', 'complete'))
    ep._conn.commit()

    zweite = Steuerung(datei, lambda: ep, uhr=Uhr(), wanduhr=lambda: JETZT)
    assert zweite.pausiert
    assert zweite.naechste_quellen(1) == [ids['frist']]  # weiter, wo es stand
    scheduler = Scheduler()
    scheduler.configure(enabled=True, interval_minutes=240)
    scheduler.anschliessen(zweite)
    # Der volle Durchgang von vor einer Stunde gilt: nicht sofort beim Start.
    assert scheduler.next_run() == JETZT - timedelta(hours=1) + timedelta(minutes=240)


def test_ohne_gemerkten_durchgang_erst_nach_dem_anlauf():
    steuerung = Steuerung(None, lambda: None, wanduhr=lambda: JETZT)
    scheduler = Scheduler()
    scheduler.configure(enabled=True, interval_minutes=240)
    scheduler.anschliessen(steuerung)
    assert scheduler.next_run() == JETZT + timedelta(seconds=ANLAUF_S)


def test_ampel_haelt_die_antwort_bis_zum_ende_des_laufenden_hintergrundaufrufs():
    ampel = ModellAmpel()
    spuren = []

    def hinten():
        with als_hintergrund():
            with ampel.aufruf():
                spuren.append(('hinten an', time.monotonic()))
                time.sleep(0.3)
                spuren.append(('hinten aus', time.monotonic()))

    faden = threading.Thread(target=hinten)
    faden.start()
    assert warten(lambda: spuren)
    with ampel.aufruf():  # dieser Faden ist Vordergrund
        spuren.append(('vorne an', time.monotonic()))
    faden.join()
    assert [s[0] for s in spuren] == ['hinten an', 'hinten aus', 'vorne an']


def test_ampel_laesst_den_hintergrund_warten_solange_eine_antwort_laeuft_oder_gesperrt_ist():
    ampel = ModellAmpel()
    spuren = []
    gesperrt = {'grund': 'nutzer'}

    def hinten():
        with als_hintergrund(lambda: gesperrt['grund']):
            with ampel.aufruf():
                spuren.append('hinten')

    with ampel.vordergrund():
        faden = threading.Thread(target=hinten)
        faden.start()
        time.sleep(0.3)
        spuren.append('vorne fertig')
    time.sleep(0.4)
    assert spuren == ['vorne fertig']  # die Sperre der Steuerung hält ihn weiter an
    gesperrt['grund'] = None
    faden.join(2)
    assert spuren == ['vorne fertig', 'hinten']


def test_ampel_parallel_nur_wenn_der_speicher_reicht():
    ampel = ModellAmpel()
    ampel.parallel = lambda: True
    frei = threading.Event()

    def hinten():
        with als_hintergrund():
            with ampel.aufruf():
                frei.wait(2)

    faden = threading.Thread(target=hinten)
    faden.start()
    assert warten(lambda: ampel.belegt()['hinten'] == 1)
    start = time.monotonic()
    with ampel.vordergrund():
        pass
    assert time.monotonic() - start < 0.2
    frei.set()
    faden.join()
    assert speicher_reicht(64, ['qwen3.5:4b', 'qwen3.5:2b'])
    assert not speicher_reicht(8, ['qwen3.5:4b', 'qwen3.5:2b'])
    assert not speicher_reicht(None, ['qwen3.5:4b', 'qwen3.5:2b'])  # Gerät unbekannt: nacheinander
    assert not speicher_reicht(64, ['qwen3.5:4b', 'qwen3.5:4b'])  # dasselbe Modell teilt die Rechenzeit
    assert not speicher_reicht(64, ['qwen3.5:4b', 'unbekannt:1b'])


def test_lokaler_anbieter_geht_ueber_die_ampel(monkeypatch):
    from icarus_memory.providers import OpenAICompatible

    anbieter = OpenAICompatible('synth', base_url='http://127.0.0.1:11434/v1')
    gesehen = []

    class Antwort:
        def raise_for_status(self):
            pass

        def json(self):
            return {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]}

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            gesehen.append(AMPEL.belegt())
            return Antwort()

    monkeypatch.setattr(anbieter, '_client', lambda timeout: Client())
    anbieter.complete([{'role': 'user', 'content': 'x'}], [])
    ergebnis = []
    faden = threading.Thread(target=lambda: ergebnis.append(_im_hintergrund(anbieter)))
    faden.start()
    faden.join()
    assert gesehen == [{'vorne': 1, 'hinten': 0}, {'vorne': 0, 'hinten': 1}]


def _im_hintergrund(anbieter):
    with als_hintergrund():
        return anbieter.complete_json([{'role': 'user', 'content': 'x'}])


def test_rate_misst_nur_die_laufzeit_und_die_schaetzung_sagt_wann():
    minute = 60.0
    proben = [[i * minute, i * 10.0] for i in range(11)]  # 10 Minuten, 10 Quellen je Minute
    # Nacht: 10 Stunden aus, danach weitere 10 Minuten
    proben += [[10 * minute + 36000 + i * minute, 100 + i * 10.0] for i in range(11)]
    assert rate(proben) == pytest.approx(10 / minute)
    assert rate(proben[:3]) is None  # zu kurz gemessen: noch unklar
    assert wann_text(JETZT + timedelta(minutes=30), JETZT) == 'in weniger als einer Stunde'
    heute = datetime(2026, 9, 30, 9, 0).astimezone()
    assert wann_text(heute.replace(hour=19), heute) == 'heute Abend'
    assert wann_text(heute + timedelta(days=1, hours=3, minutes=30), heute) == 'morgen Mittag'
    assert wann_text(heute + timedelta(days=1, hours=-2), heute) == 'morgen früh'
    assert wann_text(heute + timedelta(days=3), heute).startswith('am ')
    assert wann_text(heute + timedelta(days=21), heute) == 'in etwa drei Wochen'


def test_stand_mit_schaetzung_und_satz(bestand):
    ep, _ = bestand
    uhr = Uhr()
    wand = [JETZT]
    steuerung = Steuerung(None, lambda: ep, uhr=uhr, wanduhr=lambda: wand[0], ruhe_s=0)
    leer = steuerung.stand(freigegeben=True, mit_modell=True)
    assert leer['zustand'] == 'laeuft' and leer['schaetzung'] is None and leer['schaetzung_text'] == 'noch unklar'
    assert leer['fortschritt'] == {'gesamt': 8, 'fertig': 0, 'offen': 8}
    # Eine Quelle je Stunde gemessen: acht offene brauchen acht Stunden.
    steuerung._zustand['proben'] = [[JETZT.timestamp() + i * 60, i / 60] for i in range(61)]
    stand = steuerung.stand(freigegeben=True, mit_modell=True)
    assert stand['rate_pro_stunde'] == pytest.approx(1.0)
    assert stand['schaetzung']['sekunden'] == pytest.approx(8 * 3600, rel=0.01)
    assert stand['schaetzung_text'] == wann_text(JETZT + timedelta(hours=8), JETZT)
    assert stand['satz'] == hintergrund.SATZ_ANBLEIBEN
    assert steuerung.stand(freigegeben=False, mit_modell=True)['zustand'] == 'aus'
    assert steuerung.stand(freigegeben=True, mit_modell=False)['zustand'] == 'ohne_modell'


def test_niedrige_prioritaet_nur_fuer_den_eigenen_faden():
    import os
    import sys
    if not sys.platform.startswith('linux'):
        pytest.skip('Fadenpriorität gibt es nur unter Linux')
    vorher_prozess = os.getpriority(os.PRIO_PROCESS, 0)
    ergebnis = {}

    def faden():
        vorher = os.getpriority(os.PRIO_PROCESS, threading.get_native_id())
        ergebnis['gesetzt'] = hintergrund.niedrige_prioritaet()
        ergebnis['nachher'] = os.getpriority(os.PRIO_PROCESS, threading.get_native_id())
        ergebnis['vorher'] = vorher

    t = threading.Thread(target=faden)
    t.start()
    t.join()
    assert ergebnis['gesetzt'] and ergebnis['nachher'] == min(19, ergebnis['vorher'] + 10)
    assert os.getpriority(os.PRIO_PROCESS, 0) == vorher_prozess  # die API bleibt, wie sie war


# -- Routen und Middleware ----------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.delenv('ICARUS_SIDECAR_TOKEN', raising=False)
    monkeypatch.setenv(hintergrund.RUHE_ENV, '20')
    anwendung = create_app(SelfModelStore(MemoryBackend(), 'test'))
    yield anwendung
    anwendung.state.scheduler.stop()


def test_routen_zeigen_zustand_und_pause_ueberdauert(app, tmp_path):
    client = TestClient(app)
    stand = client.get('/api/v1/hintergrund').json()
    assert set(stand) >= {'zustand', 'fortschritt', 'rate_pro_stunde', 'schaetzung', 'schlange', 'satz'}
    assert app.state.hintergrund.sperre() is None  # eine Abfrage ist keine Eingabe
    pausiert = client.post('/api/v1/hintergrund/pause').json()
    assert pausiert['pausiert'] is True
    assert (tmp_path / 'hintergrund.json').exists()
    assert Steuerung(tmp_path / 'hintergrund.json', lambda: None).pausiert
    assert client.post('/api/v1/hintergrund/weiter').json()['pausiert'] is False


def test_eingabe_der_oberflaeche_haelt_den_hintergrund_an(app):
    client = TestClient(app)
    assert client.post('/api/v1/hintergrund/aktiv').status_code == 204
    assert app.state.hintergrund.sperre() == 'nutzer'


def test_helfer_mit_token_zaehlen_nicht_als_mensch(app):
    client = TestClient(app, headers={'X-Icarus-Token': 'synthetisch'})
    client.post('/api/v1/autostart/helfer', json={'plattform': 'macos', 'eingerichtet': False})
    assert app.state.hintergrund.sperre() is None
