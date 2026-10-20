"""Die Pause trennt ältere Mails von neuer Post (docs/46-hintergrund.md, „Pause und Akku“).

Früher hielt die Pause (und ebenso der Akkubetrieb) alles an: neue Post, Kalenderabgleich, geplante Sicherung, die
Übernahme des Mac-Kalenders. Ein Stabschef, der in der Pause die Post von heute liegen lässt, verliert etwas. Jetzt
halten Pause und Akku nur die älteren Mails (den Altbestand) und jede Modellarbeit an; neue Post, der Kalenderabgleich
und die geplante Sicherung laufen ohne Modell weiter. Unverändert halten alles an: knapper Speicherplatz, Speicherdruck
des Macs und die Rücksicht auf den Menschen (Eingabe, Antwort). Nur synthetische Daten.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from icarus_memory.connectors.mail import Message
from icarus_memory.episodes import EpisodeStore
from icarus_memory.hintergrund import Steuerung
from icarus_memory.host_power import HostPower
from icarus_memory.mail_intake import Intake
from icarus_memory.model import now
from icarus_memory.scheduler import JobResult, Scheduler
from tests.imap_attrappe import probe_mail
from tests.test_mail_intake import Reader
from tests.test_mailaufnahme_ende_zu_ende import client, einlesen_starten, hintergrund_takte, postfach  # noqa: F401


# -- Die Aufnahme: nur neue Post -------------------------------------------------------------------------------------

def _uids(ep, lane, status='captured'):
    with ep._lock:
        return [u for (u,) in ep._conn.execute(
            'SELECT uid FROM mail_intake_items WHERE lane=? AND status=? ORDER BY uid', (lane, status))]


def _ordner(ep):
    with ep._lock:
        return dict(ep._conn.execute('SELECT * FROM mail_intake_folders').fetchone())


def test_nur_neue_post_holt_neue_post_und_laesst_aeltere_liegen(tmp_path):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake, r = Intake(ep), Reader()
    r.count = 50
    intake.start('a', ['INBOX'])
    intake.step('a', r, batch=2)
    vorher_verlauf, vorher_ordner = _uids(ep, 'history'), _ordner(ep)
    r.count = 52
    for _ in range(3):
        intake.step('a', r, batch=8, nur_neu=True)
    assert _uids(ep, 'live') == [51, 52]
    assert _uids(ep, 'history') == vorher_verlauf, 'kein älterer Mail geholt'
    nachher = _ordner(ep)
    assert (nachher['scan_uid'], nachher['upper_uid'], nachher['inventory_complete']) == \
        (vorher_ordner['scan_uid'], vorher_ordner['upper_uid'], vorher_ordner['inventory_complete'])
    # Gegenbeispiel: ohne Pause geht es mit den älteren Mails weiter.
    intake.step('a', r, batch=8)
    assert len(_uids(ep, 'history')) > len(vorher_verlauf)
    ep.close()


def test_in_der_pause_begonnenes_einlesen_holt_ab_dann_neue_post(tmp_path):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake, r = Intake(ep), Reader()
    r.count = 30
    intake.start('a', ['INBOX'])
    intake.step('a', r, batch=8, nur_neu=True)
    ordner = _ordner(ep)
    assert ordner['generation'] == '7' and ordner['live_uid'] == 30 and not ordner['inventory_complete']
    with ep._lock:
        assert ep._conn.execute('SELECT COUNT(*) FROM mail_intake_items').fetchone()[0] == 0
    r.count = 31
    intake.step('a', r, batch=8, nur_neu=True)
    assert _uids(ep, 'live') == [31] and _uids(ep, 'history') == []
    # Nach der Pause: der ganze Bestand bis 30, ohne Lücke und ohne die neue Mail doppelt.
    for _ in range(10):
        intake.step('a', r, batch=8)
    assert _uids(ep, 'history') == list(range(1, 31)) and _uids(ep, 'live') == [31]
    ep.close()


def test_neue_post_mit_gescanntem_anhang_wartet_auf_die_texterkennung(tmp_path):
    from dataclasses import replace
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake, r = Intake(ep), Reader()
    r.count = 2
    intake.start('a', ['INBOX'])
    intake.step('a', r, batch=8)
    r.count = 4
    gescannt = {'7.3'}

    class MitAnhang(Reader):
        count = 4

        def message_in_folder(self, folder, uid):
            nachricht = super().message_in_folder(folder, uid)
            return replace(nachricht, anhaenge=('scan',)) if uid in gescannt else nachricht
    leser = MitAnhang()
    intake.step('a', leser, batch=8, nur_neu=True, zurueckstellen=lambda nachricht: bool(nachricht.anhaenge))
    assert _uids(ep, 'live') == [4] and _uids(ep, 'live', 'pending') == [3]
    with ep._lock:
        attempts = ep._conn.execute('SELECT attempts FROM mail_intake_items WHERE uid=3').fetchone()[0]
    assert attempts == 0, 'zurückgestellt ist nicht gescheitert'
    ep.close()


# -- Der Zeitplan ----------------------------------------------------------------------------------------------------

def _zeitplan(monkeypatch, steuerung, aufrufe):
    monkeypatch.setattr('icarus_memory.scheduler.TICK_SECONDS', 0.02)
    steuerung.probe = lambda: None
    steuerung.dringend_offen = lambda: False
    steuerung.naechste_quellen = lambda *a, **k: ['synthetische-quelle']
    steuerung.wartezeit = lambda: 0.02
    s = Scheduler()

    def merke(name, ergebnis=None):
        def aufruf(*a, **k):
            aufrufe.append(name)
            return ergebnis
        return aufruf
    s._run_mail_intake = merke('aeltere_mails')
    s._run_neue_post = merke('neue_post')
    s._run_kalender = merke('kalender', [JobResult('kalender:synthetisch', True, 'Termine unverändert')])
    s._run_backup = merke('sicherung', JobResult('sicherung', True, 'synthetisch'))
    s._run_ingest = merke('voller_lauf', [])
    s._run_working_memory = merke('modell', JobResult('gedaechtnis'))
    s._run_lage = merke('modell', JobResult('lage'))
    s._run_task_detection = merke('modell', JobResult('zusagen'))
    s._run_priority_tasks = merke('modell', JobResult('zusagen'))
    s.configure(enabled=True, with_model=True, interval_minutes=15)
    s.anschliessen(steuerung)
    s._last_at = now() - timedelta(hours=1)  # der volle Durchgang (und damit Kalender und Sicherung) ist fällig
    return s


def _warten(bedingung, sekunden=3.0):
    ende = time.monotonic() + sekunden
    while time.monotonic() < ende:
        if bedingung():
            return True
        time.sleep(0.01)
    return False


def _gesperrt_durch(tmp_path, art):
    if art == 'pausiert':
        steuerung = Steuerung(None, lambda: None, ruhe_s=0)
        steuerung.pausieren(True)
        return steuerung
    power = HostPower(tmp_path, expected=lambda: True)
    if art == 'akku':
        power.report('battery', memory_pressure='normal')
    elif art == 'speicherdruck':
        power.report('ac', memory_pressure='warning')
    # 'energie_unbekannt': keine Meldung der App
    return Steuerung(None, lambda: None, ruhe_s=0, external_gate=power.reason)


@pytest.mark.parametrize('art', ['pausiert', 'akku', 'energie_unbekannt'])
def test_pause_und_akku_lassen_neue_post_kalender_und_sicherung_ohne_modell_weiterlaufen(tmp_path, monkeypatch, art):
    steuerung = _gesperrt_durch(tmp_path, art)
    aufrufe = []
    s = _zeitplan(monkeypatch, steuerung, aufrufe)
    letzter_voller = s._last_at
    s.start()
    try:
        assert _warten(lambda: {'neue_post', 'kalender', 'sicherung'} <= set(aufrufe)), aufrufe
        time.sleep(0.2)  # viele Takte
    finally:
        s.stop()
    assert not {'aeltere_mails', 'modell', 'voller_lauf'} & set(aufrufe), aufrufe
    # Kalender und Sicherung im Abstand des Zeitplans, nicht in jedem Takt; der volle Durchgang bleibt fällig.
    assert aufrufe.count('kalender') == 1 and aufrufe.count('sicherung') == 1
    assert s._last_at == letzter_voller
    assert s.state()['last_run']['jobs'][0]['name'] == 'kalender:synthetisch'


@pytest.mark.parametrize('art', ['speicherdruck'])
def test_speicherdruck_haelt_weiter_alles_an(tmp_path, monkeypatch, art):
    steuerung = _gesperrt_durch(tmp_path, art)
    aufrufe = []
    s = _zeitplan(monkeypatch, steuerung, aufrufe)
    s.start()
    try:
        time.sleep(0.3)
    finally:
        s.stop()
    assert aufrufe == []


def test_speicherplatz_haelt_weiter_alles_an(tmp_path, monkeypatch):
    steuerung = _gesperrt_durch(tmp_path, 'pausiert')
    aufrufe = []
    s = _zeitplan(monkeypatch, steuerung, aufrufe)
    s._capacity_gate = lambda: 'storage_low'
    s.start()
    try:
        time.sleep(0.3)
    finally:
        s.stop()
    assert aufrufe == []


def test_auch_in_der_pause_wartet_alles_solange_der_mensch_arbeitet(monkeypatch):
    steuerung = Steuerung(None, lambda: None, ruhe_s=60)
    steuerung.pausieren(True)
    steuerung.aktivitaet.eingabe()
    aufrufe = []
    s = _zeitplan(monkeypatch, steuerung, aufrufe)
    s.start()
    try:
        time.sleep(0.3)
    finally:
        s.stop()
    assert aufrufe == []
    with steuerung.aktivitaet.antwort():
        assert steuerung.sperre_ohne_modell() == 'antwort'


def test_nach_weiter_kommen_aeltere_mails_und_modell_wieder_dran(tmp_path, monkeypatch):
    steuerung = _gesperrt_durch(tmp_path, 'pausiert')
    aufrufe = []
    s = _zeitplan(monkeypatch, steuerung, aufrufe)
    s.start()
    try:
        assert _warten(lambda: 'neue_post' in aufrufe)
        steuerung.pausieren(False)
        s.wecken()
        assert _warten(lambda: {'aeltere_mails', 'voller_lauf', 'modell'} <= set(aufrufe)), aufrufe
    finally:
        s.stop()


def test_ein_neustart_nach_dem_update_setzt_aeltere_mails_nicht_fort(tmp_path, monkeypatch):
    datei = tmp_path / 'hintergrund.json'
    Steuerung(datei, lambda: None, ruhe_s=0).pausieren(True)
    nach_dem_update = Steuerung(datei, lambda: None, ruhe_s=0)
    aufrufe = []
    s = _zeitplan(monkeypatch, nach_dem_update, aufrufe)
    s.start()
    try:
        assert _warten(lambda: 'neue_post' in aufrufe)
        time.sleep(0.1)
    finally:
        s.stop()
    assert 'aeltere_mails' not in aufrufe and 'modell' not in aufrufe


def test_sperre_ohne_modell_kennt_nur_was_auch_neue_post_anhaelt(tmp_path):
    for art, erwartet in (('pausiert', None), ('akku', None), ('energie_unbekannt', None),
                          ('speicherdruck', 'speicherdruck')):
        steuerung = _gesperrt_durch(tmp_path / art, art)
        assert steuerung.sperre() is not None
        assert steuerung.sperre_ohne_modell() == erwartet, art


# -- Der ganze Weg: Postfach, Pause, neue Post, Stand -----------------------------------------------------------------

SATZ_PAUSE = ('Postfach Probe-Post: Neue Post wird weiter geholt; ältere Mails sind pausiert (bisher 0 Mails gelesen). '
              'Auf Heute geht es mit „Weiter“ weiter.')


def _titel(client):
    return {e['title'] for e in client.get('/episodes', params={'limit': 50}).json() if e['kind'] == 'message'}


def test_pause_holt_neue_post_und_sagt_es(client, postfach):
    konto = einlesen_starten(client, postfach)
    assert client.post('/api/v1/hintergrund/pause').json()['pausiert']
    zeitplan = client.app.state.scheduler
    zeitplan.stop()
    zeitplan._run_neue_post()
    assert _titel(client) == set()
    stand = next(a for a in client.get('/api/v1/mail/stand').json()['accounts'] if a['account_id'] == konto)
    assert stand['zustand'] == 'pausiert' and stand['satz'] == SATZ_PAUSE, stand
    einlesen = next(a for a in client.get('/api/v1/mail/intake').json()['accounts'] if a['account_id'] == konto)
    assert einlesen['stand']['satz'] == SATZ_PAUSE

    postfach.nachrichten.append(probe_mail('Anna Berg <anna.berg@example.org>', 'Neu: Treffpunkt geändert',
                                           'Lena, wir treffen uns am Eingang.\n\nAnna', minuten=90))
    zeitplan._run_neue_post()
    assert _titel(client) == {'Neu: Treffpunkt geändert'}

    # Weiter: Jetzt kommen die älteren Mails dran, ohne die neue doppelt.
    assert client.post('/api/v1/hintergrund/weiter').json()['pausiert'] is False
    hintergrund_takte(client, 3)
    titel = _titel(client)
    assert {'Treffen am Montag', 'Neu: Treffpunkt geändert'} <= titel
    assert len([e for e in client.get('/episodes', params={'limit': 50}).json() if e['title'] == 'Neu: Treffpunkt geändert']) == 1


def test_im_akkubetrieb_sagt_der_stand_dasselbe_ohne_weiter_knopf(client, postfach):
    konto = einlesen_starten(client, postfach)
    client.app.state.hintergrund.external_gate = lambda: 'akku'
    stand = next(a for a in client.get('/api/v1/mail/stand').json()['accounts'] if a['account_id'] == konto)
    assert stand['zustand'] == 'wartet'
    assert stand['satz'] == ('Postfach Probe-Post: Neue Post wird weiter geholt; ältere Mails warten, bis der Mac am '
                             'Netzteil ist (bisher 0 Mails gelesen).')


def test_mit_ki_filter_sagt_der_satz_dass_auch_neue_post_wartet(client, postfach):
    konto = einlesen_starten(client, postfach)
    client.app.state.settings.mail_filter = {**client.app.state.settings.mail_filter, 'ai_enabled': True}
    client.post('/api/v1/hintergrund/pause')
    stand = next(a for a in client.get('/api/v1/mail/stand').json()['accounts'] if a['account_id'] == konto)
    assert stand['satz'].startswith('Postfach Probe-Post: Neue Post und ältere Mails sind pausiert, weil die lokale KI '
                                    'neue Post vor dem Speichern prüft'), stand['satz']


def test_mit_ki_filter_wartet_neue_post_ohne_modell_statt_zur_pruefung(client, postfach):
    einlesen_starten(client, postfach)
    hintergrund_takte(client, 3)  # der Bestand ist gelesen, die Grenze für neue Post steht
    vorher = _titel(client)
    zur_pruefung = set(client.app.state.settings.mail_filter.get('pending') or {})  # der Newsletter des Bestands
    client.app.state.settings.mail_filter = {**client.app.state.settings.mail_filter, 'ai_enabled': True}
    client.post('/api/v1/hintergrund/pause')
    zeitplan = client.app.state.scheduler
    zeitplan.stop()
    postfach.nachrichten.append(probe_mail('Anna Berg <anna.berg@example.org>', 'Neu: Treffpunkt geändert',
                                           'Lena, wir treffen uns am Eingang.', minuten=90))
    zeitplan._run_neue_post()
    assert _titel(client) == vorher, 'die lokale KI prüft neue Post vor dem Speichern; ohne Modell wartet sie'
    # Wartet heißt: nicht zur Prüfung beiseitegelegt (das bliebe Arbeit für den Menschen), sondern noch nicht geholt.
    assert set(client.app.state.settings.mail_filter.get('pending') or {}) == zur_pruefung
    with client.app.state.episodes._lock:
        assert client.app.state.episodes._conn.execute(
            "SELECT COUNT(*) FROM mail_intake_items WHERE lane='live'").fetchone()[0] == 0


def test_pause_hat_ihren_satz_in_der_karte_auch_ohne_modell(client, postfach):
    einlesen_starten(client, postfach)
    stand = client.post('/api/v1/hintergrund/pause').json()
    assert stand['zustand'] == 'ohne_modell' and stand['pausiert']
    assert stand['grund'] == ('Pausiert. Neue Post und Termine kommen weiter an; ältere Mails und das Lernen warten, '
                              'bis du „Weiter“ wählst.')


def test_bei_speicherdruck_verspricht_der_satz_keine_neue_post(client, postfach):
    konto = einlesen_starten(client, postfach)
    client.post('/api/v1/hintergrund/pause')
    client.app.state.hintergrund.external_gate = lambda: 'speicherdruck'
    stand = next(a for a in client.get('/api/v1/mail/stand').json()['accounts'] if a['account_id'] == konto)
    assert stand['zustand'] == 'pausiert' and 'Neue Post' not in stand['satz'], stand['satz']


def test_ohne_modell_auch_keine_texterkennung_und_gescanntes_wartet(client, postfach, monkeypatch):
    einlesen_starten(client, postfach)
    texterkennung = lambda bild: 'synthetisch'  # noqa: E731 - ein OCR-Modell wäre da
    monkeypatch.setattr('icarus_memory.anhaenge.ocr_fuer', lambda app: texterkennung)
    gesehen = []

    def schritt(self, account, reader, settings, **kwargs):
        gesehen.append((reader.ocr, kwargs['nur_neu'], kwargs['zurueckstellen']))
        return []
    monkeypatch.setattr('icarus_memory.mail_intake.Intake.background_step', schritt)
    zeitplan = client.app.state.scheduler
    zeitplan.stop()
    zeitplan._run_neue_post()
    ocr, nur_neu, zurueckstellen = gesehen[-1]
    assert ocr is None and nur_neu is True and zurueckstellen is not None
    gescannt = Message('7.9', 'Rechnung', 'a@example.org', None, '', False,
                       anhaenge=(SimpleNamespace(status='gescannt'),))
    assert zurueckstellen(gescannt) and not zurueckstellen(Message('7.8', 'Text', 'a@example.org', None, '', False))
    # Gegenbeispiel: ohne Pause liest die Texterkennung mit, und nichts wird zurückgestellt.
    zeitplan._run_mail_intake()
    assert gesehen[-1] == (texterkennung, False, None)


# -- Befunde des Reviews: Pausieren mitten in einer Modellarbeit, Speicherdruck, ehrlicher Grund ------------------------

def test_pausieren_mitten_in_einer_modellarbeit_gibt_den_zeitplan_frei(monkeypatch):
    # Vorher wartete der zweite Ampel-Aufruf bis „Weiter“: Sperren blieben gehalten, und keine neue Post kam.
    from icarus_memory.hintergrund import ModellAmpel
    monkeypatch.setattr('icarus_memory.scheduler.TICK_SECONDS', 0.02)
    ampel = ModellAmpel()
    steuerung = Steuerung(None, lambda: None, ruhe_s=0)
    steuerung.wartezeit = lambda: 0.02
    s = Scheduler()
    s.anschliessen(steuerung)
    s.configure(enabled=True, with_model=True)
    s._last_at = now()
    aufrufe = []
    s._run_neue_post = lambda: aufrufe.append('neue_post')

    def paket(ids):
        with ampel.aufruf():
            aufrufe.append('erster')
        steuerung.pausieren(True)
        with ampel.aufruf():
            aufrufe.append('zweiter')
        return JobResult('synthetisch')
    s._run_prompt_working_memory = paket
    s.start()
    try:
        assert s.request_working_memory('synthetische-quelle')
        assert _warten(lambda: 'neue_post' in aufrufe, 2), aufrufe
        assert 'zweiter' not in aufrufe
        assert s._run_lock.acquire(timeout=1)
        s._run_lock.release()
    finally:
        s.stop()


@pytest.mark.parametrize('quelle, druck', [('battery', 'critical'), ('battery', 'warning'), ('unknown', 'critical')])
def test_speicherdruck_geht_der_energiequelle_vor(tmp_path, monkeypatch, quelle, druck):
    power = HostPower(tmp_path, expected=lambda: True)
    power.report(quelle, memory_pressure=druck)
    assert power.reason() == 'speicherdruck'
    steuerung = Steuerung(None, lambda: None, ruhe_s=0, external_gate=power.reason)
    assert steuerung.sperre_ohne_modell() == 'speicherdruck'
    aufrufe = []
    s = _zeitplan(monkeypatch, steuerung, aufrufe)
    s.start()
    try:
        time.sleep(0.3)
    finally:
        s.stop()
    assert aufrufe == []


@pytest.mark.parametrize('extern, ki, erwartet, nicht', [
    (None, False, 'Neue Post und Termine kommen weiter an', None),
    ('speicherdruck', False, 'Arbeitsspeicher', 'Neue Post und Termine kommen weiter an'),
    ('storage_low', False, None, 'Neue Post und Termine kommen weiter an'),
    ('speicher_unbekannt', False, 'Speicherlast', 'Neue Post und Termine kommen weiter an'),
    (None, True, 'Termine kommen weiter an; neue Post', 'Neue Post und Termine kommen weiter an'),
])
def test_der_grund_der_pause_verspricht_nur_was_weiterlaeuft(extern, ki, erwartet, nicht):
    from icarus_memory.storage_capacity import MESSAGES
    if extern == 'storage_low':
        extern = next(iter(MESSAGES))
    steuerung = Steuerung(None, lambda: None, ruhe_s=0, external_gate=lambda: extern)
    steuerung.pausieren(True)
    satz = steuerung.grund_text('pausiert', ki_filter=ki)
    assert satz.startswith('Pausiert')
    if erwartet:
        assert erwartet in satz, satz
    if nicht:
        assert nicht not in satz, satz
    stand = steuerung.stand(freigegeben=True, mit_modell=False, ki_filter=ki)
    assert stand['grund'] == satz


def test_akku_mit_ki_filter_verspricht_keine_neue_post():
    steuerung = Steuerung(None, lambda: None, ruhe_s=0, external_gate=lambda: 'akku')
    satz = steuerung.grund_text('akku', ki_filter=True)
    assert 'Termine weiter an' in satz and 'neue Post' in satz and 'Neue Post und Termine' not in satz


def test_modellarbeit_im_hintergrund_haelt_nach_pausieren_an_auch_ohne_ampel(client, monkeypatch):
    # Anbieter, die nicht über die Ampel laufen (etwa entfernte), fragen `permitted()` zwischen den Quellen.
    from icarus_memory.hintergrund import als_hintergrund
    gesehen = []
    monkeypatch.setattr('icarus_memory.working_memory_worker.run',
                        lambda *a, **k: gesehen.append(k['permitted']) or JobResult('gedaechtnis'))
    monkeypatch.setattr('icarus_memory.memory_categories.Categories.run',
                        lambda self, *a, **k: gesehen.append(k['permitted']))
    monkeypatch.setattr('icarus_memory.lage_routes.lauf', lambda *a, **k: gesehen.append(k['permitted']) or JobResult('lage'))
    zeitplan = client.app.state.scheduler
    zeitplan.stop()
    steuerung = client.app.state.hintergrund
    ergebnis = {}

    def im_faden():
        with als_hintergrund(steuerung.sperre):
            zeitplan._run_working_memory(True)
            zeitplan._run_lage(True)
            ergebnis['frei'] = [erlaubt() for erlaubt in gesehen]
            steuerung.pausieren(True)
            ergebnis['pausiert'] = [erlaubt() for erlaubt in gesehen]
    faden = threading.Thread(target=im_faden)
    faden.start()
    faden.join(5)
    assert len(gesehen) == 3 and all(ergebnis['frei']) and not any(ergebnis['pausiert'])
    # Ein ausdrücklicher Lauf („Jetzt ausführen“) außerhalb des Zeitplanfadens bleibt erlaubt.
    assert all(erlaubt() for erlaubt in gesehen)
    steuerung.pausieren(False)
