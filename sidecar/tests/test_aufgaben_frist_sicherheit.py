"""Eine erkannte Frist darf weder verspätet noch still ohne Datum angelegt werden."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from icarus_memory.aufgaben_von_selbst import frist_aus
from icarus_memory.proposals import ProposalState
from tests import test_aufgaben_von_selbst as basis
from tests.test_aufgaben_von_selbst import welt, client  # noqa: F401

BERLIN = ZoneInfo('Europe/Berlin')
FRIDAY = datetime(2026, 10, 30, 15, tzinfo=BERLIN)


@pytest.fixture(autouse=True)
def nutzerzone(monkeypatch):
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Berlin')


@pytest.mark.parametrize('clock, hour, minute', [('um 18 Uhr', 18, 0), ('um 18:30 Uhr', 18, 30),
                                               (', 09:05 Uhr', 9, 5)])
def test_explizite_lokal_gebundene_uhrzeit_wird_nicht_auf_tagesende_verschoben(clock, hour, minute):
    text = f'Bitte schicke mir die Druckdaten bis zum 2. November 2026 {clock}.'
    due = frist_aus(text, datetime(2026, 10, 30, 9, tzinfo=timezone.utc))
    assert due == datetime(2026, 11, 2, hour, minute, tzinfo=BERLIN)


@pytest.mark.parametrize('text', [
    'Bitte schicke die Druckdaten bis zum 2. November 2026 um 18 oder 19 Uhr.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 um 25 Uhr.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 um 18:75 Uhr.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 um acht Uhr.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 um 18 Uhr UTC.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 um 18 Uhr America/New_York.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 um 18 Uhr oder später.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026. Wir telefonieren um 18 Uhr.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 um 18 Uhr. Wir telefonieren um 12 Uhr.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 zwischen 17 und 18 Uhr.',
    'Bitte schicke die Druckdaten bis zum 2. November 2026 gegen 18 Uhr.',
])
def test_unklare_ungueltige_oder_ungebundene_uhrzeit_wird_nicht_zu_2359(text):
    assert frist_aus(text, FRIDAY) is None


@pytest.mark.parametrize('date', ['29. März 2026', '25. Oktober 2026'])
def test_lokale_uhrzeit_in_dst_luecke_oder_doppelter_stunde_bleibt_unklar(date):
    assert frist_aus(f'Bitte schicke die Druckdaten bis zum {date} um 02:30 Uhr.', FRIDAY) is None


@pytest.mark.parametrize('clock', ['', ' um 18 Uhr'])
def test_ohne_gueltige_nutzerzone_wird_keine_lokale_uhrzeit_geraten(monkeypatch, clock):
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'ungueltig')
    assert frist_aus(f'Bitte schicke die Druckdaten bis zum 2. November 2026{clock}.', FRIDAY) is None


@pytest.mark.parametrize('clock', ['', ' um 18 Uhr'])
def test_automatik_uebernimmt_keine_frist_ohne_bekannte_nutzerzone(welt, monkeypatch, clock):
    monkeypatch.setattr(basis, 'JETZT', FRIDAY)
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'ungueltig')
    episodes, tasks, proposals, _, lauf, _ = welt
    _, candidate = basis.bitte(episodes, proposals,
        text=f'Bitte schicke mir die Druckdaten bis zum 2. November 2026{clock}.')
    assert lauf.schritt() == {'geprueft': 1, 'angelegt': 0, 'vorschlaege': 1}
    assert tasks.get('t-suggestion-' + candidate.id) is None
    assert proposals.get(candidate.id).state is ProposalState.PENDING
    assert tasks.auto_ergebnis(candidate.id) == 'frist_unklar'


_BEREICHS_UHREN = ['18 Uhr - 19', '18 Uhr – 19', '18 Uhr — 19', '18 Uhr – nach Absprache']


@pytest.mark.parametrize('clock', _BEREICHS_UHREN)
def test_bereichsmarker_nach_uhrzeit_duerfen_nicht_weg_normalisiert_werden(clock):
    assert frist_aus(f'Bitte schicke mir die Druckdaten bis zum 2. November 2026 um {clock}.', FRIDAY) is None


@pytest.mark.parametrize('clock', _BEREICHS_UHREN)
def test_automatik_uebernimmt_keine_durch_bereichsmarker_qualifizierte_uhrzeit(welt, monkeypatch, clock):
    monkeypatch.setattr(basis, 'JETZT', FRIDAY)
    episodes, tasks, proposals, _, lauf, _ = welt
    _, candidate = basis.bitte(episodes, proposals,
        text=f'Bitte schicke mir die Druckdaten bis zum 2. November 2026 um {clock}.')
    assert lauf.schritt() == {'geprueft': 1, 'angelegt': 0, 'vorschlaege': 1}
    assert tasks.get('t-suggestion-' + candidate.id) is None
    assert proposals.get(candidate.id).state is ProposalState.PENDING
    assert tasks.auto_ergebnis(candidate.id) == 'frist_unklar'


_QUALIFIZIERTE_UHREN = ['18 Uhr (UTC)', '18 Uhr, UTC', '18 Uhr, oder später',
                       '18 Uhr BST', '18 Uhr NZDT', '18Uhr(UTC)', '18 Uhr [GMT]', '18 Uhr; (oder später)',
                       '18 Uhr „UTC“', "18 Uhr: 'oder später'"]


@pytest.mark.parametrize('clock', _QUALIFIZIERTE_UHREN)
def test_satzzeichen_und_unbekannte_zonen_ergeben_keine_exakte_lokale_frist(clock):
    assert frist_aus(f'Bitte schicke mir die Druckdaten bis zum 2. November 2026 um {clock}.', FRIDAY) is None


@pytest.mark.parametrize('clock', _QUALIFIZIERTE_UHREN)
def test_automatik_uebernimmt_keine_durch_satzzeichen_verdeckte_zeitqualifikation(welt, monkeypatch, clock):
    monkeypatch.setattr(basis, 'JETZT', FRIDAY)
    episodes, tasks, proposals, _, lauf, _ = welt
    _, candidate = basis.bitte(episodes, proposals,
        text=f'Bitte schicke mir die Druckdaten bis zum 2. November 2026 um {clock}.')
    assert lauf.schritt() == {'geprueft': 1, 'angelegt': 0, 'vorschlaege': 1}
    assert tasks.get('t-suggestion-' + candidate.id) is None
    assert proposals.get(candidate.id).state is ProposalState.PENDING
    assert tasks.auto_ergebnis(candidate.id) == 'frist_unklar'
    assert 'Frist' in lauf.vorbefuellt(candidate)['temporal_reason']


@pytest.mark.parametrize('tail, reason', [
    ('bis Freitag', 'frist_unklar'),
    ('bis nächste Woche', 'frist_unklar'),
    ('bis zum 2. November 2026 um 25 Uhr', 'frist_unklar'),
    ('bis zum 30. Oktober 2026 um 14 Uhr', 'frist_verstrichen'),
])
def test_nicht_aufloesbare_oder_exakt_abgelaufene_frist_bleibt_vorschlag(welt, monkeypatch, tail, reason):
    monkeypatch.setattr(basis, 'JETZT', FRIDAY)
    episodes, tasks, proposals, _, lauf, _ = welt
    source, candidate = basis.bitte(episodes, proposals,
        text=f'Bitte schicke mir die Druckdaten {tail}.')
    assert lauf.schritt() == {'geprueft': 1, 'angelegt': 0, 'vorschlaege': 1}
    assert tasks.get('t-suggestion-' + candidate.id) is None
    assert proposals.get(candidate.id).state is ProposalState.PENDING
    assert tasks.auto_ergebnis(candidate.id) == reason
    judgement = lauf.urteile([(candidate, source)], FRIDAY)[0]
    assert not judgement.eindeutig and 'Frist' in judgement.satz
    assert 'Frist' in lauf.vorbefuellt(candidate)['temporal_reason']


@pytest.mark.parametrize('tail, expected', [
    ('bis zum 30. Oktober 2026', datetime(2026, 10, 30, 23, 59, tzinfo=BERLIN)),
    ('bis zum 30. Oktober 2026 um 18 Uhr', datetime(2026, 10, 30, 18, tzinfo=BERLIN)),
])
def test_freitag_nachmittag_gilt_die_noch_laufende_frist_weiter(welt, monkeypatch, tail, expected):
    monkeypatch.setattr(basis, 'JETZT', FRIDAY)
    episodes, tasks, proposals, _, lauf, _ = welt
    _, candidate = basis.bitte(episodes, proposals, text=f'Bitte schicke mir die Druckdaten {tail}.')
    assert lauf.schritt()['angelegt'] == 1
    assert tasks.get('t-suggestion-' + candidate.id).due == expected


def test_donnerstagsmail_bis_freitag_bleibt_am_freitagnachmittag_bis_2359_aktiv(welt, monkeypatch):
    monkeypatch.setattr(basis, 'JETZT', FRIDAY)
    episodes, tasks, proposals, _, lauf, _ = welt
    _, candidate = basis.bitte(episodes, proposals, text='Bitte schicke mir die Druckdaten bis Freitag.', tage=1)
    assert lauf.schritt()['angelegt'] == 1
    assert tasks.get('t-suggestion-' + candidate.id).due == datetime(2026, 10, 30, 23, 59, tzinfo=BERLIN)


def test_vorschlagsroute_erklaert_die_nicht_aufgeloeste_frist(client, monkeypatch):
    monkeypatch.setattr(basis, 'JETZT', FRIDAY)
    app = client.app
    _, candidate = basis.bitte(app.state.episodes, app.state.proposals,
                               text='Bitte schicke mir die Druckdaten bis Freitag.')
    response = client.get('/api/v1/task-candidates/page')
    assert response.status_code == 200, response.text
    row = next(row for row in response.json()['items'] if row['id'] == candidate.id)
    assert row['frist_vorschlag'] is None
    assert 'Frist' in row['temporal_reason'] and 'prüfen' in row['temporal_reason']
