"""Paket D der Persona-Prüfung (26.10.2026): Widerruf sofort wirksam, Webabruf nur mit Freigabe, ehrliche Sätze.

Alles synthetisch; die Cloud ist eine Attrappe, die jede Anfrage zählt, die sie bekommen hätte.
"""
import copy
import json
import socket
import threading

import pytest

from icarus_memory import gedaechtnis_cloud, logbuch, nach_draussen, welt_feeds
from icarus_memory.model_roles import ROLLEN
from icarus_memory.policy import ActionClass, ApprovalLevel, Policy
from icarus_memory.providers import Reply, ToolCall
from icarus_memory.tools import build_registry
from tests.test_context_identity import core  # noqa: F401  (Fixture)
from tests.test_conversation_retraction import _close_app
from tests.test_model_roles_routes import app_und_client  # noqa: F401  (Fixture)
from tests.test_source_answers_http import _api, _conversation

EINWILLIGUNG = '2026-10-26T09:00:00+00:00'
WAHL = {'modell': '', 'cloud': True, 'anbieter': 'anthropic', 'cloud_einwilligung': EINWILLIGUNG}
AUS = {'modell': '', 'cloud': False, 'anbieter': '', 'cloud_einwilligung': ''}
FRAGE = 'Wie spät ist es gerade beim Projekt ORKA-17?'


class CloudGespraech:
    """Attrappe der Cloud im Gespräch: zuerst ein Werkzeugaufruf, danach Text. Zählt jede Anfrage."""

    name = 'anthropic'
    model = 'synthetisch-cloud'
    is_local = False

    def __init__(self, werkzeug='aktuelle_zeit', argumente=None, rolle='antwort'):
        self.calls = []
        self.werkzeug = werkzeug
        self.argumente = argumente or {}
        self.nach_erstem = None
        self.cloud_einwilligung = gedaechtnis_cloud.markierung(rolle, 'anthropic', EINWILLIGUNG)

    def complete(self, messages, tools):
        self.calls.append(copy.deepcopy(messages))
        if len(self.calls) == 1:
            if self.nach_erstem:
                self.nach_erstem()
            return Reply(text='', tool_calls=[ToolCall(id='t1', name=self.werkzeug, arguments=dict(self.argumente))])
        return Reply(text='Cloud-Attrappe: fertig.')


def _gespraech(core, tmp_path, monkeypatch, *, wahl=WAHL, cloud=None, werkzeuge=('aktuelle_zeit',)):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    cloud = cloud or CloudGespraech()
    agent = app.state.agent
    agent._provider = cloud
    agent._max_rounds = 4
    alle = build_registry(agent._store)
    agent._tools = {name: alle[name] for name in werkzeuge}
    app.state.settings.model_roles = {'antwort': dict(wahl)} if wahl is not None else {}
    return app, client, cloud


def _chat(client, frage=FRAGE):
    antwort = client.post(f'/api/v1/conversations/{_conversation(client)}/messages',
                          json={'message': frage, 'answer_mode': 'chat'})
    assert antwort.status_code == 201, antwort.text
    return antwort.json()


# -- D1: Widerruf sofort wirksam ------------------------------------------------------------------------------------


def test_widerruf_wartet_nicht_auf_eine_laufende_antwort(app_und_client):
    """Die Persona sah den Schalter 12 s auf „an“: der Widerruf wartete auf die Sperre der laufenden Antwort."""
    app, client = app_und_client
    assert client.put('/api/v1/models/roles/antwort',
                      json={'cloud': True, 'anbieter': 'anthropic', 'einwilligung': True}).status_code == 200
    ergebnis = {}
    app.state.conversation_lock.acquire()  # eine Antwort läuft gerade
    try:
        faden = threading.Thread(target=lambda: ergebnis.setdefault(
            'antwort', client.put('/api/v1/models/roles/antwort', json={'cloud': False})))
        faden.start()
        faden.join(5)
        assert not faden.is_alive(), 'Der Widerruf wartet auf die laufende Antwort.'
        assert ergebnis['antwort'].status_code == 200
        assert 'antwort' not in app.state.settings.model_roles
    finally:
        app.state.conversation_lock.release()
        faden.join(10)


def test_einschalten_wartet_weiter_auf_die_laufende_antwort(app_und_client):
    """Nur das Engere wartet nicht: Eine neue Einwilligung mitten in einer Antwort wartet wie bisher."""
    app, client = app_und_client
    ergebnis = {}
    app.state.conversation_lock.acquire()
    try:
        faden = threading.Thread(target=lambda: ergebnis.setdefault('antwort', client.put(
            '/api/v1/models/roles/antwort', json={'cloud': True, 'anbieter': 'anthropic', 'einwilligung': True})))
        faden.start()
        faden.join(0.5)
        assert faden.is_alive()
    finally:
        app.state.conversation_lock.release()
        faden.join(10)
    assert ergebnis['antwort'].status_code == 200


def test_widerruf_zwischen_zwei_werkzeugrunden_sendet_nichts_mehr(core, tmp_path, monkeypatch):
    app, client, cloud = _gespraech(core, tmp_path, monkeypatch)
    cloud.nach_erstem = lambda: app.state.settings.model_roles.update(antwort=dict(AUS))
    try:
        antwort = _chat(client)['messages'][-1]
        assert len(cloud.calls) == 1, 'Nach dem Widerruf ging noch eine Anfrage an den Anbieter.'
        assert 'Cloud ist ausgeschaltet' in antwort['content']
        assert antwort['metadata']['context'].get('cloud_widerrufen') is True
    finally:
        client.close()
        _close_app(app)


@pytest.mark.parametrize('wahl', [
    None, dict(AUS), {**WAHL, 'cloud_einwilligung': ''}, {**WAHL, 'cloud_einwilligung': '2026-10-27T09:00:00+00:00'},
    {**WAHL, 'anbieter': 'openai'}, {**WAHL, 'local_only': True},
])
def test_gespraech_ohne_gueltige_einwilligung_sendet_keine_einzige_anfrage(core, tmp_path, monkeypatch, wahl):
    app, client, cloud = _gespraech(core, tmp_path, monkeypatch, wahl=wahl)
    try:
        antwort = _chat(client)['messages'][-1]
        assert cloud.calls == []
        assert 'Cloud ist ausgeschaltet' in antwort['content']
    finally:
        client.close()
        _close_app(app)


def test_gespraech_ueber_die_cloud_ist_leise_erkennbar_und_protokolliert(core, tmp_path, monkeypatch):
    app, client, cloud = _gespraech(core, tmp_path, monkeypatch)
    try:
        antwort = _chat(client)['messages'][-1]
        assert len(cloud.calls) == 2  # Werkzeugrunde und Antwort, beide mit gültiger Einwilligung
        assert antwort['metadata']['context']['cloud_antwort'] == {'anbieter': 'anthropic', 'modell': 'synthetisch-cloud'}
        # Das Protokoll sagt, was wann an wen ging, ohne Inhalte.
        eintraege = [e for e in app.state.logbuch.ereignisse(0) if e.art == 'cloud_anfrage']
        assert len(eintraege) == 2
        assert eintraege[0].daten['anbieter'] == 'anthropic' and eintraege[0].daten['wofuer'] == 'gespraech'
        roh = json.dumps([e.daten for e in eintraege], ensure_ascii=False)
        assert 'ORKA' not in roh and 'spät' not in roh
        protokoll = client.get('/api/v1/cloud/protokoll').json()
        assert protokoll['eintraege'][0]['anbieter'] == 'Anthropic (USA)'
        assert 'Gespräch' in protokoll['eintraege'][0]['satz']
        assert 'ORKA' not in json.dumps(protokoll, ensure_ascii=False)
    finally:
        client.close()
        _close_app(app)


def test_fragen_verstehen_prueft_die_einwilligung_vor_dem_versand(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    frage_cloud = CloudGespraech(rolle='frage')
    agent = app.state.agent
    agent._frage_anbieter = lambda: frage_cloud
    app.state.settings.model_roles = {'frage': dict(AUS)}
    try:
        anfrage = agent.frage_verstehen('Was gibt es Neues zu ORKA-17?')
        assert frage_cloud.calls == []
        assert anfrage is not None  # der Rückfall ohne Modell versteht die Frage
    finally:
        client.close()
        _close_app(app)


def test_gedaechtnisweg_protokolliert_jeden_versand(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.settings.model_roles = {'antwort': dict(WAHL)}
        cloud = CloudGespraech()
        agent = app.state.agent
        agent._provider = cloud
        eingegrenzt = agent._gedaechtnis_anbieter()
        assert eingegrenzt is not None
        with pytest.raises(Exception):
            eingegrenzt.complete_json([{'role': 'user', 'content': 'x'}], schema={'type': 'object'})
        eintraege = [e for e in app.state.logbuch.ereignisse(0) if e.art == 'cloud_anfrage']
        assert [e.daten['wofuer'] for e in eintraege] == ['gedaechtnis']
    finally:
        client.close()
        _close_app(app)


# -- D2: Webabruf nur mit sichtbarer Freigabe -------------------------------------------------------------------------


def test_webabruf_braucht_immer_eine_freigabe_mit_einem_klick():
    policy = Policy()
    sauber = policy.decide('web_abruf', ActionClass.READ, {'url': 'https://example.org/'})
    assert sauber.level is ApprovalLevel.CONFIRM
    # Eine Dauerregel senkt sie nicht.
    class Regel:
        name, stufe = 'Webseiten immer', 'auto'
    assert policy.decide('web_abruf', ActionClass.READ, {'url': 'https://example.org/'}, regel=Regel()).level \
        is ApprovalLevel.CONFIRM
    # In einer Runde mit fremdem Inhalt bleibt die genaue Freigabe (die Adresse könnte diktiert sein).
    assert policy.decide('web_abruf', ActionClass.READ, {'url': 'https://example.org/'}, tainted=True).level \
        is ApprovalLevel.CONFIRM_STRICT
    # Lokale Lesewege bleiben ohne Rückfrage.
    assert policy.decide('aktuelle_zeit', ActionClass.READ, {}).level is ApprovalLevel.AUTO


def test_die_freigabe_nennt_adresse_ip_und_mitgesendete_angaben():
    werkzeug = build_registry(None)['web_abruf']
    satz = werkzeug.dry_run({'url': 'https://sammler.example/info?mandant=Kreisklinik+Rheingau'})
    assert 'https://sammler.example/info?mandant=Kreisklinik+Rheingau' in satz
    assert 'sammler.example' in satz and 'IP-Adresse' in satz
    assert 'mandant=Kreisklinik Rheingau' in satz
    assert satz.count('.') >= 1 and satz.endswith('.')
    ohne = werkzeug.dry_run({'url': 'https://example.org/seite'})
    assert 'mitgesendet' not in ohne and 'IP-Adresse' in ohne


def test_webabruf_im_gespraech_wartet_auf_die_freigabe(core, tmp_path, monkeypatch):
    abgerufen = []
    monkeypatch.setattr('icarus_memory.tools._web_fetch', lambda url, **_: abgerufen.append(url) or 'Seite')
    cloud = CloudGespraech(werkzeug='web_abruf', argumente={'url': 'https://example.org/lind'})
    app, client, cloud = _gespraech(core, tmp_path, monkeypatch, cloud=cloud, werkzeuge=('web_abruf',))
    try:
        daten = _chat(client, 'Schau bitte auf https://example.org/lind nach.')
        assert abgerufen == []
        karten = daten['action_requests']
        assert len(karten) == 1 and karten[0]['tool'] == 'web_abruf'
        assert karten[0]['confirmation_phrase'] is None  # ein Klick genügt
        assert 'https://example.org/lind' in karten[0]['dry_run']
    finally:
        client.close()
        _close_app(app)


def test_webabruf_laesst_sich_unter_was_kingfisher_darf_ausschalten(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        assert client.get('/api/v1/darf/web').json() == {'an': True}
        assert client.put('/api/v1/darf/web', json={'an': False}).json() == {'an': False}
        assert app.state.settings.web_abruf == 'aus'
        assert 'web_abruf' not in app.state.agent.tool_names
        assert client.put('/api/v1/darf/web', json={'an': True}).json() == {'an': True}
        assert 'web_abruf' in app.state.agent.tool_names
    finally:
        client.close()
        _close_app(app)


# -- D4: Einwilligung nennt Anbieter und Region -----------------------------------------------------------------------


def test_anbieter_nennen_land_und_region(app_und_client):
    _, client = app_und_client
    anbieter = {a['id']: a for a in client.get('/api/v1/models/roles').json()['anbieter']}
    assert anbieter['anthropic']['wohin'] == 'Anthropic (USA)'
    assert 'nicht nur in der EU' in anbieter['anthropic']['region']
    assert anbieter['openai']['wohin'] == 'OpenAI (USA)'
    assert 'EU' in anbieter['mistral']['region'] and 'Frankreich' in anbieter['mistral']['wohin']
    assert 'Europa' in anbieter['openrouter']['region']


def test_einwilligungssatz_der_antwort_sagt_inhalte_statt_textstellen():
    satz = ROLLEN['antwort'].cloud_satz
    assert 'Inhalte deiner Mails' in satz and 'ganz oder in Auszügen' in satz
    assert 'auch bei Fragen an dein Gedächtnis' in satz


# -- Kleinpunkt c: Welt-Meldung ohne Netz -----------------------------------------------------------------------------


def test_feed_ohne_netz_sagt_es_statt_nicht_erlaubt(monkeypatch):
    def kein_netz(*a, **k):
        raise socket.gaierror(-3, 'Temporary failure in name resolution')
    monkeypatch.setattr(socket, 'getaddrinfo', kein_netz)
    with pytest.raises(welt_feeds.FeedFehler) as fehler:
        welt_feeds.abrufen('https://www.deutschlandfunk.de/nachrichten-100.rss')
    assert 'nicht erlaubt' not in str(fehler.value)
    assert 'nicht erreichbar' in str(fehler.value) and 'Internet' in str(fehler.value)


def test_feed_im_internen_netz_bleibt_nicht_erlaubt(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('10.0.0.5', 443))])
    with pytest.raises(welt_feeds.FeedFehler) as fehler:
        welt_feeds.abrufen('https://intern.example/feed.rss')
    assert 'nicht erlaubt' in str(fehler.value)


def test_protokoll_satz_ohne_inhalte():
    satz = nach_draussen.satz({'anbieter': 'anthropic', 'wofuer': 'einordnung', 'gesendet': ['mail']})
    assert satz.startswith('Mail einordnen')
    assert logbuch.VERBOTENE_FELDER.isdisjoint({'anbieter', 'modell', 'wofuer', 'gesendet'})


# -- Kleinpunkt b: auch Einordnung und Aufbau aus der Cloud stehen im Protokoll ---------------------------------------


class _Json:
    name = 'anthropic'
    model = 'synthetisch-cloud'
    is_local = False

    def __init__(self):
        self.calls = 0

    def complete_json(self, messages, *, max_tokens, schema):
        self.calls += 1
        return Reply(text='{}')


def test_eingegrenzter_cloudanbieter_vermerkt_nur_was_wirklich_hinausgeht(monkeypatch):
    from icarus_memory.providers import ProviderError
    from icarus_memory.source_processing_policy import ScopedProvider
    vermerkt = []
    monkeypatch.setattr(logbuch, 'vermerke', lambda art, **daten: vermerkt.append((art, daten)) or True)
    innen = _Json()
    eingegrenzt = ScopedProvider(innen, None, lambda: None)
    eingegrenzt.wofuer = 'einordnung'
    eingegrenzt.complete_json([{'role': 'user', 'content': 'Mail von Anna Keller'}], max_tokens=100, schema={})
    assert vermerkt == [('cloud_anfrage', {'anbieter': 'anthropic', 'modell': 'synthetisch-cloud', 'wofuer': 'einordnung'})]

    def verweigert():
        raise ProviderError('Die Freigabe hat sich geändert.')
    gesperrt = ScopedProvider(innen, None, verweigert)
    with pytest.raises(ProviderError):
        gesperrt.complete_json([{'role': 'user', 'content': 'x'}], max_tokens=100, schema={})
    assert len(vermerkt) == 1 and innen.calls == 1  # nichts gesendet, nichts vermerkt
