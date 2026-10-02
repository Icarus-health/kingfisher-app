"""Termine im Gedächtnis: Fassungen, Entzug, Inkrementalität, Zeitfenster, Suche (Etappe C1)."""
from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from icarus_memory import calendar_memory
from icarus_memory.calendar_memory import (
    ABSCHNITT_TAGE, MAC_QUELLE, VERGANGENHEIT_TAGE, ZUKUNFT_TAGE, KalenderGedaechtnis,
    abschnitte, fenster, kalender_job, quelle_fuer_mac, schluessel_praefix, termin_text, uid_aus_herkunft)
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.connectors.calendar import Event, parse_events
from icarus_memory.connectors.collections import NamedCalendar
from icarus_memory.episodes import EpisodeKind, EpisodeState, EpisodeStore
from icarus_memory.mac_calendar import MacCalendar, WorkerUpdate, install_routes
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalStore
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore

JETZT = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)
VON, BIS = fenster(JETZT)
QUELLE = 'kalender-a'


def termin(uid='t-1', titel='Abstimmung Vergabegremium', tage=-2 * 365, dauer=1, **kw) -> Event:
    beginn = JETZT + timedelta(days=tage, hours=2)
    return Event(uid=uid, summary=titel, start=beginn, end=beginn + timedelta(hours=dauer),
                 location=kw.pop('location', 'Rathaus Mainz'),
                 attendees=kw.pop('attendees', ['Sabine Becker <s.becker@klinikum.example>']),
                 notes=kw.pop('notes', 'Protokoll: Budget 40.000 Euro'), **kw)


@pytest.fixture
def bestand(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    yield episodes, claims, KalenderGedaechtnis(episodes, claims)
    episodes.close()
    claims.close()


def gleiche_ab(kg, termine, quelle=QUELLE, von=VON, bis=BIS, **kw):
    return kg.abgleichen(quelle, 'Arbeit', termine, von, bis, at=JETZT, **kw)


def aktuelle(episodes, quelle=QUELLE):
    return [e for e in episodes.all_episodes(limit=1000)
            if e.kind is EpisodeKind.EVENT and e.state is not EpisodeState.IGNORED
            and (uid_aus_herkunft(e.provenance.source_ref) or '')]


# -- Ablage ------------------------------------------------------------------


def test_termin_wird_mit_allen_angaben_als_rohquelle_abgelegt(bestand):
    episodes, _, kg = bestand
    ergebnis = gleiche_ab(kg, [termin()])
    assert (ergebnis.neu, ergebnis.geaendert) == (1, 0)
    (episode,) = aktuelle(episodes)
    assert episode.kind is EpisodeKind.EVENT and episode.state is EpisodeState.NEW
    assert episode.title == 'Abstimmung Vergabegremium'
    assert episode.occurred_at == termin().start
    assert episode.participants == ['Sabine Becker <s.becker@klinikum.example>']
    assert episode.provenance.source_type is SourceType.CALENDAR
    assert uid_aus_herkunft(episode.provenance.source_ref) == 't-1'
    for teil in ('Rathaus Mainz', 'Sabine Becker <s.becker@klinikum.example>', 'Budget 40.000 Euro', 'Arbeit', 'Uhr'):
        assert teil in episode.body


def test_text_nennt_wochentag_und_datum_in_der_zeitzone_des_nutzers():
    text = termin_text(Event(uid='x', summary='Essen', start=datetime(2026, 5, 12, 22, 30, tzinfo=timezone.utc),
                             end=datetime(2026, 5, 12, 23, 30, tzinfo=timezone.utc)))
    # Europe/Berlin: 12.05. 22:30 UTC ist schon der 13.05., 00:30 Uhr.
    assert 'Mittwoch, 13. Mai 2026 (13.05.2026), 00:30 bis 01:30 Uhr' in text


# -- Versionen ---------------------------------------------------------------


def test_verschobener_termin_ist_neue_fassung_derselben_quelle_keine_dublette(bestand):
    episodes, claims, kg = bestand
    gleiche_ab(kg, [termin()])
    (alt,) = aktuelle(episodes)
    ergebnis = gleiche_ab(kg, [termin(tage=-2 * 365 + 3)])
    assert (ergebnis.neu, ergebnis.geaendert, ergebnis.entzogen) == (0, 1, 0)
    (neu,) = aktuelle(episodes)
    assert neu.id != alt.id
    assert episodes.get(alt.id).state is EpisodeState.IGNORED
    assert episodes.get(alt.id).body == alt.body  # die alte Fassung bleibt als Nachweis lesbar
    key = calendar_memory.quelle_schluessel(QUELLE, 't-1')
    assert episodes.source_head(key) == neu.id


def test_geaenderte_fassung_sperrt_bestaetigtes_wissen_aus_der_alten(bestand, tmp_path):
    episodes, claims, kg = bestand
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    service = KnowledgeService(proposals=proposals, claims=claims, episodes=episodes)
    gleiche_ab(kg, [termin()])
    (alt,) = aktuelle(episodes)
    person = claims.entities.create('person', 'Sabine Becker')
    vorschlag, _ = service.propose(subject_ref=person['id'], predicate='budget', value='40.000 Euro',
                                   statement='Budget 40.000 Euro', rationale='Terminnotiz',
                                   evidence=[Evidence(alt.id, 'Budget 40.000 Euro', alt.digest)])
    aussage = service.accept(vorschlag.id, supersedes=[])
    assert claims.is_usable(aussage)
    gleiche_ab(kg, [termin(notes='Protokoll: Budget gestrichen')])
    assert not claims.is_usable(claims.get(aussage.id))
    proposals.close()


def test_auf_frueheren_stand_zurueckgesetzter_termin_gilt_wieder(bestand):
    episodes, claims, kg = bestand
    gleiche_ab(kg, [termin()])
    gleiche_ab(kg, [termin(tage=-2 * 365 + 3)])
    ergebnis = gleiche_ab(kg, [termin()])
    assert ergebnis.wiederhergestellt == 1
    (aktuell,) = aktuelle(episodes)
    assert aktuell.state is EpisodeState.NEW and aktuell.occurred_at == termin().start


# -- Entzug ------------------------------------------------------------------


def test_geloeschter_termin_wird_entzogen_die_episode_bleibt(bestand):
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin('t-1'), termin('t-2', 'Steuerberater', tage=-2 * 365 + 5)])
    ergebnis = gleiche_ab(kg, [termin('t-2', 'Steuerberater', tage=-2 * 365 + 5)])
    assert ergebnis.entzogen == 1 and ergebnis.unveraendert == 1
    (uebrig,) = aktuelle(episodes)
    assert uebrig.title == 'Steuerberater'
    weg = next(e for e in episodes.all_episodes(limit=100) if e.title == 'Abstimmung Vergabegremium')
    assert weg.state is EpisodeState.IGNORED and 'entzogen:kalender' in weg.tags


def test_leerer_abschnitt_entzieht_nichts_er_kann_ein_lesefehler_sein(bestand):
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin()])
    ergebnis = gleiche_ab(kg, [])
    assert ergebnis.leer_ohne_entzug and ergebnis.entzogen == 0
    assert len(aktuelle(episodes)) == 1


def test_fehlender_termin_ausserhalb_des_gelesenen_abschnitts_bleibt(bestand):
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin('alt', tage=-900), termin('neu', 'Neu', tage=-10)])
    # Der Abschnitt der letzten 30 Tage kennt nur „neu“; „alt“ liegt nicht darin.
    ergebnis = gleiche_ab(kg, [termin('neu', 'Neu', tage=-10)], von=JETZT - timedelta(days=30), bis=JETZT)
    assert ergebnis.entzogen == 0 and len(aktuelle(episodes)) == 2


def test_vom_nutzer_ausgeschlossener_termin_bleibt_ausgeschlossen(bestand):
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin()])
    (episode,) = aktuelle(episodes)
    episodes.ignore(episode.id)  # Ausschluss durch den Nutzer, ohne Marke
    ergebnis = gleiche_ab(kg, [termin()])
    assert ergebnis.ausgeschlossen == 1 and ergebnis.wiederhergestellt == 0
    assert episodes.get(episode.id).state is EpisodeState.IGNORED


def test_trennen_entzieht_nur_die_getrennte_quelle_und_ein_erneutes_verbinden_stellt_her(bestand):
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin('a-1')], quelle='kalender-a')
    gleiche_ab(kg, [termin('b-1', 'Zahnarzt')], quelle='kalender-b')
    assert kg.entziehen_ohne_freigabe(lambda quelle: quelle != 'kalender-a') == 1
    assert [e.title for e in aktuelle(episodes)] == ['Zahnarzt']
    assert kg.anzahl('kalender-a') == 0 and kg.anzahl('kalender-b') == 1
    # Zweimal getrennt ist nicht zweimal entzogen.
    assert kg.entziehen_ohne_freigabe(lambda quelle: quelle != 'kalender-a') == 0
    ergebnis = gleiche_ab(kg, [termin('a-1')], quelle='kalender-a')
    assert ergebnis.wiederhergestellt == 1 and kg.anzahl('kalender-a') == 1


def test_ohne_freigabe_wird_nichts_geschrieben(bestand):
    episodes, _, kg = bestand
    ergebnis = gleiche_ab(kg, [termin()], erlaubt=lambda: False)
    assert ergebnis.keine_freigabe and episodes.all_episodes(limit=10) == []


# -- Inkrementalität ---------------------------------------------------------


def test_zweiter_abgleich_fasst_unveraenderte_termine_nicht_an(bestand, monkeypatch):
    episodes, _, kg = bestand
    termine = [termin(f'u-{i}', f'Termin {i}', tage=-100 + i) for i in range(30)]
    gleiche_ab(kg, termine)
    schreibt = []
    for name in ('record', 'advance_source_head', 'ignore', 'reopen'):
        original = getattr(episodes, name)
        monkeypatch.setattr(episodes, name, lambda *a, _o=original, _n=name, **k: schreibt.append(_n) or _o(*a, **k))
    ergebnis = gleiche_ab(kg, termine)
    assert (ergebnis.neu, ergebnis.geaendert, ergebnis.unveraendert) == (0, 0, 30)
    assert schreibt == []
    # Nur der geänderte Termin wird angefasst.
    geaendert = [*termine[:29], termin('u-29', 'Termin 29', tage=-100 + 29, location='Frankfurt')]
    ergebnis = gleiche_ab(kg, geaendert)
    assert (ergebnis.geaendert, ergebnis.unveraendert) == (1, 29)
    assert schreibt.count('record') == 1


def test_gleiche_uid_doppelt_im_abschnitt_ergibt_zwei_quellen(bestand):
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin('serie', tage=-50), termin('serie', tage=-43)])
    assert len(aktuelle(episodes)) == 2


# -- Zeitfenster -------------------------------------------------------------


def test_zeitraum_steht_an_einer_stelle_drei_jahre_zurueck_ein_jahr_voraus():
    assert (VERGANGENHEIT_TAGE, ZUKUNFT_TAGE) == (1095, 365)
    assert (JETZT - VON).days == VERGANGENHEIT_TAGE and (BIS - JETZT).days == ZUKUNFT_TAGE
    teile = abschnitte(VON, BIS)
    assert teile[0][0] == VON and teile[-1][1] == BIS
    assert all(a[1] == b[0] for a, b in zip(teile, teile[1:]))
    assert all(b - a <= timedelta(days=ABSCHNITT_TAGE) for a, b in teile)


def test_termine_ausserhalb_des_fensters_kommen_nicht_hinein(bestand):
    episodes, _, kg = bestand
    ergebnis = gleiche_ab(kg, [termin('alt', tage=-VERGANGENHEIT_TAGE - 60), termin('fern', tage=ZUKUNFT_TAGE + 60),
                               termin('ok', tage=-VERGANGENHEIT_TAGE + 30)])
    assert ergebnis.ausserhalb == 2 and ergebnis.neu == 1
    assert [uid_aus_herkunft(e.provenance.source_ref) for e in aktuelle(episodes)] == ['ok']


def test_zeitplanlauf_liest_das_ganze_fenster_in_abschnitten_und_faengt_lesefehler_ab(bestand):
    episodes, _, kg = bestand
    gerufen = []

    class Leser:
        def events(self, days=7, at=None):
            gerufen.append((at, days))
            return [termin('im-fenster', tage=-800)] if at <= JETZT - timedelta(days=800) < at + timedelta(days=days) else []

    class Kaputt:
        def events(self, days=7, at=None):
            raise OSError('Netz weg')

    ergebnisse = kalender_job(kg, [NamedCalendar('a', 'A', Leser()), NamedCalendar('b', 'B', Kaputt())], at=JETZT)
    assert gerufen[0][0] == VON
    assert gerufen[-1][0] + timedelta(days=gerufen[-1][1]) >= BIS
    assert len(gerufen) == len(abschnitte(VON, BIS))
    assert ergebnisse['a'].neu == 1 and ergebnisse['b'].fehler and kg.anzahl('b') == 0
    # Ein Lesefehler ist kein Löschbeweis: nach einem Fehlerlauf bleibt der Termin von „a“ liegen.
    class Kaputt2(Kaputt):
        pass
    kalender_job(kg, [NamedCalendar('a', 'A', Kaputt2())], at=JETZT)
    assert kg.anzahl('a') == 1


# -- Suche -------------------------------------------------------------------


class Einordnung:
    """Weist jedem Absatz die Art `fact` zu (wie die Messlatte ohne Modell)."""
    name, model, is_local, supports_json = 'test', 'konstant', True, True

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        import json
        blocks = json.loads(messages[-1]['content'])['blocks']
        return Reply(text=json.dumps({'items': [{'block_id': b['block_id'], 'kind': 'fact'} for b in blocks]}),
                     model=self.model)


def test_suche_findet_einen_termin_von_vor_zwei_jahren(bestand):
    from icarus_memory.working_memory_worker import run
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin('t-1', 'Abstimmung Vergabegremium', tage=-2 * 365),
                    termin('t-2', 'Zahnarzt', tage=-30, notes='', attendees=[], location='')])
    run(episodes, Einordnung(), threading.Lock(), limit=50)
    treffer = WorkingMemoryStore(episodes).search('Vergabegremium')['refs']
    (episode_id,) = {r['episode_id'] for r in treffer}
    assert episodes.get(episode_id).title == 'Abstimmung Vergabegremium'
    # Auch die Terminnotiz ist auffindbar, nicht nur der Titel.
    assert WorkingMemoryStore(episodes).search('Budget')['refs']
    # Ein entzogener Termin fällt aus der Suche.
    gleiche_ab(kg, [termin('t-2', 'Zahnarzt', tage=-30, notes='', attendees=[], location='')])
    assert WorkingMemoryStore(episodes).search('Vergabegremium')['refs'] == []


def test_termine_sind_keine_vorlage_fuer_die_verdichtung(bestand):
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin()])
    assert episodes.pending() == []
    episodes.record(EpisodeKind.DOCUMENT, 'Notiz', 'Text', Provenance(source_type=SourceType.DOCUMENT))
    assert [e.title for e in episodes.pending()] == ['Notiz']


def test_keine_abfrage_laesst_termine_still_aus():
    """Wer message und document aufzählt, muss auch event nennen (siehe `episodes.ROHQUELLEN`)."""
    ordner = Path(calendar_memory.__file__).parent
    fehlstellen = []
    for datei in sorted(ordner.rglob('*.py')):
        for treffer in re.finditer(r"kind\s+IN\s*\(([^)]*)\)", datei.read_text(encoding='utf-8')):
            arten = set(re.findall(r"'(\w+)'", treffer.group(1)))
            if {'message', 'document'} <= arten and 'event' not in arten:
                fehlstellen.append(f'{datei.name}: {treffer.group(0)}')
    assert not fehlstellen


# -- Personen ----------------------------------------------------------------


def test_bevorstehender_termin_zaehlt_nicht_als_kontakt_vergangener_schon(bestand):
    from icarus_memory import personen
    episodes, _, kg = bestand
    gleiche_ab(kg, [termin('v', tage=-10, attendees=['Sabine Becker <s.becker@klinikum.example>']),
                    termin('z', 'Zukunft', tage=20, attendees=['Sabine Becker <s.becker@klinikum.example>']),
                    termin('z2', 'Nur Zukunft', tage=21, attendees=['Paul Neu <p.neu@x.example>'])])
    # Menschen sind über ihre Adresse gekennzeichnet (identitaet.py), nicht über den Namenstext.
    menschen = {p.id: p for p in personen.alle(episodes=episodes, jetzt=JETZT)}
    assert menschen['a:s.becker@klinikum.example'].episoden_anzahl == 1
    assert menschen['a:s.becker@klinikum.example'].letzter_kontakt < JETZT
    assert 'a:p.neu@x.example' not in menschen


# -- Quellenformate ----------------------------------------------------------


def test_ical_liefert_notiz_und_teilnehmernamen():
    ical = ('BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:u1\r\nDTSTART:20260501T090000Z\r\nDTEND:20260501T100000Z\r\n'
            'SUMMARY:Jour fixe\r\nDESCRIPTION:Punkt 1\\nPunkt 2\\, wichtig\r\n'
            'ATTENDEE;CN="Anna Keller";RSVP=TRUE:mailto:anna@x.example\r\n'
            'ATTENDEE;RSVP=TRUE:mailto:bob@x.example\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n')
    (event,) = parse_events(ical)
    assert event.notes == 'Punkt 1\nPunkt 2, wichtig'
    assert event.attendees == ['Anna Keller <anna@x.example>', 'bob@x.example']
    assert 'notes' not in event.to_dict()  # die Live-Anzeige bekommt keine Notizen


# -- Mac-Route: Freigabe, Abwahl, Trennen -------------------------------------


@pytest.fixture
def mac(tmp_path, bestand):
    episodes, claims, kg = bestand
    kalender = MacCalendar(tmp_path / 'mac.sqlite3')
    app = FastAPI()
    install_routes(app, [], kalender, lambda: None, kg)
    client = TestClient(app)
    info = [{'id': 'privat', 'name': 'Privat'}, {'id': 'arbeit', 'name': 'Arbeit'}]
    stand = kalender.enable()
    kalender.update(WorkerUpdate(generation=stand['generation'], status='granted', calendars=info))
    stand = kalender.select(['privat', 'arbeit'])

    def abschnitt(*ereignisse, generation=None, **kw):
        return client.post('/api/v1/mac-calendar/memory', json={
            'generation': generation if generation is not None else stand['generation'],
            'range_from': VON.isoformat(), 'range_to': BIS.isoformat(),
            'events': [dict(e, start=e['start'].isoformat(), end=e['end'].isoformat()) for e in ereignisse], **kw})
    return SimpleNamespaceMac(client, kalender, kg, episodes, stand, abschnitt)


class SimpleNamespaceMac:
    def __init__(self, client, kalender, kg, episodes, stand, abschnitt):
        self.client, self.kalender, self.kg, self.episodes, self.stand, self.abschnitt = (
            client, kalender, kg, episodes, stand, abschnitt)


def mac_termin(uid, kalender, tage=-400, **kw):
    beginn = JETZT + timedelta(days=tage)
    return dict(uid=uid, summary=kw.pop('summary', 'Termin ' + uid), start=beginn, end=beginn + timedelta(hours=1),
                source_id=kalender, source_label=kalender, notes=kw.pop('notes', ''), **kw)


def test_mac_abschnitt_legt_termine_je_kalender_ab(mac):
    antwort = mac.abschnitt(mac_termin('e1', 'privat'), mac_termin('e2', 'arbeit', notes='Notiz der Arbeit'))
    assert antwort.status_code == 200 and antwort.json()['neu'] == 2
    assert mac.kg.anzahl(quelle_fuer_mac('privat')) == 1 and mac.kg.anzahl(MAC_QUELLE) == 2
    # Erneut gesendet: nichts Neues.
    assert mac.abschnitt(mac_termin('e1', 'privat'), mac_termin('e2', 'arbeit', notes='Notiz der Arbeit')).json()['unveraendert'] == 2


def test_mac_verschobener_termin_behaelt_seine_uid_und_wird_neue_fassung(mac):
    mac.abschnitt(mac_termin('e1', 'privat', tage=-400))
    antwort = mac.abschnitt(mac_termin('e1', 'privat', tage=-395)).json()
    assert (antwort['neu'], antwort['geaendert'], antwort['entzogen']) == (0, 1, 0)
    assert mac.kg.anzahl(MAC_QUELLE) == 1


def test_mac_abwaehlen_und_trennen_entziehen_die_termine(mac):
    mac.abschnitt(mac_termin('e1', 'privat'), mac_termin('e2', 'arbeit'))
    antwort = mac.client.put('/api/v1/mac-calendar/selection', json={'ids': ['arbeit']})
    assert antwort.status_code == 200
    assert mac.kg.anzahl(quelle_fuer_mac('privat')) == 0 and mac.kg.anzahl(quelle_fuer_mac('arbeit')) == 1
    assert mac.client.delete('/api/v1/mac-calendar').status_code == 200
    assert mac.kg.anzahl(MAC_QUELLE) == 0
    # Beide Episoden sind noch da, nur ausgeschlossen.
    assert len([e for e in mac.episodes.all_episodes(limit=10) if e.state is EpisodeState.IGNORED]) == 2


def test_mac_route_lehnt_veraltete_generation_und_fremde_kalender_ab(mac):
    assert mac.abschnitt(mac_termin('e1', 'privat'), generation=mac.stand['generation'] - 1).status_code == 409
    assert mac.abschnitt(mac_termin('e1', 'unbekannt')).status_code == 400
    assert mac.abschnitt(dict(mac_termin('e1', 'privat'), end=JETZT - timedelta(days=500))).status_code == 400
    assert mac.kg.anzahl(MAC_QUELLE) == 0


def test_mac_route_schreibt_nichts_nach_dem_trennen(mac):
    mac.kalender.disconnect()
    assert mac.abschnitt(mac_termin('e1', 'privat')).status_code == 409
    assert mac.kg.anzahl(MAC_QUELLE) == 0


def test_mac_worker_erfaehrt_das_gedaechtnisfenster_vom_sidecar(mac):
    fensterangabe = mac.client.get('/api/v1/mac-calendar').json()['memory_window']
    assert fensterangabe == {'days_back': VERGANGENHEIT_TAGE, 'days_ahead': ZUKUNFT_TAGE}


# -- Server: Trennen einer Kalenderquelle, Zeitplan, Auskunft ------------------


def server_client(tmp_path, monkeypatch):
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.audit import AuditLog
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'), audit=AuditLog(tmp_path / 'audit.sqlite3'),
                     episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'))
    return app, TestClient(app)


def test_trennen_einer_kalenderquelle_entzieht_ihre_termine(tmp_path, monkeypatch):
    from icarus_memory.connectors import collections
    letzter = datetime.now(timezone.utc)
    monkeypatch.setattr(collections.ICalendarSubscription, 'events', lambda self, days=7, at=None: [
        Event(uid='u1', summary='Bilanzgespräch', start=letzter - timedelta(days=400), end=letzter - timedelta(days=400, hours=-1),
              notes='Zahlen 2024')])
    app, client = server_client(tmp_path, monkeypatch)
    quelle = client.post('/api/v1/integrations/calendar', json={
        'label': 'Kanzlei', 'kind': 'ical', 'url': 'https://kalender.example.test/kanzlei.ics'}).json()['calendar_sources'][0]['id']
    antwort = client.post('/api/v1/calendar-memory/sync').json()
    assert antwort['quellen'][quelle]['neu'] == 1
    auskunft = client.get('/api/v1/calendar-memory').json()
    assert auskunft['quellen'] == [{'id': quelle, 'label': 'Kanzlei', 'termine': 1}]
    assert auskunft['fenster'] == {'tage_zurueck': VERGANGENHEIT_TAGE, 'tage_voraus': ZUKUNFT_TAGE}
    episoden = [e for e in app.state.episodes.all_episodes(limit=10) if e.kind is EpisodeKind.EVENT]
    assert [e.title for e in episoden] == ['Bilanzgespräch'] and 'Zahlen 2024' in episoden[0].body
    assert client.delete(f'/api/v1/integrations/calendar/{quelle}').status_code == 200
    assert episoden[0].id and app.state.episodes.get(episoden[0].id).state is EpisodeState.IGNORED
    assert client.get('/api/v1/calendar-memory').json()['quellen'] == []
