"""Lint-Routen: Anstoß, Befunde, „Erledigt“/„Ignorieren“, Entscheidung per Klick, Hintergrundlauf."""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import akten_routes, lint, lint_routes
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalState
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_mappe import _projekt, _quelle
from tests.test_source_answers_http import _api

KOLBE = 'Bernd Kolbe <b.kolbe@kuechenforum.example>'
NEUMANN = 'Carla Neumann <c.neumann@pflegeverband.example>'
WELLER = 'Anja Weller <a.weller@druckerei-weller.example>'
FRIST_ALT = 'Bitte schicken Sie mir die Anmeldeliste bis zum 20. Oktober 2030.'
FRIST_NEU = 'Die Anmeldeliste verschiebt sich auf den 6. November 2030.'
UMZUG = 'Unsere Rechnungsanschrift hat sich geändert: Mühlweg 8, 64823 Groß-Umstadt.'


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        yield app, client
    finally:
        client.close()


def fristen(app):
    p = _projekt(app, 'Schulungsreihe Pflegeküche')
    alt = _quelle(app, 'Anmeldeliste', [(FRIST_ALT, 'request')], KOLBE, p.id, tage=100)
    neu = _quelle(app, 'Späterer Start', [(FRIST_NEU, 'change')], NEUMANN, p.id, tage=40)
    return p, alt, neu


def angenommen(app):
    notiz, _ = app.state.episodes.record(
        EpisodeKind.DOCUMENT, 'Telefonat Druckerei', 'Die Rechnungsanschrift der Druckerei ist Gutenbergring 3, 64807 Dieburg.',
        Provenance(SourceType.USER_STATED, source_ref='notiz:druckerei'),
        occurred_at=datetime.now(timezone.utc) - timedelta(days=150))
    service = app.state.knowledge_service
    vorschlag, _ = service.propose(subject_ref='organisation:druckereiweller', predicate='Rechnungsanschrift',
                                   value='Gutenbergring 3, 64807 Dieburg',
                                   statement='Die Rechnungsanschrift der Druckerei Weller ist Gutenbergring 3, 64807 Dieburg.',
                                   rationale='Telefonat', evidence=[Evidence(notiz.id, notiz.body, notiz.digest)])
    aussage = service.accept(vorschlag.id, supersedes=[])
    neu = _quelle(app, 'Umzug', [(UMZUG, 'change')], WELLER, tage=10)
    return aussage, neu


def offen(client):
    return client.get('/api/v1/lint/befunde').json()['befunde']


def test_anstoss_findet_den_widerspruch_und_legt_nur_vorschlaege_an(api):
    app, client = api
    p, alt, neu = fristen(app)
    revision = app.state.claims.revision
    antwort = client.post('/api/v1/lint').json()
    assert antwort['lauf']['befunde'] == 1 and antwort['lauf']['vorschlaege'] == 2
    assert antwort['zusammenfassung']['je_art']['widerspruch'] == 1 and antwort['zusammenfassung']['wichtig'] == 1
    [befund] = offen(client)
    assert befund['art'] == 'widerspruch' and befund['art_text'] == 'Widerspruch zwischen Akten'
    assert {s['name'] for s in befund['sachen']} >= {'Bernd Kolbe', 'Schulungsreihe Pflegeküche'}
    assert [(b['episode_id'], b['rolle'], b['titel']) for b in befund['belege']] == [
        (alt.id, 'alt', 'Anmeldeliste'), (neu.id, 'neu', 'Späterer Start')]
    assert sorted((v['wahl'], v['zustand'], v['wert']) for v in befund['vorschlaege']) == [
        ('alt', 'pending', '20.10.2030'), ('neu', 'pending', '06.11.2030')]
    assert 'entwuerfe' not in befund
    # Die Regel des Gedächtnisses: kein Fakt ohne Klick.
    assert app.state.claims.revision == revision
    # Ein zweiter Lauf legt nichts doppelt an.
    assert client.post('/api/v1/lint').json()['lauf']['vorschlaege'] == 0 and len(offen(client)) == 1


def test_neu_gilt_macht_den_neuen_wert_zu_wissen_und_die_mail_bleibt_in_der_akte(api):
    app, client = api
    p, alt, neu = fristen(app)
    client.post('/api/v1/lint')
    [befund] = offen(client)
    vorschlaege = {v['wahl']: v['id'] for v in befund['vorschlaege']}
    antwort = client.post(f'/api/v1/lint/befunde/{befund["id"]}/entscheiden', json={'wahl': 'neu'}).json()
    assert antwort['befund']['status'] == 'erledigt' and antwort['befund']['entschieden'] == 'neu'
    assert antwort['aussage']['value'] == '06.11.2030' and antwort['aussage']['subject_ref'] == f'project:{p.id}'
    assert app.state.proposals.get(vorschlaege['neu']).state is ProposalState.SUPERSEDED
    # Der andere Wert wird nie Wissen: Die Annahme stellt den widersprechenden Vorschlag zurück.
    assert app.state.proposals.get(vorschlaege['alt']).state is ProposalState.SUPERSEDED
    # Die Annahme steht auf einer eigenen Quelle „vom Nutzer entschieden“, nicht auf der Mail: Die Akte zeigt die Mail weiter.
    aussage = app.state.claims.get(antwort['aussage']['id'])
    assert aussage.evidence[0].episode_id not in {alt.id, neu.id}
    assert app.state.claims.source_is_unclaimed(neu.id)
    akte = client.get('/api/v1/akten/akte', params={'sache': f'projekt:{p.id}'}).json()
    assert [f['datum'] for f in akte['fristen']['kommend']] == ['2030-11-06']
    assert offen(client) == [] and client.post('/api/v1/lint').json()['zusammenfassung']['offen'] == 0
    assert client.post(f'/api/v1/lint/befunde/{befund["id"]}/entscheiden', json={'wahl': 'alt'}).status_code == 409


def test_alt_gilt_behaelt_die_angenommene_aussage(api):
    app, client = api
    aussage, neu = angenommen(app)
    client.post('/api/v1/lint')
    [befund] = offen(client)
    assert befund['art'] == 'aussage_gegen_quelle' and 'Gutenbergring 3' in befund['text']
    [vorschlag] = befund['vorschlaege']
    antwort = client.post(f'/api/v1/lint/befunde/{befund["id"]}/entscheiden', json={'wahl': 'alt'}).json()
    assert antwort['aussage'] is None and antwort['befund']['status'] == 'erledigt'
    assert app.state.proposals.get(vorschlag['id']).state is ProposalState.REJECTED
    assert app.state.claims.get(aussage.id).status.value == 'active'


def test_neu_gilt_loest_die_angenommene_aussage_ab(api):
    app, client = api
    aussage, neu = angenommen(app)
    client.post('/api/v1/lint')
    [befund] = offen(client)
    antwort = client.post(f'/api/v1/lint/befunde/{befund["id"]}/entscheiden', json={'wahl': 'neu'}).json()
    assert antwort['aussage']['value'] == 'Mühlweg 8'
    assert app.state.claims.get(aussage.id).status.value == 'superseded'
    assert app.state.claims.get(antwort['aussage']['id']).status.value == 'active'


def test_ignorieren_lehnt_die_vorschlaege_ab_und_der_befund_kommt_nicht_wieder(api):
    app, client = api
    fristen(app)
    client.post('/api/v1/lint')
    [befund] = offen(client)
    revision = app.state.claims.revision
    antwort = client.patch(f'/api/v1/lint/befunde/{befund["id"]}', json={'status': 'abgewiesen'}).json()
    assert antwort['befund']['status'] == 'abgewiesen' and antwort['zusammenfassung']['offen'] == 0
    assert {app.state.proposals.get(v['id']).state for v in befund['vorschlaege']} == {ProposalState.REJECTED}
    client.post('/api/v1/lint')
    assert offen(client) == [] and app.state.claims.revision == revision
    abgewiesen = client.get('/api/v1/lint/befunde', params={'status': 'abgewiesen'}).json()['befunde']
    assert [b['id'] for b in abgewiesen] == [befund['id']]
    # Zurück auf offen: Der nächste Lauf legt frische Vorschläge an.
    client.patch(f'/api/v1/lint/befunde/{befund["id"]}', json={'status': 'offen'})
    assert client.post('/api/v1/lint').json()['lauf']['vorschlaege'] == 2
    assert all(v['zustand'] == 'pending' for v in offen(client)[0]['vorschlaege'])


def test_erledigt_fuer_einen_hinweis_und_fehler_sind_deutlich(api):
    app, client = api
    for n in range(3):
        _quelle(app, f'Demo {n}', [(f'Angabe {n} zur Software.', 'fact')], 'Holger Weidner <h.weidner@diaetplan.example>',
                tage=500 + n)
    client.post('/api/v1/lint')
    [befund] = offen(client)
    assert (befund['art'], befund['unterart'], befund['schwere'], befund['vorschlaege']) == ('waise', 'ruhend', 'hinweis', [])
    assert client.post(f'/api/v1/lint/befunde/{befund["id"]}/entscheiden', json={'wahl': 'neu'}).status_code == 409
    assert client.patch(f'/api/v1/lint/befunde/{befund["id"]}', json={'status': 'erledigt'}).json()['befund']['status'] == 'erledigt'
    assert client.patch('/api/v1/lint/befunde/b-gibtsnicht', json={'status': 'erledigt'}).status_code == 404
    assert client.post('/api/v1/lint/befunde/b-gibtsnicht/entscheiden', json={'wahl': 'neu'}).status_code == 404
    assert client.patch(f'/api/v1/lint/befunde/{befund["id"]}', json={'status': 'vielleicht'}).status_code == 422
    assert client.get('/api/v1/lint/befunde', headers={'X-Icarus-Token': 'falsch'}).status_code in (401, 403)


def test_entzogene_quelle_nimmt_den_befund_sofort_aus_der_liste(api):
    app, client = api
    _, _, neu = fristen(app)
    client.post('/api/v1/lint')
    assert len(offen(client)) == 1
    app.state.episodes.ignore(neu.id)
    assert offen(client) == []
    assert client.post('/api/v1/lint').json()['lauf']['entfallen'] == 1


def test_anderswo_entschiedener_vorschlag_erledigt_den_befund(api):
    app, client = api
    fristen(app)
    client.post('/api/v1/lint')
    [befund] = offen(client)
    for v in befund['vorschlaege']:
        app.state.knowledge_service.reject(v['id'])
    assert offen(client) == []
    assert app.state.lint_befunde.get(befund['id'])['entschieden'] == 'vorschlag'


def test_hintergrund_laeuft_nach_dem_abgleich_im_selben_faden_und_gedrosselt(api, monkeypatch):
    app, _ = api
    fristen(app)
    aufrufe = []
    echt = lint_routes.ausfuehren
    monkeypatch.setattr(lint_routes, 'ausfuehren', lambda app_, **kw: aufrufe.append(1) or echt(app_, **kw))
    # Nach dem Start wartet der erste Lauf den Mindestabstand ab.
    akten_routes.nachfuehren(app)
    faden = getattr(app.state, 'akten_faden', None)
    if faden is not None:
        faden.join(20)
    assert aufrufe == [] and lint.zusammenfassung(app)['offen'] == 0
    app.state.lint_abstand_s = 0
    app.state.lint_letzter = None
    akten_routes.nachfuehren(app)
    app.state.akten_faden.join(20)
    assert aufrufe == [1] and lint.zusammenfassung(app)['je_art']['widerspruch'] == 1
    assert app.state.akten_faden.name == 'akten-bezuege'
    # Gedrosselt: Innerhalb des Abstands läuft nichts, auch wenn sich etwas ändert.
    app.state.lint_abstand_s = 3600
    _quelle(app, 'Neu', [('Noch eine Angabe.', 'fact')], tage=1)
    assert lint_routes.faellig(app) is False
    akten_routes.nachfuehren(app)
    app.state.akten_faden.join(20)
    assert aufrufe == [1]
    # Ohne Änderung ist auch nach dem Abstand nichts fällig.
    app.state.lint_abstand_s = 0
    akten_routes.nachfuehren(app, warten=True)
    lint_routes.ausfuehren(app)
    assert lint_routes.faellig(app) is False


def test_befunde_gehoeren_zur_sicherung_und_zur_schemapruefung():
    from icarus_memory import update_backup
    from icarus_memory.backup import BACKUP_DATA_FILES, SQLITE_DATA_FILES
    assert 'lint.sqlite3' in SQLITE_DATA_FILES and 'lint.sqlite3' in BACKUP_DATA_FILES
    assert 'lint.sqlite3' in update_backup._targets()
