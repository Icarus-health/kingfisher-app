"""Lage im Server: Anzeige mit der Akte, Lauf im Zeitplan nur mit lokalem Modell und Freigabe."""
import json
from dataclasses import asdict

import pytest

from icarus_memory.lage_routes import PAKET, lagen_von, lauf
from icarus_memory.scheduler import JobResult, Scheduler
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_lage import LageModell, satz
from tests.test_mappe import _quelle
from tests.test_source_answers_http import _api

SACHE = 'person:a:anna@agentur.example'
BITTE = 'Bitte schicke mir die Druckdaten für das Plakat bis zum 20. Oktober 2099.'
STAND = 'Die Druckdaten für das Plakat sind seit dem 3. September 2026 freigegeben.'


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        yield app, client
    finally:
        client.close()


def seed(app, client):
    _quelle(app, 'Druckdaten', [(BITTE, 'request')], tage=3)
    _quelle(app, 'Freigabe', [(STAND, 'status')], tage=1)
    assert client.post('/api/v1/akten/aktualisieren').json()['offen'] == 0


def akte(client, **kwargs):
    antwort = client.get('/api/v1/akten/akte', params={'sache': SACHE, **kwargs})
    assert antwort.status_code == 200
    return antwort.json()


def nummer_von(messages, stichwort):
    """Die Belegnummer der ersten Zeile, deren Zitat das Stichwort enthält (das Modell liest die Nummern aus der Eingabe)."""
    import re
    for nummer, zitat in re.findall(r'\[(\d+)\] [^\n]*\n\s+([^\n]*)', messages[1]['content']):
        if stichwort in zitat:
            return int(nummer)
    raise AssertionError(stichwort)


def modell(app):
    return LageModell(lambda messages: {'saetze': [
        satz('Die Druckdaten für das Plakat sind freigegeben.', nummer_von(messages, 'freigegeben')),
        satz('Die Frist für die Druckdaten ist der 20.10.2099.', nummer_von(messages, 'Oktober 2099')),
        satz('Das Plakat kostet 900 Euro.', nummer_von(messages, 'freigegeben')),
    ]})


def schritt_von(app):
    from types import SimpleNamespace
    from icarus_memory.server import _wire_scheduler
    for name in ('consolidator', 'summarizer'):
        if not hasattr(app.state, name):
            setattr(app.state, name, SimpleNamespace(run=lambda **_: None))
    _wire_scheduler(app)
    return app.state.scheduler._run_lage


def erlaubt():
    return True


def test_akte_ohne_lage_ist_kein_fehler(api):
    app, client = api
    seed(app, client)
    daten = akte(client)
    assert daten['lage'] is None and daten['verlauf']['gesamt'] == 2


def test_lage_erscheint_mit_der_akte_mit_belegen_und_verworfenen_saetzen(api):
    app, client = api
    seed(app, client)
    m = modell(app)
    ergebnis = lauf(app, m, permitted=erlaubt)
    assert ergebnis.ok and '2 Lagen erstellt' in ergebnis.detail and '2 Sätze' in ergebnis.detail  # Person und Organisation
    lage = akte(client)['lage']
    assert [s['text'] for s in lage['saetze']] == ['Die Druckdaten für das Plakat sind freigegeben.',
                                                   'Die Frist für die Druckdaten ist der 20.10.2099.']
    assert lage['veraltet'] is False and lage['quellen'] == 2 and lage['verworfen'] == 1
    beleg = lage['saetze'][0]['belege'][0]
    assert beleg['titel'] == 'Freigabe' and beleg['episode_id']
    assert akte(client, alle=True)['lage']['veraltet'] is False  # „alle zeigen“ ändert die Lage nicht


def test_neue_quelle_macht_die_lage_veraltet_und_der_naechste_lauf_schreibt_sie_neu(api):
    app, client = api
    seed(app, client)
    m = modell(app)
    lauf(app, m, permitted=erlaubt)
    assert lauf(app, m, permitted=erlaubt).detail == 'Alle Lagen sind aktuell.'
    assert len(m.aufrufe) == 2  # Person und Organisation der Absenderin
    _quelle(app, 'Nachtrag', [('Die Druckdaten wurden nochmals geprüft.', 'status')], tage=0)
    client.post('/api/v1/akten/aktualisieren')
    lagen_von(app).mindestabstand_s = 0
    veraltet = akte(client)
    # Die neue Standmeldung überholt die alten Sätze: sie werden nicht mehr gezeigt, die Oberfläche weiß von der neuen Lage.
    assert veraltet['lage'] is None and veraltet['lage_wird_aktualisiert'] is True
    lauf(app, m, permitted=erlaubt)
    assert akte(client)['lage']['veraltet'] is False and len(m.aufrufe) == 4


def test_lauf_ohne_lokales_modell_oder_ohne_freigabe_ruft_nichts_auf(api):
    app, client = api
    seed(app, client)

    class Cloud(LageModell):
        is_local = False

    cloud = Cloud({'saetze': []})
    assert lauf(app, cloud, permitted=erlaubt).detail == 'Für die Lage wird ein lokales Modell benötigt.'
    assert lauf(app, None, permitted=erlaubt).ok
    lokal = modell(app)
    assert lauf(app, lokal, permitted=lambda: False).detail == 'Lage nach geänderter Freigabe gestoppt.'
    assert cloud.aufrufe == [] and lokal.aufrufe == []
    assert akte(client)['lage'] is None


def test_lauf_entzug_mitten_im_paket_stoppt(api):
    app, client = api
    seed(app, client)
    stand = {'n': 0}

    def permitted():
        stand['n'] += 1
        return stand['n'] < 3  # die Freigabe endet nach der Vorprüfung, vor dem ersten Modellaufruf

    m = modell(app)
    ergebnis = lauf(app, m, permitted=permitted)
    assert ergebnis.detail == 'Lage nach geänderter Freigabe gestoppt.' and m.aufrufe == []


def test_paketgroesse_ist_klein(api):
    app, client = api
    for n in range(4):
        _quelle(app, f'Mail {n}', [(f'Bitte melde dich zu Thema {n}.', 'request')], f'P{n} <p{n}@firma{n}.example>', tage=1)
    client.post('/api/v1/akten/aktualisieren')
    m = LageModell({'saetze': []})
    lauf(app, m, permitted=erlaubt)
    assert len(m.aufrufe) == PAKET == 2


def test_zeitplanschritt_ist_verdrahtet_und_pausiert_ohne_modellpruefung(api):
    app, client = api
    schritt = schritt_von(app)
    assert schritt(False) == JobResult('lage', True, 'Lagen pausiert: Modellprüfung ist ausgeschaltet.')
    seed(app, client)
    m = modell(app)
    app.state.agent._provider = m
    ergebnis = schritt(True)
    assert ergebnis.name == 'lage' and ergebnis.ok
    assert akte(client)['lage'] is not None


def test_zeitplanschritt_ohne_lokales_modell_lasst_die_quellen_zu_hause(api):
    app, client = api
    seed(app, client)
    m = modell(app)
    m.is_local = False
    app.state.agent._provider = m
    assert 'lokales Modell' in schritt_von(app)(True).detail
    assert m.aufrufe == [] and akte(client)['lage'] is None


def test_zeitplanschritt_mit_lokalpflicht_prueft_die_gewichte_und_faellt_bei_fehlen_zu(api, monkeypatch):
    """Mit `local_model_only` wird der Anbieter in `VerifiedLocalProvider` gepackt: erst prüfen, dann erst Quellen senden."""
    from icarus_memory.local_model_guard import LocalModelIdentity
    from icarus_memory.providers import ProviderError
    app, client = api
    seed(app, client)
    app.state.settings.schedule.local_model_only = True
    m = modell(app)
    app.state.agent._provider = m

    def unbestaetigt(provider):
        raise ProviderError('nicht bestätigt')

    monkeypatch.setattr('icarus_memory.local_model_guard.verify_local_model', unbestaetigt)
    ergebnis = schritt_von(app)(True)
    assert m.aufrufe == [] and not ergebnis.ok
    assert akte(client)['lage'] is None
    monkeypatch.setattr('icarus_memory.local_model_guard.verify_local_model',
                        lambda provider: LocalModelIdentity(provider.model, 'a' * 64))
    lagen_von(app).verwerfen()
    lagen_von(app)._fehler.clear()
    assert schritt_von(app)(True).ok and m.aufrufe
    assert akte(client)['lage'] is not None


def test_zeitplanschritt_stoppt_bei_geaenderter_freigabe(api):
    app, client = api
    seed(app, client)
    m = LageModell(None)

    def antwort(messages):
        app.state.settings.schedule.local_model_only = not app.state.settings.schedule.local_model_only
        return {'saetze': [satz('Die Druckdaten für das Plakat sind freigegeben.', 1)]}

    m.antwort = antwort
    app.state.agent._provider = m
    schritt_von(app)(True)
    assert akte(client)['lage'] is None  # Plan geändert, während das Modell rechnete: nichts gespeichert


def test_scheduler_ruft_lage_im_durchgang_und_faengt_fehler():
    s = Scheduler()
    s._run_lage = lambda modell: JobResult('lage', True, f'mit_modell={modell}')
    bericht = s.run_once(with_model=True)
    assert [(j.name, j.detail) for j in bericht.jobs] == [('lage', 'mit_modell=True')]

    def kaputt(modell):
        raise RuntimeError('geheimer Quelltext')

    s._run_lage = kaputt
    job = s.run_once(with_model=True).jobs[0]
    assert (job.name, job.ok) == ('lage', False) and 'geheimer' not in job.detail


def test_hintergrundschritt_nur_mit_zeitplan_und_modellfreigabe_und_ohne_dringenderes():
    s = Scheduler()
    aufrufe = []
    s._run_lage = lambda modell: aufrufe.append(modell) or JobResult('lage')
    s._run_background_lage()
    assert aufrufe == []  # Zeitplan aus
    s.configure(enabled=True, with_model=False)
    s._run_background_lage()
    assert aufrufe == []  # Modellprüfung aus
    s.configure(with_model=True)
    s._memory_pending['e-1'] = None
    s._run_background_lage()
    assert aufrufe == []  # Einordnung neuer Quellen hat Vorrang
    s._memory_pending.clear()
    s._stop.set()
    s._run_background_lage()
    assert aufrufe == []
    s._stop.clear()
    s._run_background_lage()
    assert aufrufe == [True]


def test_hintergrundschritt_teilt_sich_die_sperre_und_startet_keinen_eigenen_thread():
    import threading
    s = Scheduler()
    s.configure(enabled=True, with_model=True)
    aufrufe = []
    s._run_lage = lambda modell: aufrufe.append(threading.current_thread().name) or JobResult('lage')
    with s._run_lock:
        s._run_background_lage()  # ein anderer Lauf hält die Sperre: kein Warten, kein zweiter Modellaufruf
    assert aufrufe == []
    s._run_background_lage()
    assert aufrufe == [threading.current_thread().name]


def test_lauf_meldet_keine_quelldaten_bei_fehlern(api):
    app, client = api
    seed(app, client)
    m = LageModell(RuntimeError('Inhalt der Quelle: geheim'))
    ergebnis = lauf(app, m, permitted=erlaubt)
    assert not ergebnis.ok and 'geheim' not in ergebnis.detail
    assert json.dumps(asdict(ergebnis)).count('Druckdaten') == 0
