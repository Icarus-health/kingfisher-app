"""Fristen im Briefing: kommende der nächsten sieben Tage, verstrichene offene Zusagen, nie eine überholte."""
from datetime import date, datetime, timedelta

import pytest

from icarus_memory import fristlage, identitaet
from icarus_memory.akten_routes import bausteine, nachfuehren
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api
from tests.test_terminvorbereitung import ANNA, BEN, ICH, _mail

EIGENE = ['lea@hartmann-beratung.example']


@pytest.fixture
def app(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    app.state.settings.mail.user = 'lea@hartmann-beratung.example'
    try:
        yield app
    finally:
        client.close()


def tag(delta: int) -> str:
    return (date.today() + timedelta(days=delta)).strftime('%d.%m.%Y')


def lage(app, **args) -> list[fristlage.Frist]:
    nachfuehren(app, warten=True)
    bezuege, akten = bausteine(app)
    return fristlage.sammeln(akten, bezuege, jetzt=datetime.now().astimezone(), eigene=identitaet.eigene_adressen(app.state.settings), **args)


def test_kommende_fristen_der_naechsten_sieben_tage_nach_dringlichkeit_mit_quelle(app):
    spaet = _mail(app, 'Muster', [(f'Bitte schick uns die Muster bis zum {tag(5)}.', 'request')], [BEN, ICH], tage=3)
    frueh = _mail(app, 'Daten', [(f'Bitte schick mir die Druckdaten bis zum {tag(1)}.', 'request')], [ANNA, ICH], tage=3)
    _mail(app, 'Spaeter', [(f'Bitte schick die Rechnung bis zum {tag(20)}.', 'request')], [ANNA, ICH], tage=3)
    fristen = lage(app)
    assert [f.episode_id for f in fristen] == [frueh.id, spaet.id]  # morgen vor in fünf Tagen; in 20 Tagen nicht dabei
    assert [f.status for f in fristen] == ['kommend', 'kommend'] and [f.tage for f in fristen] == [1, 5]
    assert fristen[0].text.startswith('Bitte schick mir die Druckdaten') and fristen[0].titel == 'Daten'
    assert fristen[0].richtung == 'an_mich' and 'morgen' in fristlage.beschreibung(fristen[0])


def test_verstrichene_zusage_ohne_erledigung_erscheint_als_vermutlich_offen(app):
    zusage = _mail(app, 'Unterlagen', [(f'Ich sende dir die Unterlagen bis zum {tag(-5)}.', 'commitment')], [ICH, ANNA], tage=12)
    fristen = lage(app)
    assert [f.episode_id for f in fristen] == [zusage.id]
    f = fristen[0]
    assert (f.status, f.tage, f.richtung, f.art, f.vermutlich) == ('verstrichen', -5, 'von_mir', 'Zusage', True)
    satz = fristlage.beschreibung(f)
    assert satz.startswith('Du hattest bis') and 'seit 5 Tagen' in satz and 'vermutlich noch offen' in satz


def test_erledigte_zusage_steht_nicht_als_verstrichen_da(app):
    _mail(app, 'Unterlagen', [(f'Ich sende dir die Unterlagen bis zum {tag(-5)}.', 'commitment')], [ICH, ANNA], tage=12)
    _mail(app, 'Danke', [('Die Unterlagen sind erhalten.', 'status')], [ANNA, ICH], tage=3)
    assert lage(app) == []


def test_sehr_alte_verstrichene_fristen_werden_nicht_mehr_gezeigt(app):
    _mail(app, 'Alt', [(f'Ich sende dir die Unterlagen bis zum {tag(-90)}.', 'commitment')], [ICH, ANNA], tage=100)
    assert lage(app) == []


def test_eine_ueberholte_frist_ist_nie_aktuell_weder_kommend_noch_verstrichen(app):
    _mail(app, 'Frist alt', [(f'Die Einreichfrist ist der {tag(2)}.', 'change')], [ANNA, ICH], tage=10)
    neu = _mail(app, 'Frist neu', [(f'Die Einreichfrist wurde auf den {tag(40)} verschoben.', 'change')], [ANNA, ICH], tage=2)
    fristen = lage(app)
    assert fristen == []  # 2 Tage: überholt, nicht kommend; 40 Tage: außerhalb der sieben Tage
    weit = lage(app, arten=('person', 'organisation', 'projekt'))
    assert weit == []
    bezuege, akten = bausteine(app)
    akte = akten.akte('person:a:anna@agentur.example', alle=True)
    assert [f['episode_id'] for f in akte['fristen']['ersetzt']] and [f['datum'] for f in akte['fristen']['kommend']] == [
        (date.today() + timedelta(days=40)).isoformat()]
    breit = fristlage.aus_akte(akte, heute=date.today(), tage_voraus=60)
    assert [f.episode_id for f in breit] == [neu.id] and breit[0].tage == 40


def test_aus_akte_prueft_die_ueberholung_selbst_noch_einmal():
    zeile = {'episode_id': 'e1', 'text': 'Frist', 'titel': 't', 'art': 'Bitte', 'participants': [], 'datum': (date.today() + timedelta(days=1)).isoformat(),
             'ausdruck': 'morgen', 'ersetzt_durch': {'datum': '2030-01-01'}}
    akte = {'sache': 'person:a:x@y.z', 'name': 'X', 'offen': {'eintraege': []},
            'fristen': {'kommend': [zeile], 'verstrichen': [{**zeile, 'datum': (date.today() - timedelta(days=2)).isoformat()}]}}
    assert fristlage.aus_akte(akte, heute=date.today()) == []
    frei = {**akte, 'fristen': {'kommend': [{**zeile, 'ersetzt_durch': None}], 'verstrichen': []}}
    assert [f.episode_id for f in fristlage.aus_akte(frei, heute=date.today())] == ['e1']


def test_dieselbe_quelle_in_mehreren_akten_zaehlt_einmal_die_person_gibt_den_namen(app):
    _mail(app, 'Daten', [(f'Bitte schick mir die Druckdaten bis zum {tag(2)}.', 'request')], [ANNA, ICH], tage=3)
    fristen = lage(app)
    assert len(fristen) == 1 and fristen[0].sache.startswith('person:')


def test_dringlichkeit_heute_und_morgen_vor_verstrichenem_vor_dem_rest():
    def f(status, tage, name):
        return fristlage.Frist(datum=date(2026, 9, 30) + timedelta(days=tage), text=name, ausdruck='', episode_id=name, titel='t',
                               quelle_datum=None, quelle_art='Mail', art='Bitte', richtung='an_mich', status=status, tage=tage)
    geordnet = fristlage.nach_dringlichkeit([f('kommend', 5, 'fuenf'), f('verstrichen', -20, 'alt'), f('kommend', 0, 'heute'),
                                             f('verstrichen', -2, 'juengst'), f('kommend', 1, 'morgen'), f('kommend', 3, 'drei')])
    assert [x.episode_id for x in geordnet] == ['heute', 'morgen', 'juengst', 'alt', 'drei', 'fuenf']


def test_wann_und_richtung():
    assert fristlage.richtung([], EIGENE) == 'unklar'
    assert fristlage.richtung(['Lea <lea@hartmann-beratung.example>'], EIGENE) == 'von_mir'
    assert fristlage.richtung(['Anna <anna@x.example>'], EIGENE) == 'an_mich'
