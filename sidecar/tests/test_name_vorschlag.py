"""Der Assistent schlägt den Namen vor, statt zu fragen (V3): woher, was nicht gilt, und dass nichts ohne Klick bleibt.

Nur synthetische Namen und Adressen (Lea Hartmann, `example.org`).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from icarus_memory import MemoryBackend, SelfModelStore, name_vorschlag
from icarus_memory.audit import AuditLog
from icarus_memory.episodes import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.name_vorschlag import Merker, aus_postfach, aus_rechner, bereinigt, vorname, vorschlagen
from icarus_memory.server import create_app
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

ICH = 'lea.hartmann@example.org'
ENV = ('ICARUS_PROVIDER', 'ICARUS_MODEL', 'ICARUS_BASE_URL', 'KINGFISHER_USER_NAME', 'KINGFISHER_VOLLER_NAME',
       'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'LLM_API_KEY')
JETZT = datetime(2026, 9, 29, 7, 30, tzinfo=timezone.utc)
_ZAEHLER = [0]


def mail(episoden: EpisodeStore, *, von_name: str, ich: bool = True, an_name: str = 'Silke Vogt', tage: int = 1,
         adresse: str = ICH, an_zuerst: bool = False) -> None:
    """Eine Mail mit Rollen wie aus der Aufnahme; `ich` heißt, die Absenderadresse gehört einem eigenen Postfach."""
    _ZAEHLER[0] += 1
    kontakte = [{'name': von_name, 'adresse': adresse if ich else 'silke@example.org', 'rolle': 'von', 'ich': ich},
                {'name': an_name, 'adresse': 'silke@example.org' if ich else adresse, 'rolle': 'an', 'ich': not ich}]
    if an_zuerst:
        kontakte.reverse()
    episoden.record(EpisodeKind.MESSAGE, 'Hallo', f'Text {_ZAEHLER[0]}',
                    Provenance(SourceType.EMAIL, source_ref=f'konto:<{_ZAEHLER[0]}@example.org>'),
                    participants=[f'{k["name"]} <{k["adresse"]}>' for k in kontakte], contacts=kontakte,
                    occurred_at=JETZT - timedelta(days=tage))


@pytest.fixture
def api(tmp_path, monkeypatch):
    for name in ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('ICARUS_SIDECAR_TOKEN', 'local-owner-token')
    # Die Tests laufen auf Linux oder im Container; der Mac-Weg wird eigens geprüft.
    monkeypatch.setattr(name_vorschlag.sys, 'platform', 'linux')
    episoden = EpisodeStore(tmp_path / 'episodes.sqlite3')
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'), audit=AuditLog(tmp_path / 'audit.sqlite3'),
                     tasks=TaskStore(tmp_path / 'tasks.sqlite3'), workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'),
                     episodes=episoden)
    with TestClient(app, headers={'X-Icarus-Token': 'local-owner-token'}) as client:
        yield app, client, episoden


# -- Was ein Name ist ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize('roh,name,vor', [
    ('Lea Hartmann', 'Lea Hartmann', 'Lea'),
    ('Hartmann, Lea', 'Lea Hartmann', 'Lea'),
    ('"Dr. Lea Hartmann"', 'Dr. Lea Hartmann', 'Lea'),
    ('Lea Hartmann | Hartmann Beratung', 'Lea Hartmann', 'Lea'),
    ('Lea Hartmann – Geschäftsführung', 'Lea Hartmann', 'Lea'),
    ('Anna-Lena Weiß (Büro)', 'Anna-Lena Weiß', 'Anna-Lena'),
    ('Prof. Dr. Jürgen Krämer', 'Prof. Dr. Jürgen Krämer', 'Jürgen'),
    ('Lea', 'Lea', 'Lea'),
])
def test_name_und_vorname(roh, name, vor) -> None:
    assert bereinigt(roh) == name
    assert vorname(roh) == vor


@pytest.mark.parametrize('roh', ['', 'lea.hartmann', 'lea.hartmann@example.org', 'Info', 'Praxis Team', 'root',
                                 'System Administrator', 'Familie Hartmann', 'R2D2', 'Kingfisher', 'Hartmann, Lea, Büro'])
def test_kein_name_eines_menschen(roh) -> None:
    assert bereinigt(roh) == '' and vorname(roh) == ''


@pytest.mark.parametrize('roh', ['Frau Dr. Hartmann', 'Herr Krämer', 'Dr. Hartmann', 'A. Keller'])
def test_kein_vorname_erfunden(roh) -> None:
    """Nach Anrede oder Titel vor nur einem Wort steht der Nachname; eine Initiale ist kein Vorname."""
    assert vorname(roh) == ''


# -- Woher ----------------------------------------------------------------------------------------------------------

def test_postfach_der_haeufigste_eigene_absendername() -> None:
    namen = ['Lea Hartmann', 'Lea Hartmann | Beratung', 'Lea', 'Hartmann, Lea', 'info']
    assert aus_postfach(None, namen) == 'Lea Hartmann'


def test_postfach_ohne_mails_nimmt_den_absender_des_kontos() -> None:
    einstellungen = SimpleNamespace(mail_accounts=[SimpleNamespace(sender=''), SimpleNamespace(sender='Lea Hartmann <lea@example.org>')])
    assert aus_postfach(einstellungen, []) == 'Lea Hartmann'
    assert aus_postfach(SimpleNamespace(mail_accounts=[SimpleNamespace(sender='lea@example.org')]), []) == ''


def test_rechner_nur_auf_dem_mac() -> None:
    konto = lambda: 'Lea Hartmann,,,'  # noqa: E731
    assert aus_rechner({}, plattform='darwin', im_container=False, konto=konto) == 'Lea Hartmann'
    assert aus_rechner({}, plattform='linux', im_container=False, konto=konto) == ''
    assert aus_rechner({}, plattform='darwin', im_container=True, konto=konto) == ''
    assert aus_rechner({}, plattform='darwin', im_container=False, konto=lambda: 'root') == ''
    # Die Mac-App meldet den Namen an den Container.
    assert aus_rechner({'KINGFISHER_VOLLER_NAME': 'Lea Hartmann'}, plattform='linux', im_container=True) == 'Lea Hartmann'


def test_reihenfolge_umgebung_postfach_rechner() -> None:
    mac = {'plattform': 'linux', 'im_container': True}
    umgebung = {'KINGFISHER_USER_NAME': 'Lena', 'KINGFISHER_VOLLER_NAME': 'Lea Mac'}
    assert vorschlagen(None, lambda: ['Lea Hartmann'], umgebung=umgebung, **mac)['quelle'] == 'umgebung'
    umgebung.pop('KINGFISHER_USER_NAME')
    assert vorschlagen(None, lambda: ['Lea Hartmann'], umgebung=umgebung, **mac) == \
        {'name': 'Lea Hartmann', 'vorname': 'Lea', 'quelle': 'postfach'}
    assert vorschlagen(None, lambda: [], umgebung=umgebung, **mac) == {'name': 'Lea Mac', 'vorname': 'Lea', 'quelle': 'rechner'}
    assert vorschlagen(None, lambda: [], umgebung={}, **mac) is None


def test_umgebung_fragt_den_bestand_nicht() -> None:
    def nie():
        raise AssertionError('Mit gesetzter Umgebung wird der Bestand nicht gelesen')
    assert vorschlagen(None, nie, umgebung={'KINGFISHER_USER_NAME': 'Lena'}, plattform='linux', im_container=True)['vorname'] == 'Lena'


def test_ein_fehler_im_bestand_kippt_den_vorschlag_nicht() -> None:
    def kaputt():
        raise RuntimeError('Bestand nicht lesbar')
    assert vorschlagen(None, kaputt, umgebung={'KINGFISHER_VOLLER_NAME': 'Lea Hartmann'}, plattform='linux',
                       im_container=True)['quelle'] == 'rechner'


def test_merker_rechnet_je_frist_einmal_und_neu_bei_anderem_schluessel() -> None:
    uhr = [0.0]
    merker, aufrufe = Merker(frist=60, uhr=lambda: uhr[0]), []
    rechnen = lambda: aufrufe.append(1) or {'name': 'Lea', 'vorname': 'Lea', 'quelle': 'postfach'}  # noqa: E731
    for _ in range(5):
        merker.holen('a', rechnen)
    assert len(aufrufe) == 1
    merker.holen('b', rechnen)
    uhr[0] = 61
    merker.holen('b', rechnen)
    assert len(aufrufe) == 3


# -- Bestand und Route ----------------------------------------------------------------------------------------------

def test_eigene_absendernamen_nur_eigene_mails_juengste_zuerst(tmp_path) -> None:
    episoden = EpisodeStore(tmp_path / 'episodes.sqlite3')
    mail(episoden, von_name='Lea Hartmann', tage=5)
    mail(episoden, von_name='Lea H.', tage=1)
    mail(episoden, von_name='Silke Vogt', ich=False, an_name='Frau Hartmann')  # fremde Mail an mich
    mail(episoden, von_name='', tage=0)  # eigene Mail ohne Namen
    mail(episoden, von_name='Lea Hartmann', an_name='Jonas Brandl', tage=7, an_zuerst=True)  # Empfänger vor dem Absender
    assert episoden.eigene_absendernamen() == ['Lea H.', 'Lea Hartmann', 'Lea Hartmann']
    assert episoden.eigene_absendernamen(limit=1) == ['Lea H.']


def test_route_schlaegt_den_namen_aus_eigenen_mails_vor(api) -> None:
    _, client, episoden = api
    for tage in (1, 2, 3):
        mail(episoden, von_name='Lea Hartmann', tage=tage)
    stand = client.get('/api/v1/einrichtung').json()
    assert stand['name_vorschlag'] == {'name': 'Lea Hartmann', 'vorname': 'Lea', 'quelle': 'postfach'}


def test_vorschlag_wird_nicht_gespeichert_und_nicht_gegruesst(api) -> None:
    """Kein Fakt ohne Bestätigung: Der Vorschlag steht weder im Merkzettel noch im Gruß, bis der Mensch ihn bestätigt."""
    app, client, episoden = api
    mail(episoden, von_name='Lea Hartmann')
    stand = client.get('/api/v1/einrichtung').json()
    assert stand['name'] == '' and stand['name_vorschlag']['vorname'] == 'Lea'
    assert stand['schritte'] == {}
    assert (app.state.settings.einrichtung or {}).get('name', '') == ''
    assert ', Lea' not in client.get('/api/v1/morning-briefing').json()['greeting']
    # Erst der Klick auf „Weiter“ speichert; danach gibt es keinen Vorschlag mehr.
    stand = client.put('/api/v1/einrichtung', json={'name': 'Lea', 'schritt': {'id': 'name', 'stand': 'erledigt'}}).json()
    assert stand['name'] == 'Lea' and stand['name_vorschlag'] is None
    assert ', Lea.' in client.get('/api/v1/morning-briefing').json()['greeting']


def test_ohne_quelle_kein_vorschlag(api) -> None:
    _, client, _ = api
    assert client.get('/api/v1/einrichtung').json()['name_vorschlag'] is None


def test_umgebung_als_vorschlag_und_geaenderter_name_gilt_im_gruss(api, monkeypatch) -> None:
    """`KINGFISHER_USER_NAME` ist ein Vorschlag; wer ihn ändert, wird mit dem geänderten Namen gegrüßt."""
    _, client, _ = api
    monkeypatch.setenv('KINGFISHER_USER_NAME', 'Lena')
    assert client.get('/api/v1/einrichtung').json()['name_vorschlag'] == {'name': 'Lena', 'vorname': 'Lena', 'quelle': 'umgebung'}
    client.put('/api/v1/einrichtung', json={'name': 'Lene'})
    assert ', Lene.' in client.get('/api/v1/morning-briefing').json()['greeting']
