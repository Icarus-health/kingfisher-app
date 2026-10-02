"""E1 im echten Gespräch: Gedächtnisfragen gehen in den belegten Weg, die gespeicherte Anfrage bleibt maßgeblich."""
import json

import pytest

from icarus_memory import frage as frage_modul
from icarus_memory.frage import Anfrage
from icarus_memory.memory_routing import route
from icarus_memory.providers import Reply
from icarus_memory.working_memory_answers import lookup_of
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api, _ask, _conversation, _upload
from tests.test_working_memory_flow import run_working


def _modell(provider, *, frage=None, app=None):
    """Wie der Klassifizierer der anderen Tests, dazu Antworten der Rolle „frage“ (Text -> Anfrage)."""
    def complete_json(messages, *, max_tokens, schema):
        daten = json.loads(messages[-1]['content'])
        if 'frage' in daten:
            provider.frage_aufrufe.append(daten['frage'])
            if frage is None or daten['frage'] not in frage:
                raise ValueError('keine Vorgabe')
            return Reply(text=json.dumps(frage[daten['frage']]))
        provider.calls.append(daten)
        if 'blocks' in daten:
            return Reply(text=json.dumps({'items': [
                {'block_id': block['block_id'], 'kind': 'fact'} for block in daten['blocks']]}))
        return Reply(text=json.dumps({'status': 'reports', 'ids': [row['id'] for row in daten['sources']]}))
    provider.frage_aufrufe = []
    provider.complete_json = complete_json
    if frage is not None and app is not None:
        # Die Rolle „frage“ ist diesem Modell zugewiesen (im Betrieb: Einstellungen, Lokale KI).
        app.state.agent._frage_anbieter = lambda: provider


def _anfrage(**felder):
    return {'sachen': [], 'zeitraum': 'keiner', 'absicht': 'fakt', 'suchworte': [], 'umschreibungen': [], **felder}


@pytest.mark.parametrize('frage', [
    'Findet der Workshop bei der Akademie Taunus am 28. Oktober statt?',
    'Warum wurde der Workshop in Bad Homburg abgesagt?',
    'Muss ich noch etwas beim Workshop tun?',
    'Wir hatten doch vor ein paar Jahren mal Kontakt zu jemandem beim Workshop. Wer war das?',
    'Mit wem hatte ich mal beim Workshop zu tun?',
    'Seit wann kenne ich die Akademie Taunus?',
])
def test_gedaechtnisfragen_gehen_in_den_belegten_weg_und_nicht_in_den_chat(core, tmp_path, monkeypatch, frage):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    _modell(provider)
    text = 'Der Workshop bei der Akademie Taunus in Bad Homburg am 28. Oktober wurde von der Akademie abgesagt.'
    try:
        _upload(client, text)
        run_working(app)
        antwort = _ask(client, _conversation(client), frage)
        kontext = antwort['metadata']['context']
        assert kontext['answer_mode'] == 'memory_evidence'
        assert kontext['working_answer']['refs'], 'Die Antwort muss belegt sein'
        assert text in antwort['content']
    finally:
        client.close()
        _close_app(app)


def test_allgemeine_fragen_ohne_bezug_zum_bestand_bleiben_im_chat(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    _modell(provider)
    try:
        _upload(client, 'Der Workshop bei der Akademie Taunus wurde abgesagt.')
        run_working(app)
        antwort = _ask(client, _conversation(client), 'Wie funktioniert ein Vulkan?')
        assert antwort['metadata']['context'].get('answer_mode') != 'memory_evidence'
    finally:
        client.close()
        _close_app(app)


def test_route_wertet_die_anfrage_aus_statt_einzelmustern():
    # Vorher Chat: keine der Formen begann mit einem Fragewort der alten Liste.
    for frage in ('Findet der Workshop am 28. Oktober statt?', 'Muss ich noch etwas wegen des Hotels tun?',
                  'Mit wem hatte ich mal wegen einer Software zu tun?', 'Seit wann kenne ich Claudia Reinhardt?',
                  'Warum wurde der Workshop abgesagt?', 'Für welche Firma arbeitet Alex Winter?',
                  'Wir hatten doch mal Kontakt zu jemandem. Wer war das?', 'Was ist eigentlich mit Mainz los?',
                  'Mainz?'):
        assert route(frage, working_available=True) == 'memory_evidence', frage
    # Ohne Treffer im Bestand bleibt jede Frage im Chat, und Aufträge sowieso.
    for frage in ('Findet der Workshop am 28. Oktober statt?', 'Wie funktioniert ein Vulkan?'):
        assert route(frage, working_available=False) == 'chat'
    for auftrag in ('Kannst du mir die Mail von Anna zusammenfassen?', 'Schreib Anna wegen Mainz',
                    'Suche mir einen Termin im Kalender heraus, wann ist das?'):
        assert route(auftrag, working_available=True) == 'chat', auftrag


def test_haelt_das_modell_eine_frage_fuer_allgemein_bleibt_sie_nur_mit_bezug_im_bestand():
    modell = dict(herkunft='modell')
    allgemein = Anfrage((), None, 'allgemein', **modell)
    assert route('Was ist ein Auflauf?', working_available=True, anfrage=allgemein) == 'chat'
    # Ein Fehlurteil des kleinen Modells schickt eine Gedächtnisfrage nicht in den Chat:
    assert route('Wann habe ich mit Frau Koch gesprochen?', working_available=True,
                 anfrage=Anfrage(('Koch',), None, 'allgemein', **modell)) == 'memory_evidence'
    assert route('Was hatte ich mir dazu notiert?', working_available=True, anfrage=allgemein) == 'memory_evidence'
    assert route('Wie geht es dir?', working_available=True, anfrage=allgemein) == 'chat'


def test_die_gespeicherte_anfrage_bestimmt_die_frischepruefung_ohne_neuen_modellaufruf(core, tmp_path, monkeypatch):
    app, client, provider = _api(core, tmp_path, monkeypatch)
    frage = 'Wie teuer wird das Catering für die Tagung?'
    _modell(provider, app=app, frage={frage: _anfrage(sachen=['Catering', 'Tagung'], suchworte=['Catering'],
                                                      umschreibungen=['Verpflegung', 'Fachtag'])})
    quelle = 'Verpflegungspauschale Fachtag: 45 Euro pro Kopf für Mittagessen und Pausen.'
    try:
        _upload(client, quelle)
        run_working(app)
        gespraech = _conversation(client)
        antwort = _ask(client, gespraech, frage)
        arbeitsstand = antwort['metadata']['context']['working_answer']
        # Ohne die Umschreibung hätte die Suche die Quelle nie gefunden: kein Wort der Frage steht darin.
        assert quelle in antwort['content']
        assert arbeitsstand['anfrage']['umschreibungen'] == ['Verpflegung', 'Fachtag']
        assert arbeitsstand['anfrage']['herkunft'] == 'modell' and 'retrieval_query' not in arbeitsstand
        assert provider.frage_aufrufe == [frage]

        # Beim Wiederöffnen prüft das Produkt die Frische mit der GESPEICHERTEN Anfrage.
        # Das Modell darf dafür nicht mehr gefragt werden.
        def verboten(*args, **kwargs):
            raise AssertionError('Die Frischeprüfung darf das Modell nicht erneut fragen.')
        monkeypatch.setattr(frage_modul, 'verstehen', verboten)
        offen = client.get(f'/api/v1/conversations/{gespraech}').json()['messages'][-1]
        assert quelle in offen['content']
        assert offen['metadata']['context']['answer_contract']['status'] != 'working_unavailable'
        assert provider.frage_aufrufe == [frage]
    finally:
        client.close()
        _close_app(app)


def test_lookup_of_ist_eine_reine_funktion_der_gespeicherten_anfrage():
    frage = 'Wie teuer wird das Catering?'
    anfrage = Anfrage(('Catering',), None, 'fakt', umschreibungen=('Verpflegung',), herkunft='modell')
    antwort = {'query': frage, 'anfrage': anfrage.als_dict()}
    assert lookup_of(antwort) == frage + ' Verpflegung'
    assert lookup_of({'query': frage}) == frage
    assert lookup_of({'query': frage, 'retrieval_query': 'anderer Text', 'anfrage': anfrage.als_dict()}) == 'anderer Text'
    # Eine untergeschobene oder veränderte Anfrage ergibt keinen Suchtext: Die Antwort gilt als nicht frisch.
    assert lookup_of({'query': frage, 'anfrage': {**anfrage.als_dict(), 'sachen': ['Geheimprojekt']}}) is None
    assert lookup_of({'query': frage, 'anfrage': 'kaputt'}) is None
    assert lookup_of({'query': 7}) is None
