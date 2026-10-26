"""Befund A2 der Persona-Prüfung: Kurz nach der Einrichtung antwortet Kingfisher auch aus frisch eingelesener Post.

Helga Brandt fragte „Wann ist die nächste Vorstandssitzung?“, Mail und Termin waren da, und die Antwort lautete „Das
kann ich mit den gefundenen Belegen nicht beantworten“. Die Ursache: Eine Quelle, die die Einordnung noch nicht
erreicht hatte, fand der Volltextindex zwar, sie konnte aber kein Beleg werden. Jetzt wird eine kurze, noch nicht
eingeordnete Quelle als ganze Rohquelle Beleg (Art `quelle`), mit denselben Prüfungen wie jede andere. Und solange
Kingfisher noch liest und trotzdem nichts findet, sagt die Antwort das in einem Satz und bietet an, neu zu fragen.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType, source_candidates, working_memory_answers as wma
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import ROH, ROH_MAX_ZEICHEN, WorkingMemoryStore

JETZT = datetime(2026, 10, 26, 18, 0, tzinfo=timezone.utc)
EINLADUNG = ('Liebe Helga,\n\nhiermit lade ich dich herzlich zur nächsten Vorstandssitzung ein: am Donnerstag, '
             '29. Oktober, um 18 Uhr im Vereinsheim.\n\nHerzliche Grüße\nErika')


class Auswahl:
    """Lokales Modell: wählt jede Quelle, merkt sich, was es sah; Sätze nur, wenn `saetze` gesetzt ist."""
    is_local = True

    def __init__(self, saetze=None):
        self.zeilen, self.saetze = None, saetze

    def complete_json(self, messages, **kwargs):
        from icarus_memory import satzantwort
        nutzer = json.loads(messages[-1]['content'])
        if satzantwort.ist_satzanfrage(messages):
            return Reply(text=json.dumps(self.saetze(nutzer) if self.saetze else {'status': 'unklar', 'saetze': []}))
        self.zeilen = nutzer['sources']
        return Reply(text=json.dumps({'status': 'source_reports', 'ids': [z['id'] for z in self.zeilen]}))


@pytest.fixture
def stores(tmp_path):
    episodes, claims = EpisodeStore(tmp_path / 'e.sqlite3'), ClaimStore(tmp_path / 'k.sqlite3')
    yield episodes, claims
    claims.close()
    episodes.close()


def mail(episodes, titel, text, *, stunden=72):
    episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL, source_ref=f'm:{titel}'),
                                 participants=['Erika Schulte <erika@gartenfreunde.example>'],
                                 occurred_at=JETZT - timedelta(hours=stunden))
    return episode


# -- Die Ursache: frische Quellen werden gefunden und können Beleg werden --------------------------------


def test_frische_quelle_wird_als_rohquelle_kandidat(stores):
    episodes, _ = stores
    quelle = mail(episodes, 'Einladung zur Vorstandssitzung', EINLADUNG)
    store = WorkingMemoryStore(episodes)
    assert store.progress()['remaining'] == 1, 'nichts eingeordnet'
    gefunden = source_candidates.zusammenfuehren(store, 'Wann ist die nächste Vorstandssitzung?', limit=12)
    assert gefunden.refs == [{'episode_id': quelle.id, 'fingerprint': gefunden.refs[0]['fingerprint'],
                              'start': 0, 'end': len(EINLADUNG), 'kind': ROH}]
    assert gefunden.zaehlung['roh'] == 1 and gefunden.zaehlung['ohne_einordnung'] == 0
    assert store.resolve(gefunden.refs[0]) is not None


def test_antwort_aus_frisch_eingelesener_mail(stores):
    episodes, claims = stores
    mail(episodes, 'Einladung zur Vorstandssitzung', EINLADUNG)
    modell = Auswahl()
    antwort = wma.prepare('Wann ist die nächste Vorstandssitzung?', episodes, claims, modell)
    assert antwort is not None and antwort['status'] == 'reports', 'Vorher: None, also „nicht beantwortbar“'
    assert [z['kind'] for z in modell.zeilen] == [ROH]
    text, links, status = wma.render(antwort, episodes, claims)
    assert status == 'working_reports' and EINLADUNG in text and len(links) == 1


def test_satzantwort_aus_rohquelle_mit_satzpruefung(stores):
    episodes, claims = stores
    mail(episodes, 'Einladung zur Vorstandssitzung', EINLADUNG)

    def saetze(nutzer):
        return {'status': 'antwort', 'saetze': [
            {'text': 'Die nächste Vorstandssitzung ist am 29. Oktober um 18 Uhr im Vereinsheim.', 'belege': [1]},
            {'text': 'Die Vorstandssitzung ist am 30. Oktober.', 'belege': [1]}]}

    antwort = wma.prepare('Wann ist die nächste Vorstandssitzung?', episodes, claims, Auswahl(saetze), saetze=True)
    satz = antwort['satzantwort']
    assert [s['text'] for s in satz['saetze']] == ['Die nächste Vorstandssitzung ist am 29. Oktober um 18 Uhr im '
                                                   'Vereinsheim.']
    assert satz['verworfen'] == 1, 'Das falsche Datum fällt auch bei einer Rohquelle'


def test_nach_der_einordnung_gilt_der_eingeordnete_abschnitt(stores):
    episodes, claims = stores
    quelle = mail(episodes, 'Einladung zur Vorstandssitzung', EINLADUNG)
    store = WorkingMemoryStore(episodes)
    [snapshot] = store.pending(limit=5)
    assert store.commit(snapshot, [{'start': 0, 'end': len(EINLADUNG), 'kind': 'fact'}], model='t')
    gefunden = source_candidates.zusammenfuehren(store, 'Vorstandssitzung', limit=12)
    assert [(r['episode_id'], r['kind']) for r in gefunden.refs] == [(quelle.id, 'fact')]
    assert gefunden.zaehlung['roh'] == 0


# -- Grenzen der Rohquelle ---------------------------------------------------------------------------------


def test_ausgenommene_quelle_wird_keine_rohquelle(stores):
    episodes, _ = stores
    quelle = mail(episodes, 'Herbstangebote Vorstandssitzung', 'Werbung zur Vorstandssitzung: 30 % auf alles.')
    store = WorkingMemoryStore(episodes)
    assert store.dismiss(quelle.id)
    gefunden = source_candidates.zusammenfuehren(store, 'Vorstandssitzung', limit=12)
    assert gefunden.refs == []


def test_zu_lange_quelle_bleibt_gezaehlt_und_ohne_beleg(stores):
    episodes, _ = stores
    mail(episodes, 'Protokoll Vorstandssitzung', 'Vorstandssitzung. ' + 'Bericht. ' * (ROH_MAX_ZEICHEN // 8))
    gefunden = source_candidates.zusammenfuehren(WorkingMemoryStore(episodes), 'Vorstandssitzung', limit=12)
    assert gefunden.refs == [] and gefunden.zaehlung['ohne_einordnung'] == 1


def test_zitierter_verlauf_gehoert_nicht_zur_rohquelle(stores):
    episodes, _ = stores
    neu = 'Ja, ich komme zur Vorstandssitzung.\n\n'
    alt = 'Am 15.10.2026 schrieb Erika Schulte:\n> Die Vorstandssitzung ist am 22. Oktober.\n'
    quelle = mail(episodes, 'Re: Vorstandssitzung', neu + alt)
    [ref] = source_candidates.zusammenfuehren(WorkingMemoryStore(episodes), 'Vorstandssitzung', limit=12).refs
    assert ref['episode_id'] == quelle.id and ref['kind'] == ROH
    assert '22. Oktober' not in quelle.body[ref['start']:ref['end']]


@pytest.mark.parametrize('aenderung', [
    {'end': 10}, {'start': 1}, {'fingerprint': '0' * 64}, {'kind': 'unbekannt'}])
def test_rohverweis_gilt_nur_genau_so(stores, aenderung):
    episodes, _ = stores
    mail(episodes, 'Einladung zur Vorstandssitzung', EINLADUNG)
    store = WorkingMemoryStore(episodes)
    [ref] = source_candidates.zusammenfuehren(store, 'Vorstandssitzung', limit=12).refs
    assert store.resolve({**ref, **aenderung}) is None


def test_geaenderte_quelle_entwertet_den_rohverweis(stores):
    episodes, _ = stores
    quelle = mail(episodes, 'Einladung zur Vorstandssitzung', EINLADUNG)
    store = WorkingMemoryStore(episodes)
    [ref] = source_candidates.zusammenfuehren(store, 'Vorstandssitzung', limit=12).refs
    episodes.ignore(quelle.id)
    assert store.resolve(ref) is None


# -- Der ehrliche Satz, solange Kingfisher noch liest ---------------------------------------------------------


from tests.test_context_identity import core  # noqa: E402,F401 - Fixture
from tests.test_conversation_retraction import _close_app  # noqa: E402
from tests.test_source_answers_http import _api, _ask, _conversation  # noqa: E402

LIEST = 'Kingfisher liest deine Post gerade noch ein (2 von 5 Mails).'


def test_nichts_gefunden_waehrend_des_einlesens_sagt_es_und_bietet_neu_fragen_an(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.agent._lesestand = lambda: LIEST
        antwort = _ask(client, _conversation(client), 'Wann ist die nächste Vorstandssitzung?')
        assert antwort['content'] == f'{LIEST} Bisher habe ich dazu nichts gefunden. Frag gleich noch einmal.'
        kontext = antwort['metadata']['context']
        assert kontext['refresh_available'] is True and kontext['einlesen'] is True
        assert kontext['original_question'] == 'Wann ist die nächste Vorstandssitzung?'
    finally:
        client.close()
        _close_app(app)


def test_ohne_einlesen_bleibt_die_antwort_wie_sie_war(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.agent._lesestand = lambda: ''
        antwort = _ask(client, _conversation(client), 'Wann ist die nächste Vorstandssitzung?')
        assert antwort['content'] == 'Das kann ich mit den gefundenen Belegen nicht beantworten.'
        assert 'refresh_available' not in antwort['metadata']['context']
    finally:
        client.close()
        _close_app(app)


def test_lesestand_aus_postfach_und_einordnung(core, tmp_path, monkeypatch):
    from icarus_memory import agent_verdrahtung, mail_stand
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        monkeypatch.setattr(mail_stand, 'stand', lambda _app: [{'zustand': 'liest', 'gelesen': 120, 'gesamt': 4300}])
        assert agent_verdrahtung.lesestand_satz(app) == 'Kingfisher liest deine Post gerade noch ein (120 von 4.300 Mails).'
        monkeypatch.setattr(mail_stand, 'stand', lambda _app: [{'zustand': 'aktuell'}])
        mail(app.state.episodes, 'Einladung zur Vorstandssitzung', EINLADUNG)
        plan = app.state.settings.schedule
        monkeypatch.setattr(plan, 'enabled', False)
        assert agent_verdrahtung.lesestand_satz(app) == '', 'Ausgeschaltete Einordnung verspricht nichts'
        monkeypatch.setattr(plan, 'enabled', True)
        monkeypatch.setattr(plan, 'with_model', True)
        assert agent_verdrahtung.lesestand_satz(app) == 'Kingfisher ordnet deine Post und Termine gerade noch ein (noch 1 von 1 Quelle).'
        app.state.hintergrund.pausieren(True)
        assert agent_verdrahtung.lesestand_satz(app) == '', 'Pausiert verspricht nichts'
    finally:
        client.close()
        _close_app(app)
