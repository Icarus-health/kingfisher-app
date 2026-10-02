"""Terminvorbereitung aus den Akten: ohne Klick, belegt, nichts geraten, überholte Werte nie als Stand."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient  # noqa: F401 - Fixture-Kette
from icarus_memory import einpacken
from icarus_memory.connectors.calendar import Event
from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType, user_timezone
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api

ICH = 'Lea Hartmann <lea@hartmann-beratung.example>'
ANNA = 'Anna Keller <anna@agentur.example>'
BEN = 'Ben Braun <ben@druck.example>'


def _mail(app, titel, abschnitte, teilnehmer, tage=1):
    """Eine eingeordnete Mail; `teilnehmer[0]` ist der Absender."""
    text = ' '.join(t for t, _ in abschnitte)
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL, source_ref=f'tv:<{titel}@example.invalid>'),
        participants=list(teilnehmer), occurred_at=datetime.now(timezone.utc) - timedelta(days=tage))
    store = WorkingMemoryStore(app.state.episodes)
    pending = store.pending(episode_ids=[episode.id])[0]
    items, pos = [], 0
    for teil, art in abschnitte:
        start = text.index(teil, pos)
        items.append({'start': start, 'end': start + len(teil), 'kind': art})
        pos = start + len(teil)
    assert store.commit(pending, items, model='local-test')
    return episode


def _notiz(app, titel, text, tage=1):
    episode, _ = app.state.episodes.record(
        EpisodeKind.DOCUMENT, titel, text, Provenance(SourceType.USER_STATED),
        occurred_at=datetime.now(timezone.utc) - timedelta(days=tage))
    return episode


class Kalender:
    def __init__(self, *events):
        self.items = list(events)

    def events(self, **kwargs):
        return self.items


def termin(uid='t1', titel='Gespräch Druckerei', tage=1, stunde=14, ort='Druckerei Braun, Werkstraße 4, Mainz',
           teilnehmer=(ANNA, BEN, ICH), dauer=90):
    zone = user_timezone() or timezone.utc
    tag = (datetime.now(zone) + timedelta(days=tage)).replace(hour=stunde, minute=0, second=0, microsecond=0)
    return Event(uid, titel, tag, tag + timedelta(minutes=dauer), location=ort, attendees=list(teilnehmer))


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    app.state.settings.mail.user = 'lea@hartmann-beratung.example'
    try:
        yield app, client
    finally:
        client.close()


def kalender(app, *events):
    app.state.calendar = CalendarCollection([NamedCalendar('test', 'Testkalender', Kalender(*events))])


def briefing(client):
    antwort = client.get('/api/v1/tag/briefing')
    assert antwort.status_code == 200
    return antwort.json()


def seed(app):
    """Anna bittet und wünscht sich etwas; Ben schrieb einmal; Lea schrieb, was sie mitbringt."""
    frist = (datetime.now().date() + timedelta(days=3)).strftime('%d.%m.%Y')
    bitte = _mail(app, 'Druckdaten', [(f'Bitte schick mir die Druckdaten bis zum {frist}.', 'request')], [ANNA, ICH], tage=6)
    wunsch = _mail(app, 'Format', [('Das Plakat hätte ich gern im Format A2.', 'fact')], [ANNA, ICH], tage=4)
    ben = _mail(app, 'Angebot', [('Das Angebot der Druckerei liegt bei 1.200 Euro.', 'status')], [BEN, ICH], tage=3)
    eigene = _mail(app, 'AW: Format', [('Ich bringe die Kalkulation und einen Probedruck mit.', 'fact')], [ICH, ANNA], tage=2)
    fremde = _mail(app, 'Muster', [('Ich bringe folgende Muster mit.', 'fact')], [BEN, ICH], tage=2)
    return {'bitte': bitte, 'wunsch': wunsch, 'ben': ben, 'eigene': eigene, 'fremde': fremde, 'frist': frist}


def test_der_termin_ist_ohne_klick_vorbereitet_mit_wunsch_bitte_letztem_kontakt_und_belegen(api):
    app, client = api
    quellen = seed(app)
    kalender(app, termin())
    daten = briefing(client)  # ein einziger Aufruf: nichts wird vorher geöffnet oder angeklickt
    assert len(daten['termine']) == 1
    vorbereitung = daten['termine'][0]
    assert vorbereitung['bereit'] is True and vorbereitung['ort'].startswith('Druckerei Braun')
    personen = {p['name']: p for p in vorbereitung['personen']}
    assert set(personen) == {'Anna Keller', 'Ben Braun'}
    anna = personen['Anna Keller']
    will = {z['rolle']: z for z in anna['will']}
    assert will['sie_bittet']['beleg']['episode_id'] == quellen['bitte'].id and will['sie_bittet']['vermutlich'] is True
    assert will['wunsch']['text'] == 'Das Plakat hätte ich gern im Format A2.'
    assert will['wunsch']['beleg']['episode_id'] == quellen['wunsch'].id and will['wunsch']['vermutlich'] is True
    assert anna['letzter_kontakt']['beleg']['episode_id'] == quellen['eigene'].id
    assert anna['organisation'] == 'Agentur'
    assert [f['episode_id'] for f in anna['fristen']] == [quellen['bitte'].id]
    assert anna['fristen'][0]['status'] == 'kommend'


def test_jede_aussage_der_vorbereitung_hat_eine_echte_quelle_und_ein_wortlaut_zitat(api):
    app, client = api
    seed(app)
    _notiz(app, 'Vorbereitung Braun', 'Laptop und Probedruck mitnehmen.', tage=1)
    kalender(app, termin())
    vorbereitung = briefing(client)['termine'][0]
    zeilen = []
    for p in vorbereitung['personen']:
        zeilen += p['will'] + p['zuletzt'] + p['stand'] + ([p['letzter_kontakt']] if p['letzter_kontakt'] else [])
    for h in vorbereitung['hintergrund']:
        zeilen += h['zeilen']
    assert zeilen
    for zeile in zeilen:
        episode = app.state.episodes.get(zeile['beleg']['episode_id'])
        wortlaut = ' '.join(episode.body.split())
        # Gekürzte Zitate enden mit „ …“; der Anfang ist wörtlich aus der Quelle.
        assert ' '.join(zeile['text'].removesuffix(' …').split()) in wortlaut, zeile
    for stueck in vorbereitung['einpacken']:
        assert ' '.join(stueck['text'].removesuffix(' …').split()) in ' '.join(app.state.episodes.get(stueck['episode_id']).body.split())


def test_teilnehmer_ohne_akte_oder_ohne_adresse_werden_nicht_geraten(api):
    app, client = api
    seed(app)
    kalender(app, termin(teilnehmer=(ANNA, 'Neu Person <neu@fremd.example>', 'Herr Braun', ICH)))
    vorbereitung = briefing(client)['termine'][0]
    assert [p['name'] for p in vorbereitung['personen']] == ['Anna Keller']
    assert sorted(vorbereitung['unbekannt']) == ['Herr Braun', 'Neu Person']


def test_ein_termin_ohne_bekannte_teilnehmer_ist_nicht_vorbereitet_und_sagt_das(api):
    app, client = api
    kalender(app, termin(teilnehmer=('Neu Person <neu@fremd.example>', ICH)))
    daten = briefing(client)
    vorbereitung = daten['termine'][0]
    assert vorbereitung['bereit'] is False and vorbereitung['personen'] == [] and vorbereitung['einpacken'] == []
    zeilen = daten['tageslage']['zeilen']
    assert [z['art'] for z in zeilen] == ['termin'] and 'Nicht im Gedächtnis' not in zeilen[0]['text']


def test_einpacken_nennt_nur_belegtes_und_nie_was_ein_anderer_selbst_mitbringt(api):
    app, client = api
    quellen = seed(app)
    _notiz(app, 'Vorbereitung Braun', 'Für Mittwoch: Preise prüfen.\nLaptop und Probedruck mitnehmen.', tage=1)
    kalender(app, termin())
    stuecke = briefing(client)['termine'][0]['einpacken']
    texte = [s['text'] for s in stuecke]
    assert 'Laptop und Probedruck mitnehmen.' in texte
    assert 'Ich bringe die Kalkulation und einen Probedruck mit.' in texte
    assert not any('Muster' in t for t in texte)  # Bens „Ich bringe … mit“ ist Bens Sache
    assert {s['episode_id'] for s in stuecke} >= {quellen['eigene'].id}
    assert all(s['art'] in ('notiz', 'mail', 'termin') and s['episode_id'] for s in stuecke)


def test_ohne_beleg_gibt_es_keinen_einpacken_abschnitt_und_keine_zeile(api):
    app, client = api
    _mail(app, 'Angebot', [('Das Angebot liegt bei 1.200 Euro.', 'status')], [BEN, ICH], tage=3)
    kalender(app, termin(teilnehmer=(BEN, ICH)))
    daten = briefing(client)
    assert daten['termine'][0]['einpacken'] == []
    assert 'einpacken' not in [z['art'] for z in daten['tageslage']['zeilen']]


def test_notiz_zum_termin_kommt_aus_dem_gedaechtnis(api):
    app, client = api
    seed(app)
    ereignis = termin()
    from icarus_memory.calendar_memory import KalenderGedaechtnis
    ereignis.notes = 'Bitte Ausweis und den unterschriebenen Vertrag mitbringen.'
    KalenderGedaechtnis(app.state.episodes, app.state.claims).abgleichen(
        'test', 'Testkalender', [ereignis], ereignis.start - timedelta(days=1), ereignis.end + timedelta(days=1))
    kalender(app, ereignis)
    stuecke = briefing(client)['termine'][0]['einpacken']
    assert any(s['art'] == 'termin' and 'Ausweis' in s['text'] for s in stuecke)


def test_ueberholte_werte_stehen_nicht_als_stand_und_nicht_unter_zuletzt(api):
    app, client = api
    _mail(app, 'Budget alt', [('Das Budget beträgt 15.000 Euro.', 'status')], [ANNA, ICH], tage=20)
    _mail(app, 'Budget neu', [('Das Budget beträgt jetzt 12.000 Euro.', 'change')], [ANNA, ICH], tage=5)
    kalender(app, termin(teilnehmer=(ANNA, ICH)))
    text = str(briefing(client)['termine'][0])
    assert '12.000' in text and '15.000' not in text


def test_der_briefing_pfad_schreibt_nichts_in_den_bestand(api):
    app, client = api
    seed(app)
    kalender(app, termin())
    vorher = (app.state.episodes.counts(), app.state.proposals.counts(), len(app.state.store.usable()))
    briefing(client)
    briefing(client)
    assert (app.state.episodes.counts(), app.state.proposals.counts(), len(app.state.store.usable())) == vorher


def test_ein_kaputter_kalender_kippt_die_fristen_nicht(api):
    app, client = api
    seed(app)

    class Kaputt:
        def events(self, **kwargs):
            raise RuntimeError('nicht erreichbar')
    app.state.calendar = CalendarCollection([NamedCalendar('test', 'Testkalender', Kaputt())])
    daten = briefing(client)
    assert daten['termine'] == [] and [f['episode_id'] for f in daten['fristen']]


def test_einpacken_regeln_direkt():
    def quelle(text, von_mir, art='mail'):
        return einpacken.Quelle('e1', 't', datetime(2026, 9, 1, tzinfo=timezone.utc), text, art, von_mir)
    assert einpacken.packliste([quelle('Bitte bringen Sie den Vertrag mit.', False)])[0].text == 'Bitte bringen Sie den Vertrag mit.'
    assert einpacken.packliste([quelle('Ich bringe die Zahlen mit.', False)]) == []
    assert einpacken.packliste([quelle('Ich bringe die Zahlen mit.', True)])
    assert einpacken.packliste([quelle('Frau Engel bringt die Zahlen mit.', True)]) == []
    assert einpacken.packliste([quelle('Wir sprechen über das Budget.', True)]) == []
    assert einpacken.packliste([]) == []
