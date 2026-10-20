"""„Was brauche ich morgen?“: Termine, Fristen und Aufgaben eines kommenden Zeitraums, ohne Modell.

Zusicherungen:
1. `time_scope.kommender_zeitraum` löst nur künftige Angaben auf (morgen, nächste Woche, am Freitag, am 24.10.);
   Vergangenes bleibt Sache von `mentioned_period`. Der gleiche Wochentag wie heute ist mehrdeutig.
2. `kommendes.antwort` nennt in fester Reihenfolge Termine, Fristen und Zusagen, Aufgaben und „wartet auf“, jede
   Zeile mit Quelle, nichts außerhalb des Zeitraums; ohne Inhalt einen ehrlichen Satz, nie „du bist frei“.
3. Der Zeitraum reicht nie weiter als `MAX_CALENDAR_WINDOW`; die Antwort sagt, wenn sie kürzt.
4. Im Gespräch geht die Frage vor dem Fragenverständnis und ohne Modell den neuen Weg; Vergangenes den alten.
5. Die Wegezeit wird nur gelesen; kein Kartendienst wird für die Antwort angefragt.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from icarus_memory import fristlage, identitaet, kommendes, wegezeit
from icarus_memory.akten_routes import bausteine, nachfuehren
from icarus_memory.calendar_window import MAX_CALENDAR_WINDOW
from icarus_memory.connectors.calendar import Event
from icarus_memory.memory_routing import route
from icarus_memory.model import Provenance, SourceType, user_timezone
from icarus_memory.time_scope import kommender_zeitraum, mentioned_period
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_terminvorbereitung import ANNA, BEN, ICH, _mail, api, kalender, termin  # noqa: F401 - Fixture, Helfer

BERLIN = ZoneInfo('Europe/Berlin')
DIENSTAG = datetime(2026, 10, 20, 9, 0, tzinfo=BERLIN)
FREITAG = datetime(2026, 10, 23, 9, 0, tzinfo=BERLIN)


def tage(frage, jetzt=DIENSTAG):
    gefunden = kommender_zeitraum(frage, jetzt)
    if gefunden is None:
        return None
    von, bis, beschriftung = gefunden
    return von.date(), bis.date(), beschriftung['text'], beschriftung.get('mehrdeutig', False)


# -- 1. Der kommende Zeitraum -------------------------------------------------------------------------


@pytest.mark.parametrize('frage, erwartet', [
    ('Was brauche ich morgen?', (date(2026, 10, 21), date(2026, 10, 22), 'morgen', False)),
    ('Was steht übermorgen an?', (date(2026, 10, 22), date(2026, 10, 23), 'übermorgen', False)),
    ('Was steht nächste Woche an?', (date(2026, 10, 26), date(2026, 11, 2), 'nächste Woche', False)),
    ('Was steht kommende Woche an?', (date(2026, 10, 26), date(2026, 11, 2), 'nächste Woche', False)),
    ('Was habe ich nächsten Monat?', (date(2026, 11, 1), date(2026, 12, 1), 'nächsten Monat', False)),
    ('Was ist in 3 Tagen los?', (date(2026, 10, 23), date(2026, 10, 24), 'in 3 Tagen', False)),
    ('Was steht in zwei Wochen an?', (date(2026, 11, 3), date(2026, 11, 4), 'in zwei Wochen', False)),
    ('Was steht am Freitag an?', (date(2026, 10, 23), date(2026, 10, 24), 'am Freitag', False)),
    ('Was steht nächsten Freitag an?', (date(2026, 10, 23), date(2026, 10, 24), 'am Freitag', False)),
    ('Was steht am kommenden Freitag an?', (date(2026, 10, 23), date(2026, 10, 24), 'am Freitag', False)),
    ('Was steht am Montag an?', (date(2026, 10, 26), date(2026, 10, 27), 'am Montag', False)),
    ('Was steht am 24.10. an?', (date(2026, 10, 24), date(2026, 10, 25), 'am 24. Oktober 2026', False)),
    ('Was steht am 24. Oktober an?', (date(2026, 10, 24), date(2026, 10, 25), 'am 24. Oktober 2026', False)),
    ('Was steht am 24.10.2026 an?', (date(2026, 10, 24), date(2026, 10, 25), 'am 24. Oktober 2026', False)),
    # Ein Datum ohne Jahr, das dieses Jahr schon vorbei ist, meint das nächste.
    ('Was steht am 3.1. an?', (date(2027, 1, 3), date(2027, 1, 4), 'am 3. Januar 2027', False)),
    ('Was ist heute los?', (date(2026, 10, 20), date(2026, 10, 21), 'heute', False)),
    ('Was steht diese Woche an?', (date(2026, 10, 20), date(2026, 10, 26), 'diese Woche', False)),
])
def test_kuenftige_angaben_werden_zu_zeitraeumen(frage, erwartet):
    assert tage(frage) == erwartet


@pytest.mark.parametrize('frage', [
    'Was war letzte Woche?', 'Was kam gestern?', 'Was ist vor zwei Wochen passiert?', 'Was lief letzten Monat?',
    'Was war vorgestern?', 'Was stand am 1.10.2026 an?', 'Was steht am Morgen an?', 'Was steht in 400 Jahren an?',
    'Was steht in 0 Tagen an?',
])
def test_vergangenes_und_unklares_ist_kein_kommender_zeitraum(frage):
    assert kommender_zeitraum(frage, DIENSTAG) is None


def test_letzte_woche_bleibt_sache_von_mentioned_period():
    assert kommender_zeitraum('Was war letzte Woche?', DIENSTAG) is None
    assert mentioned_period('Was war letzte Woche?', DIENSTAG) is not None
    # Unverändert (test_answer_time_scope): „nächste Woche“ ordnet die Suche nicht.
    assert mentioned_period('Was ist nächste Woche?', DIENSTAG) is None


def test_heute_und_diese_woche_beginnen_jetzt_nicht_um_mitternacht():
    von, bis, _ = kommender_zeitraum('Was steht heute an?', DIENSTAG)
    assert von == DIENSTAG and bis == datetime(2026, 10, 21, 0, 0, tzinfo=BERLIN)
    von, bis, _ = kommender_zeitraum('Was steht diese Woche an?', DIENSTAG)
    assert von == DIENSTAG and bis == datetime(2026, 10, 26, 0, 0, tzinfo=BERLIN)


def test_gleicher_wochentag_wie_heute_ist_mehrdeutig():
    von, bis, beschriftung = kommender_zeitraum('Was steht am Freitag an?', FREITAG)
    assert beschriftung['mehrdeutig'] is True and beschriftung['text'] == 'am Freitag'
    assert beschriftung['rueckfrage'] == 'Meinst du heute oder nächsten Freitag?'
    assert (von.date(), bis.date()) == (date(2026, 10, 23), date(2026, 10, 24))
    # „nächsten Freitag“ am Freitag meint die kommende Woche: nicht mehrdeutig.
    assert tage('Was steht nächsten Freitag an?', FREITAG) == (date(2026, 10, 30), date(2026, 10, 31), 'am Freitag', False)
    assert tage('Was steht am Freitag an?', DIENSTAG)[3] is False


def test_zeitzone_des_nutzers_bestimmt_den_tag(monkeypatch):
    monkeypatch.setenv('KINGFISHER_TIMEZONE', 'Europe/Berlin')
    # 22:30 UTC am 20.10. ist in Berlin schon der 21.10.: „morgen“ ist der 22.10.
    spaet = datetime(2026, 10, 20, 22, 30, tzinfo=timezone.utc)
    von, bis, _ = kommender_zeitraum('Was brauche ich morgen?', spaet)
    assert von.isoformat() == '2026-10-22T00:00:00+02:00' and bis.isoformat() == '2026-10-23T00:00:00+02:00'


def test_relative_zeit_bleibt_unveraendert():
    from icarus_memory.relative_zeit import aufloesen
    assert [(a.von, a.bis) for a in aufloesen('nächste Woche', DIENSTAG)] == [(date(2026, 10, 26), date(2026, 11, 1))]
    assert aufloesen('am Freitag', DIENSTAG) == []


# -- Die Frageform ---------------------------------------------------------------------------------


@pytest.mark.parametrize('frage, ist', [
    ('Was brauche ich morgen?', True), ('Was steht morgen an?', True), ('Was steht morgen bei mir an?', True),
    ('Was steht eigentlich übermorgen alles an?', True), ('Was habe ich nächste Woche?', True),
    ('Was habe ich morgen vor?', True), ('Was ist morgen los?', True), ('Welche Termine habe ich am Freitag?', True),
    ('Welche Termine stehen nächste Woche an?', True), ('Was muss ich morgen erledigen?', True),
    ('Was muss ich für morgen vorbereiten?', True), ('Bin ich am Freitag frei?', True), ('Habe ich morgen frei?', True),
    ('Was steht am 24.10. an?', True), ('Was kommt nächste Woche auf mich zu?', True),
    ('Was steht heute noch an?', True),
    # Kein kommender Zeitraum, oder keine Frage nach dem, was ansteht.
    ('Was steht an?', False), ('Was habe ich morgen geschrieben?', False), ('Was war letzte Woche?', False),
    ('Worauf warte ich noch?', False), ('Was hat Anna morgen zugesagt?', False),
    ('Schreib Anna, was morgen ansteht', False), ('Merk dir: morgen steht nichts an', False),
    ('Was steht morgen beim Klinikum an?', False), ('Was kam heute?', False), ('Wann ist morgen der Termin?', False),
])
def test_feste_frageformen_mit_kommendem_zeitraum(frage, ist):
    assert kommendes.ist_frage(frage) is ist


@pytest.mark.parametrize('frage', ['Was brauche ich morgen?', 'Was steht nächste Woche an?', 'Bin ich am Freitag frei?',
                                   'Was muss ich morgen erledigen?'])
def test_nie_im_freien_chat(frage):
    assert route(frage) == 'memory_evidence'


def test_vergangenes_geht_weiter_den_alten_weg():
    assert route('Was war letzte Woche?') == 'chat'


# -- 2. Die Antwort aus Kalender, Akten und Aufgaben --------------------------------------------------


def jetzt() -> datetime:
    return datetime.now(user_timezone() or timezone.utc)


def tag(delta: int) -> str:
    return (jetzt().date() + timedelta(days=delta)).strftime('%d.%m.%Y')


def antwort(app, frage: str) -> kommendes.Antwort:
    nachfuehren(app, warten=True)
    ergebnis = kommendes.antwort(app, frage, jetzt())
    assert ergebnis is not None
    return ergebnis


def quellen(text: str) -> list[int]:
    return [int(n) for n in re.findall(r'\[Quelle (\d+)\]', text)]


def aufgabe(app, titel: str, *, tage: int, wartet_auf: str | None = None):
    task = app.state.tasks.add(titel, Provenance(SourceType.USER_STATED),
                               due=(jetzt() + timedelta(days=tage)).replace(hour=12, minute=0, second=0, microsecond=0))
    if wartet_auf:
        app.state.tasks.warten_auf(task.id, wartet_auf)
    return task


def test_morgen_in_fester_reihenfolge_jede_zeile_mit_quelle_nichts_ausserhalb(api):
    app, _ = api
    kalender(app, termin(tage=1, stunde=14), termin(uid='t2', titel='Weit weg', tage=5, stunde=10))
    bitte = _mail(app, 'Daten', [(f'Bitte schick mir die Druckdaten bis zum {tag(1)}.', 'request')], [ANNA, ICH], tage=3)
    zusage = _mail(app, 'Muster', [(f'Ich schicke die Muster bis zum {tag(1)}.', 'commitment')], [ICH, BEN], tage=2)
    _mail(app, 'Spaeter', [(f'Bitte schick die Rechnung bis zum {tag(6)}.', 'request')], [ANNA, ICH], tage=3)
    _mail(app, 'Heute', [(f'Bitte schick die Teilnehmerliste bis zum {tag(0)}.', 'request')], [ANNA, ICH], tage=3)
    aufgabe(app, 'Folien fertig machen', tage=1)
    aufgabe(app, 'Schon heute fällig', tage=0)
    aufgabe(app, 'Angebot von Ben', tage=1, wartet_auf='Ben')
    aufgabe(app, 'Erst nächste Woche', tage=5)
    a = antwort(app, 'Was brauche ich morgen?')
    text = a.text
    # Reihenfolge: Termine, Fristen und Zusagen, Aufgaben, Wartet auf.
    koepfe = [text.index(s) for s in ('Termine:', 'Fristen und Zusagen:', 'Aufgaben:', 'Wartet auf:')]
    assert koepfe == sorted(koepfe), text
    for inhalt, abschnitt in (('Gespräch Druckerei', 0), ('Druckdaten', 1), ('die Muster', 1),
                              ('Folien fertig machen', 2), ('Angebot von Ben', 3)):
        stelle = text.index(inhalt)
        assert koepfe[abschnitt] < stelle and all(stelle < k for k in koepfe[abschnitt + 1:]), (inhalt, text)
    # Der Termin mit Ort und Teilnehmern; die Frist an dich und deine Zusage in Alltagssprache.
    assert 'Druckerei Braun, Werkstraße 4, Mainz' in text and 'Anna Keller' in text and 'Ben Braun' in text
    assert 'Anna Keller bittet um etwas bis' in text and 'Du hast bis' in text and 'zugesagt' in text
    # Nichts außerhalb des Zeitraums.
    for fremd in ('Weit weg', 'Rechnung', 'Erst nächste Woche', 'Teilnehmerliste', 'Schon heute fällig'):
        assert fremd not in text, fremd
    # Jede Zeile mit Quelle, fortlaufend nummeriert; die Links zeigen auf die Episoden.
    assert quellen(text) == [1, 2] and sorted(l['episode_id'] for l in a.links) == sorted([bitte.id, zusage.id])
    assert all(l['label'] == f'Quelle {n} öffnen' for n, l in enumerate(a.links, 1))
    assert not re.search(r'\bfrei\b', text)


def test_termin_im_gedaechtnis_bekommt_eine_quelle(api):
    app, _ = api
    from icarus_memory.calendar_memory import herkunft
    from icarus_memory.episodes import EpisodeKind
    t = termin(tage=1, stunde=10)
    kalender(app, t)
    episode, _ = app.state.episodes.record(
        EpisodeKind.EVENT, t.summary, 'Termin: Gespräch Druckerei\nNotiz:\nMuster mitbringen',
        Provenance(SourceType.CALENDAR, source_ref=herkunft('test', t.uid)), occurred_at=t.start)
    a = antwort(app, 'Was steht morgen an?')
    assert '[Quelle 1]' in a.text and a.links[0]['episode_id'] == episode.id
    assert 'Muster mitbringen' not in a.text  # Die Notiz des Termins bleibt im Gedächtnis, nicht in der Antwort.


def test_leer_ist_ehrlich_und_behauptet_nie_frei(api):
    app, _ = api
    kalender(app)
    for frage, text in (('Was brauche ich morgen?', 'Für morgen steht nichts im Kalender und keine Frist an.'),
                        ('Bin ich nächste Woche frei?', 'Für nächste Woche steht nichts im Kalender und keine Frist an.')):
        a = antwort(app, frage)
        assert a.text.startswith(text), a.text
        assert not re.search(r'\bfrei\b', a.text) and a.links == []


def test_ohne_kalender_sagt_es_die_antwort_und_nennt_die_fristen(api):
    app, _ = api
    app.state.calendar = None
    _mail(app, 'Daten', [(f'Bitte schick mir die Druckdaten bis zum {tag(1)}.', 'request')], [ANNA, ICH], tage=3)
    a = antwort(app, 'Was brauche ich morgen?')
    assert 'Es ist kein Kalender verbunden.' in a.text and 'Druckdaten' in a.text


def test_kalenderfehler_kostet_nur_die_termine(api):
    app, _ = api

    class Kaputt:
        def events(self, **kwargs):
            raise RuntimeError('CalDAV antwortet nicht')

    from icarus_memory.connectors.collections import CalendarCollection, NamedCalendar
    app.state.calendar = CalendarCollection([NamedCalendar('k', 'Kaputt', Kaputt())])
    _mail(app, 'Daten', [(f'Bitte schick mir die Druckdaten bis zum {tag(1)}.', 'request')], [ANNA, ICH], tage=3)
    a = antwort(app, 'Was brauche ich morgen?')
    assert 'nicht erreichbar' in a.text and 'Druckdaten' in a.text and 'CalDAV' not in a.text


def test_mehrdeutiger_wochentag_fragt_nach_statt_zu_raten(api):
    app, _ = api
    kalender(app, termin(tage=0, stunde=23), termin(uid='t7', titel='In einer Woche', tage=7, stunde=10))
    wochentag = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')[jetzt().weekday()]
    a = antwort(app, f'Was steht am {wochentag} an?')
    assert a.text == f'Meinst du heute oder nächsten {wochentag}?' and a.links == [] and a.rueckfrage is True
    assert 'Gespräch Druckerei' not in a.text and 'In einer Woche' not in a.text


def test_zeitraum_reicht_nie_weiter_als_das_kalenderfenster(api):
    app, _ = api
    kalender(app)
    grenze_tage = MAX_CALENDAR_WINDOW.days
    a = antwort(app, f'Was steht in {grenze_tage + 50} Tagen an?')
    assert f'weiter als {grenze_tage} Tage voraus' in a.text and a.zeitraum is None
    a = antwort(app, f'Was steht in {grenze_tage} Tagen an?')
    assert a.zeitraum is not None and a.zeitraum['gekuerzt'] is True
    assert datetime.fromisoformat(a.zeitraum['bis']) - jetzt() <= MAX_CALENDAR_WINDOW
    assert f'nur bis {grenze_tage} Tage voraus' in a.text


def test_fristlage_sammeln_reicht_tage_voraus_durch(api):
    app, _ = api
    _mail(app, 'Nah', [(f'Bitte schick die Muster bis zum {tag(2)}.', 'request')], [ANNA, ICH], tage=3)
    _mail(app, 'Fern', [(f'Bitte schick die Rechnung bis zum {tag(10)}.', 'request')], [ANNA, ICH], tage=3)
    nachfuehren(app, warten=True)
    bezuege, akten = bausteine(app)
    eigene = identitaet.eigene_adressen(app.state.settings)
    assert [f.titel for f in fristlage.sammeln(akten, bezuege, jetzt=jetzt(), eigene=eigene)] == ['Nah']
    assert [f.titel for f in fristlage.sammeln(akten, bezuege, jetzt=jetzt(), eigene=eigene, tage_voraus=14)] == ['Nah', 'Fern']
    assert fristlage.sammeln(akten, bezuege, jetzt=jetzt(), eigene=eigene, tage_voraus=1) == []


def test_wegezeit_wird_nur_gelesen_nie_angefragt(api):
    app, _ = api
    ort = 'Druckerei Braun, Werkstraße 4, Mainz'
    kalender(app, termin(tage=1, stunde=14, ort=ort))
    app.state.settings.wegezeit = {'aktiv': True, 'heimat': 'Wiesbaden, Rheinstraße 1', 'verkehrsmittel': 'auto'}
    einstellung = lambda: wegezeit.Einstellung.aus(app.state.settings.wegezeit)  # noqa: E731

    class Antwortet:
        name = 'test'

        def verfuegbar(self):
            return True

        def fahrzeit(self, von, nach, verkehrsmittel, abfahrt):
            return wegezeit.Fahrzeit(25, verkehrsmittel, 'Testdienst')

    class Verboten(Antwortet):
        def fahrzeit(self, *args):
            raise AssertionError('Für die Antwort im Gespräch darf kein Kartendienst angefragt werden.')

    # Noch nichts berechnet: Die Antwort sagt das und fragt nichts an.
    app.state.wegezeit = wegezeit.WegezeitDienst({'apple': Verboten()}, einstellung=einstellung)
    a = antwort(app, 'Was brauche ich morgen?')
    assert 'Fahrzeit noch nicht berechnet' in a.text and 'Losfahren' not in a.text
    # Die Heute-Seite hat gerechnet (Zwischenspeicher): Die Antwort nennt Losfahren, ohne neu zu fragen.
    app.state.wegezeit = wegezeit.WegezeitDienst({'apple': Antwortet()}, einstellung=einstellung)
    beginn = datetime.fromisoformat(app.state.calendar.events(days=3)[0].start.isoformat())
    assert app.state.wegezeit.auskunft(ort, beginn=beginn).status == 'berechnet'
    app.state.wegezeit._anbieter = {'apple': Verboten()}
    a = antwort(app, 'Was brauche ich morgen?')
    assert 'Fahrzeit etwa 25 Minuten' in a.text and 'Losfahren um' in a.text


# -- 4. Im Gespräch --------------------------------------------------------------------------------------


def _gespraech(client):
    return client.post('/api/v1/conversations', json={}).json()['conversation']['id']


def test_im_gespraech_ohne_modell_und_vor_dem_fragenverstaendnis(api, monkeypatch):
    app, client = api
    from icarus_memory import server as server_modul
    from icarus_memory.providers import ProviderError

    def kaputt(*args, **kwargs):
        raise ProviderError('Kein Modell für diese Antwort')

    monkeypatch.setattr(app.state.agent._provider, 'complete', kaputt)
    monkeypatch.setattr(app.state.agent._provider, 'complete_json', kaputt, raising=False)
    verstanden = []
    # Weder der Server noch der Agent verstehen die Frage erst mit dem Fragenmodell: Der neue Weg kommt davor.
    monkeypatch.setattr(server_modul, '_frage_verstehen', lambda app_, text: verstanden.append(('server', text)) or None)
    monkeypatch.setattr(app.state.agent, 'frage_verstehen', lambda text: verstanden.append(('agent', text)) or None)
    kalender(app, termin(tage=1, stunde=14))
    _mail(app, 'Daten', [(f'Bitte schick mir die Druckdaten bis zum {tag(1)}.', 'request')], [ANNA, ICH], tage=3)
    client.post('/api/v1/akten/aktualisieren')
    gespraech = _gespraech(client)
    antwort_ = client.post(f'/api/v1/conversations/{gespraech}/messages', json={'message': 'Was brauche ich morgen?'})
    assert antwort_.status_code == 201, antwort_.text
    assert verstanden == []
    gespeichert = app.state.conversations.messages(gespraech)[-1]
    vertrag = gespeichert.metadata['context']['answer_contract']
    assert vertrag['status'] == 'kommendes' and vertrag['model_called'] is False
    # Im Verlauf steht kein Zitat und kein Termin, nur die Frage.
    assert 'Druckdaten' not in gespeichert.content and 'Druckerei' not in gespeichert.content
    assert 'source_links' not in gespeichert.metadata['context']
    assert gespeichert.metadata['context']['kommendes_answer']['query'] == 'Was brauche ich morgen?'
    geoeffnet = client.get(f'/api/v1/conversations/{gespraech}').json()
    letzte = geoeffnet['messages'][-1]
    assert 'Gespräch Druckerei' in letzte['content'] and 'Druckdaten' in letzte['content']
    assert letzte['metadata']['context']['source_links'][0]['label'] == 'Quelle 1 öffnen'


def test_answer_memory_versteht_die_frage_nicht_erst_mit_dem_modell(api, monkeypatch):
    """Auch ohne mitgegebene Anfrage (direkter Aufruf) kommt der neue Weg vor `frage_verstehen`."""
    app, _ = api
    kalender(app, termin(tage=1, stunde=14))

    def verboten(text):
        raise AssertionError('frage_verstehen darf vor dem neuen Weg nicht laufen')

    monkeypatch.setattr(app.state.agent, 'frage_verstehen', verboten)
    turn = app.state.agent.answer_memory('Was brauche ich morgen?')
    assert turn.context['answer_contract']['status'] == 'kommendes' and 'Gespräch Druckerei' in turn.reply


def test_vergangenes_geht_im_gespraech_weiter_den_alten_weg(api, monkeypatch):
    app, client = api
    from icarus_memory import server as server_modul
    from icarus_memory.frage import rueckfall
    verstanden = []
    monkeypatch.setattr(server_modul, '_frage_verstehen', lambda app_, text: verstanden.append(text) or rueckfall(text))
    gespraech = _gespraech(client)
    antwort_ = client.post(f'/api/v1/conversations/{gespraech}/messages', json={'message': 'Was war letzte Woche?'})
    assert antwort_.status_code == 201
    assert verstanden == ['Was war letzte Woche?']
    assert 'kommendes_answer' not in (app.state.conversations.messages(gespraech)[-1].metadata.get('context') or {})


def test_eine_aeltere_antwort_wird_beim_oeffnen_nicht_still_fuer_einen_anderen_tag_gezeigt(api, monkeypatch):
    app, client = api
    from icarus_memory import agent as agent_modul
    kalender(app, termin(tage=1, stunde=14))
    gespraech = _gespraech(client)
    # Gefragt gestern: Die Uhr des Agenten steht einen Tag zurück, der Kalender läuft echt.
    gestern = datetime.now(timezone.utc) - timedelta(days=1)
    with pytest.MonkeyPatch.context() as uhr:
        uhr.setattr(agent_modul, 'now', lambda: gestern)
        client.post(f'/api/v1/conversations/{gespraech}/messages', json={'message': 'Was brauche ich morgen?'})
    nachricht = app.state.conversations.messages(gespraech)[-1]
    assert nachricht.metadata['context']['kommendes_answer']['gefragt_am'].startswith(gestern.isoformat()[:10])
    letzte = client.get(f'/api/v1/conversations/{gespraech}').json()['messages'][-1]
    assert letzte['content'].startswith('Diese Antwort galt für den ') and 'Bitte erneut fragen' in letzte['content']
    assert 'Gespräch Druckerei' not in letzte['content']
    assert letzte['metadata']['context']['refresh_available'] is True
    assert letzte['metadata']['context']['original_question'] == 'Was brauche ich morgen?'
