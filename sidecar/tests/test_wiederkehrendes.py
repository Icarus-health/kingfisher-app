"""Geburtstage und Wiederkehrendes (M4): Vorschläge mit Beleg, Fakt erst nach Annahme, Briefing nur für den inneren Kreis.

Zusicherungen (jede mit Sabotageprobe, docs/49-kreis-und-privat.md):

1. Geburtstage werden nur aus belegten Stellen gefunden: eigener Glückwunsch am Tag, eigene Angabe der Person, ein
   Termin „Carlas Geburtstag“. Nicht nachträglich, nicht aus dem Zitat, nicht „Papas Geburtstag“.
2. Vorgeschlagen wird nur für Personen im inneren Kreis, nie für Kollegen oder Kontakte.
3. Ein Vorschlag schreibt keinen Fakt; was einmal vorgeschlagen war, auch abgelehnt, kommt nicht wieder.
4. Im Briefing steht ein Geburtstag nur bei bestätigtem innerem Kreis **und** angenommenem Geburtstag.
5. Wiederkehrendes braucht Rhythmus und Gegenstand im selben Satz; jede Zahl steht wörtlich in der Quelle.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import tagesbriefing, wiederkehrendes as wk
from icarus_memory.akten_routes import bausteine, nachfuehren
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType, user_timezone
from icarus_memory.proposals import ProposalKind
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_kreis import ICH, KOLLEGE, MAMA, api, familie, fremder, kollege, mail  # noqa: F401 - Fixtures

STADTWERKE = 'abschlag@stadtwerke-wiesental.example'


def _lokal(zeit: datetime) -> datetime:
    zone = user_timezone()
    return zeit.astimezone(zone) if zone else zeit


# -- 1. Regeln ohne Modell ---------------------------------------------------------------------------------------


def test_glueckwunsch_am_tag_ist_der_geburtstag_nachtraeglich_und_zitat_nicht():
    tag = datetime(2025, 9, 30, 8, 0)
    fund = wk.aus_glueckwunsch('Hallo Mama,\n\nalles Gute zum Geburtstag! Feier schön.\n\nLea', tag)
    assert fund is not None and fund.wert == '09-30' and fund.herkunft == 'glueckwunsch'
    assert 'alles Gute zum Geburtstag' in fund.satz
    assert wk.aus_glueckwunsch('Hallo Mama, alles Gute nachträglich zum Geburtstag!', tag) is None
    assert wk.aus_glueckwunsch('Hallo Mama, alles Gute zum Geburtstag! Bis morgen beim Essen.', tag) is None
    assert wk.aus_glueckwunsch('Danke!\n\n> Alles Gute zum Geburtstag, Lea!', tag) is None
    assert wk.aus_glueckwunsch('Alles Gute für die Prüfung!', tag) is None


def test_eigene_angabe_mit_datum_nicht_der_geburtstag_eines_anderen():
    fund = wk.aus_eigener_angabe('Hallo Lea,\n\nmein Geburtstag ist am 18. Dezember, ich feiere danach.\n\nFelix')
    assert fund is not None and fund.wert == '12-18'
    assert wk.aus_eigener_angabe('Hi, ich habe am 03.10. Geburtstag und lade dich ein.').wert == '10-03'
    assert wk.aus_eigener_angabe('denkst du an Papas Geburtstag am 14. Juli?') is None
    assert wk.aus_eigener_angabe('Ich habe an deinen Geburtstag am 2. Mai gedacht.') is None
    assert wk.aus_eigener_angabe('Mein Geburtstag ist bald.') is None


def test_termin_nennt_nur_einen_namen():
    assert wk.name_aus_termin('Carlas Geburtstag') == 'Carla'
    assert wk.name_aus_termin('Geburtstag: Felix') == 'Felix'
    assert wk.name_aus_termin('Geburtstag Gabi') == 'Gabi'
    assert wk.name_aus_termin('Papas Geburtstag im Garten') == ''
    verzeichnis = {'person:a:carla.weinert@web.example': wk.namensschluessel('Carla Weinert', 'carla.weinert@web.example'),
                   'person:a:gabi.hartmann@gmx.example': wk.namensschluessel('Gabriele Hartmann', 'gabi.hartmann@gmx.example')}
    assert wk.kandidaten_fuer_namen('Carlas', verzeichnis) == ['person:a:carla.weinert@web.example']
    assert wk.kandidaten_fuer_namen('Gabi', verzeichnis) == ['person:a:gabi.hartmann@gmx.example']
    assert wk.kandidaten_fuer_namen('Jutta', verzeichnis) == []


def test_naechster_geburtstag_und_schaltjahr():
    from datetime import date
    assert wk.naechster_geburtstag('09-30', date(2026, 9, 29)) == date(2026, 9, 30)
    assert wk.naechster_geburtstag('09-28', date(2026, 9, 29)) == date(2027, 9, 28)
    assert wk.naechster_geburtstag('02-29', date(2026, 2, 1)) == date(2026, 2, 28)


# -- 2. bis 4.: Vorschläge, Annahme, Briefing ----------------------------------------------------------------------


def _vorlegen(app):
    nachfuehren(app, warten=True)
    bezuege, _ = bausteine(app)
    return wk.geburtstage_vorlegen(bezuege, app.state.knowledge_service, app.state.proposals, app.state.claims, [ICH])


def _offen(app, sache: str):
    return [p for p in app.state.proposals.pending(ProposalKind.KNOWLEDGE, limit=500)
            if p.subject_ref == sache and p.predicate == wk.PRAEDIKAT_GEBURTSTAG]


def _glueckwunsch(app, an: str, name: str, *, tage: int):
    return mail(app, ICH, an, f'Hallo {name.split()[0]},\n\nalles Gute zum Geburtstag!', tage=tage, name=name,
                titel='Glückwunsch')


def test_vorschlag_nur_im_inneren_kreis_nie_fuer_kollegen_oder_kontakte(api):
    app, _ = api
    familie(app)
    kollege(app)
    fremder(app)
    _glueckwunsch(app, MAMA, 'Gabi Hartmann', tage=200)
    _glueckwunsch(app, KOLLEGE, 'Jan Vogt', tage=180)
    _glueckwunsch(app, 'neue.nummer@web.example', 'Unbekannt', tage=1)
    lauf = _vorlegen(app)
    assert lauf.vorgeschlagen == 1
    (vorschlag,) = _offen(app, f'person:a:{MAMA}')
    assert vorschlag.evidence[0].quote == 'alles Gute zum Geburtstag!'
    assert 'Geburtstag' in vorschlag.statement and 'Glückwunsch' in vorschlag.rationale
    assert not _offen(app, f'person:a:{KOLLEGE}') and not _offen(app, 'person:a:neue.nummer@web.example')
    # Kein Fakt ohne Annahme.
    assert not [c for c in app.state.claims.by_subject(f'person:a:{MAMA}') if c.predicate == wk.PRAEDIKAT_GEBURTSTAG]


def test_bestaetigter_kontakt_bekommt_keinen_geburtstag(api):
    app, client = api
    familie(app)
    _glueckwunsch(app, MAMA, 'Gabi Hartmann', tage=200)
    nachfuehren(app, warten=True)
    assert client.put('/api/v1/kreis', json={'sache': f'person:a:{MAMA}', 'kreis': 'kontakte'}).status_code == 200
    assert _vorlegen(app).vorgeschlagen == 0


def test_abgelehnter_geburtstag_kommt_nicht_wieder(api):
    app, client = api
    familie(app)
    _glueckwunsch(app, MAMA, 'Gabi Hartmann', tage=200)
    _vorlegen(app)
    (vorschlag,) = _offen(app, f'person:a:{MAMA}')
    assert client.post(f'/api/v1/memory/candidates/{vorschlag.id}/reject').status_code == 200
    assert _vorlegen(app).vorgeschlagen == 0 and not _offen(app, f'person:a:{MAMA}')


def test_briefing_nur_mit_bestaetigtem_inneren_kreis_und_angenommenem_geburtstag(api):
    app, client = api
    familie(app)
    episode = _glueckwunsch(app, MAMA, 'Gabi Hartmann', tage=364)
    tag = _lokal(episode.occurred_at)
    jetzt = tag.replace(year=tag.year + 1) - timedelta(days=1)
    bezuege, _ = bausteine(app)
    briefing = lambda: wk.im_briefing(app.state.episodes, app.state.claims, bezuege.beschriftungen, jetzt)  # noqa: E731
    _vorlegen(app)
    (vorschlag,) = _offen(app, f'person:a:{MAMA}')
    assert briefing() == []                                   # nichts bestätigt, nichts angenommen
    assert client.put('/api/v1/kreis', json={'sache': f'person:a:{MAMA}', 'kreis': 'innerer_kreis'}).status_code == 200
    assert briefing() == []                                   # Kreis bestätigt, Geburtstag noch Vorschlag
    angenommen = client.post(f'/api/v1/memory/candidates/{vorschlag.id}/accept', json={'supersedes': []})
    assert angenommen.status_code == 200, angenommen.text
    (eintrag,) = briefing()
    assert (eintrag['wann'], eintrag['vorname']) == ('morgen', 'Gabi')
    zeile = next(z for z in tagesbriefing.erstellen([], [], None, jetzt=jetzt, geburtstage=[eintrag]).zeilen
                 if z.art == 'geburtstag')
    assert zeile.text == 'Morgen hat Gabi Geburtstag.' and zeile.aktionen[0].ref == f'person:a:{MAMA}'
    # Wird die Person später Kontakt, verschwindet der Geburtstag aus dem Briefing.
    assert client.put('/api/v1/kreis', json={'sache': f'person:a:{MAMA}', 'kreis': 'kontakte'}).status_code == 200
    assert briefing() == []


def test_geburtstag_aus_dem_kalender_nur_bei_eindeutigem_namen(api):
    app, _ = api
    familie(app)
    for titel, tag in (('Gabis Geburtstag', 'Mittwoch, 30. September 2026 (30.09.2026)'),
                       ('Juttas Geburtstag', 'Samstag, 3. Oktober 2026 (03.10.2026)')):
        app.state.episodes.record(
            EpisodeKind.EVENT, titel, f'Termin: {titel}\nWann: ganztägig, {tag}',
            Provenance(SourceType.CALENDAR, source_ref=f'kalender:{titel}'),
            occurred_at=datetime(2026, 9, 30, tzinfo=timezone.utc))
    _vorlegen(app)
    (vorschlag,) = _offen(app, f'person:a:{MAMA}')
    assert vorschlag.value == '09-30' and vorschlag.evidence[0].quote.startswith('Wann:')
    assert 'Gabis Geburtstag' in vorschlag.rationale


def test_mehrdeutiger_name_im_kalender_bleibt_ohne_vorschlag(api):
    app, _ = api
    familie(app)
    mail(app, 'gabi.krause@web.example', ICH, 'Hallo Lea, bis bald!', tage=12, name='Gabi Krause')
    app.state.episodes.record(
        EpisodeKind.EVENT, 'Gabis Geburtstag', 'Termin: Gabis Geburtstag\nWann: ganztägig, Mittwoch, 30. September 2026',
        Provenance(SourceType.CALENDAR, source_ref='kalender:gabi'), occurred_at=datetime(2026, 9, 30, tzinfo=timezone.utc))
    assert _vorlegen(app).vorgeschlagen == 0 and not _offen(app, f'person:a:{MAMA}')


def test_route_zeigt_offen_und_angenommen(api):
    app, client = api
    familie(app)
    _glueckwunsch(app, MAMA, 'Gabi Hartmann', tage=200)
    antwort = client.post('/api/v1/wiederkehrendes/vorschlagen')
    assert antwort.status_code == 200 and antwort.json()['vorgeschlagen'] == 1
    stand = client.get('/api/v1/wiederkehrendes', params={'sache': f'person:a:{MAMA}'}).json()
    assert len(stand['offen']) == 1 and stand['angenommen'] == []
    assert stand['offen'][0]['beleg']['zitat'] == 'alles Gute zum Geburtstag!'


# -- 5. Wiederkehrendes ----------------------------------------------------------------------------------------------


def test_wiederkehrendes_braucht_rhythmus_und_gegenstand():
    funde = wk.wiederkehrendes_finden('Ihr monatlicher Abschlag bleibt bei 94,00 €. Die Restmülltonne wird ab Oktober '
                                      'alle zwei Wochen geleert. Der Elternabend findet jeden ersten Dienstag im Monat '
                                      'statt. Wir melden uns monatlich.')
    assert [(w.art, w.rhythmus, w.was) for w in funde] == [
        ('zahlung', 'monatlich', 'Abschlag'), ('muell', 'alle zwei Wochen', 'Restmülltonne'),
        ('termin', 'monatlich', 'Elternabend')]
    assert funde[0].aussage('Stadtwerke') == 'Monatlich: Abschlag, 94,00 € (Stadtwerke)'
    assert wk.wiederkehrendes_finden('Der Elternbeitrag wird am 05.10.2026 abgebucht.') == []
    assert wk.wiederkehrendes_finden('Ihr Vertrag wurde gekündigt, der monatliche Beitrag entfällt.') == []
    vertrag = wk.wiederkehrendes_finden('Der Vertrag verlängert sich jeweils um zwölf Monate, wenn er nicht drei Monate '
                                        'vor Ablauf gekündigt wird.')
    assert [(w.art, w.rhythmus) for w in vertrag] == [('vertrag', 'jährlich')]


def test_serie_im_kalender():
    zeiten = [datetime(2026, 9, d, 19, 30) for d in (9, 16, 23)]
    assert wk.serie_finden(('Chor', z) for z in zeiten) == 'wöchentlich'
    assert wk.serie_finden(('Chor', z) for z in zeiten[:2]) == ''
    assert wk.serie_finden(('x', datetime(2026, m, 5)) for m in (7, 8, 9)) == 'monatlich'
    assert wk.serie_finden(('x', datetime(2026, 9, d)) for d in (1, 8, 22)) == ''


def test_wiederkehrendes_aus_privater_akte_als_vorschlag_mit_beleg(api):
    app, client = api
    mail(app, STADTWERKE, ICH, 'Sehr geehrte Frau Hartmann,\n\nIhr monatlicher Abschlag bleibt bei 94,00 €.\n\n'
                               'Ihre Stadtwerke Wiesental', tage=20, name='Stadtwerke Wiesental',
         titel='Ihre Jahresabrechnung Strom')
    mail(app, KOLLEGE, ICH, 'Die Lizenzgebühr wird monatlich mit 120,00 € abgebucht.', tage=10, name='Jan Vogt',
         titel='Lizenz')
    nachfuehren(app, warten=True)
    assert client.post('/api/v1/wiederkehrendes/vorschlagen').json()['vorgeschlagen'] == 1
    offen = [p for p in app.state.proposals.pending(ProposalKind.KNOWLEDGE, limit=500)
             if p.predicate == wk.PRAEDIKAT_WIEDERKEHREND]
    (vorschlag,) = offen
    assert vorschlag.statement.startswith('Monatlich: Abschlag, 94,00 €')
    assert vorschlag.evidence[0].quote == 'Ihr monatlicher Abschlag bleibt bei 94,00 €.'
    from icarus_memory.akten_arten import zahlen_belegt
    assert zahlen_belegt(vorschlag.statement, app.state.episodes.get(vorschlag.evidence[0].episode_id).body) == []
    # Zweiter Lauf: nichts Neues.
    assert client.post('/api/v1/wiederkehrendes/vorschlagen').json()['vorgeschlagen'] == 0


@pytest.mark.parametrize('titel', ['Chorprobe'])
def test_serie_wird_vorschlag(api, titel):
    app, client = api
    for tage in (21, 14, 7):
        zeit = datetime.now(timezone.utc).replace(hour=17, minute=30) - timedelta(days=tage)
        app.state.episodes.record(EpisodeKind.EVENT, titel, f'Termin: {titel}\nWann: {zeit:%d.%m.%Y}, 19:30 Uhr',
                                  Provenance(SourceType.CALENDAR, source_ref=f'kalender:{titel}:{tage}'),
                                  occurred_at=zeit)
    nachfuehren(app, warten=True)
    client.post('/api/v1/wiederkehrendes/vorschlagen')
    (vorschlag,) = [p for p in app.state.proposals.pending(ProposalKind.KNOWLEDGE, limit=500)
                    if p.predicate == wk.PRAEDIKAT_WIEDERKEHREND]
    assert vorschlag.statement == 'Wöchentlich: Chorprobe (Kalender)'
    assert vorschlag.evidence[0].quote == 'Termin: Chorprobe'
