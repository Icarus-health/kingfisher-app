"""Persona-Prüfung, Befund A6: Die Vorbereitung im Kalender findet selbst, was offen ist, und die Terminkarte nennt
Namen statt Adressen.

Zusicherungen:
1. `GET /api/v1/calendar/vorbereitung` bereitet jeden Termin (nicht nur heute und morgen) aus den Akten seiner
   Teilnehmer vor: offene Bitten an dich, deine Bitten, Zusagen, mit Quelle; ohne gewähltes Projekt oder Person.
2. Ein Termin mit fremden Teilnehmern bleibt ehrlich leer („nicht im Gedächtnis“), nichts wird geraten.
3. Die Kalenderübersicht liefert die Namen der Teilnehmer, soweit der Bestand die Adresse kennt; unbekannte bleiben
   Adressen.
"""
from datetime import datetime, timedelta, timezone

from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_terminvorbereitung import ANNA, BEN, ICH, api, kalender, seed, termin  # noqa: F401


def _vorbereitung(client, event):
    antwort = client.get('/api/v1/calendar/vorbereitung', params={'uid': 'test:' + event.uid,
                                                                  'start': event.start.isoformat()})
    assert antwort.status_code == 200, antwort.text
    return antwort.json()['vorbereitung']


def test_vorbereitung_findet_die_offene_bitte_des_teilnehmers_ohne_wahl(api):
    app, client = api
    quellen = seed(app)
    event = termin(tage=9, teilnehmer=('anna@agentur.example', 'ben@druck.example'))   # nur Adressen, wie im Kalender
    kalender(app, event)
    daten = _vorbereitung(client, event)
    personen = {p['name']: p for p in daten['personen']}
    assert set(personen) == {'Anna Keller', 'Ben Braun'}
    bitte = next(z for z in personen['Anna Keller']['will'] if z['rolle'] == 'sie_bittet')
    assert bitte['beleg']['episode_id'] == quellen['bitte'].id and bitte['text'].startswith('Bitte schick mir die Druckdaten')
    assert daten['bereit'] is True


def test_fremde_teilnehmer_bleiben_ehrlich_unbekannt(api):
    app, client = api
    seed(app)
    event = termin(tage=4, teilnehmer=('Neu Person <neu@fremd.example>', 'Herr Braun'))
    kalender(app, event)
    daten = _vorbereitung(client, event)
    assert daten['personen'] == [] and sorted(daten['unbekannt']) == ['Herr Braun', 'Neu Person']


def test_kalender_nennt_namen_statt_adressen(api):
    app, client = api
    seed(app)
    kalender(app, termin(tage=2, teilnehmer=('anna@agentur.example', 'ben@druck.example', 'neu@fremd.example')))
    jetzt = datetime.now(timezone.utc)
    antwort = client.get('/api/v1/calendar', params={'from': (jetzt - timedelta(days=1)).isoformat(),
                                                     'until': (jetzt + timedelta(days=5)).isoformat()})
    item = antwort.json()['items'][0]
    assert item['attendees'] == ['anna@agentur.example', 'ben@druck.example', 'neu@fremd.example']
    assert item['attendee_names'] == ['Anna Keller', 'Ben Braun', 'neu@fremd.example']
