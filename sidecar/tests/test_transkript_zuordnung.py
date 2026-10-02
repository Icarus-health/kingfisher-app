"""Zuordnung von Mitschrift zu Termin und von Sprecher zu Person (F3)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.calendar_memory import KalenderGedaechtnis, fenster
from icarus_memory.claims import ClaimStore
from icarus_memory.connectors.calendar import Event
from icarus_memory.episodes import EpisodeState, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.source_versions import track_source
from icarus_memory.transkript_eingang import aufnehmen, lesen
from icarus_memory.transkript_zuordnung import (
    Zuordner, Zuordnungen, entscheiden, sprecher_zu_teilnehmern, termin_zu, termine_zwischen)

JETZT = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)
# Montag, 28. September 2026, 14:30 Uhr in Berlin (UTC+2)
TAG = datetime(2026, 9, 28, 12, 30, tzinfo=timezone.utc)
ANNA = 'Anna Berg <anna.berg@winter.example>'
BERT = 'Bert Kraus <bert@winter.example>'
ICH = 'Lena Probe <ich@meins.example>'
MEETING = 'Anna Berg: Guten Tag.\nBert Kraus: Hallo.\nAnna Berg: Das Budget steht.\nBert Kraus: Gut.\n'


def event(uid, titel, start=TAG, dauer=1, teilnehmer=(ANNA, BERT, ICH)) -> Event:
    return Event(uid=uid, summary=titel, start=start, end=start + timedelta(hours=dauer), attendees=list(teilnehmer))


@pytest.fixture
def welt(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    ablage = Zuordnungen(tmp_path / 'gespraeche.sqlite3')
    kalender = KalenderGedaechtnis(episodes, claims)
    von, bis = fenster(JETZT)

    def termine(*eintraege):
        kalender.abgleichen('k', 'Arbeit', list(eintraege), von, bis, at=JETZT)

    zuordner = Zuordner(episodes, ablage, eigene=lambda: ['ich@meins.example'])

    def mitschrift(name, text=MEETING, geaendert=None):
        t = lesen(name, text.encode(), geaendert)
        episode, _ = aufnehmen(episodes, t, Provenance(source_type=SourceType.DOCUMENT, source_ref=f'transkript:{name}'),
                               f'transkript:{name}')
        track_source(episodes, claims, f'transkript:{name}', episode)
        return episode, zuordner.vormerken(episode, t.hinweise())

    yield type('Welt', (), {'episodes': episodes, 'ablage': ablage, 'termine': staticmethod(termine),
                            'zuordner': zuordner, 'mitschrift': staticmethod(mitschrift)})
    episodes.close()
    claims.close()
    ablage.close()


def test_eindeutige_uhrzeit_ordnet_zu_und_nennt_den_grund(welt):
    welt.termine(event('a', 'Jour fixe Winter'), event('b', 'Zahnarzt', start=TAG + timedelta(days=1), teilnehmer=()))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    assert zeile['status'] == 'zugeordnet' and zeile['von'] == 'auto'
    assert zeile['termin'].startswith('a|')
    assert any('Uhrzeit' in grund for grund in zeile['gruende'])
    assert welt.zuordner.fuer_termin(zeile['termin'])[0]['id'] == episode.id


def test_mehrdeutig_ist_ein_vorschlag_und_wird_nicht_zugeordnet(welt):
    # Zwei Termine zur selben Zeit; der Titel der Mitschrift passt zu keinem.
    welt.termine(event('a', 'Fokuszeit', teilnehmer=()), event('b', 'Abstimmung Lieferant', teilnehmer=()))
    _, zeile = welt.mitschrift('2026-09-28 14.30 Notizen.txt', 'Hallo zusammen\nWeiter geht es\n')
    assert zeile['status'] == 'vorschlag'
    assert zeile['termin'] == ''
    assert {k['uid'] for k in zeile['kandidaten']} == {'a', 'b'}
    assert welt.zuordner.fuer_termin(zeile['kandidaten'][0]['key']) == []


def test_der_titel_entscheidet_zwischen_zwei_terminen_zur_selben_zeit(welt):
    welt.termine(event('a', 'Fokuszeit', teilnehmer=()), event('b', 'Jour fixe Winter', teilnehmer=()))
    _, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    assert zeile['status'] == 'zugeordnet' and zeile['termin'].startswith('b|')


def test_ohne_passenden_termin_steht_die_mitschrift_allein(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    _, zeile = welt.mitschrift('2026-10-05 10.00 Etwas anderes.txt', 'Hallo\nWeiter\n')
    assert zeile['status'] == 'allein' and zeile['kandidaten'] == []


def test_widerspricht_die_datei_dem_tag_entfaellt_der_termin_trotz_gleichem_titel(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    _, zeile = welt.mitschrift('2026-10-05 14.30 Jour fixe Winter.txt')
    assert zeile['status'] == 'allein'


def test_dateizeitpunkt_allein_ordnet_nie_zu(welt):
    welt.termine(event('a', 'Fokuszeit', teilnehmer=()))
    kurz_danach = TAG + timedelta(hours=1, minutes=20)
    _, zeile = welt.mitschrift('Aufnahme.txt', 'Hallo\nWeiter\n', geaendert=kurz_danach)
    assert zeile['status'] == 'allein'      # ein Punkt reicht nicht einmal für einen Vorschlag


def test_dateizeitpunkt_mit_sprechern_reicht_fuer_die_zuordnung(welt):
    welt.termine(event('a', 'Fokuszeit'))
    _, zeile = welt.mitschrift('Aufnahme.txt', geaendert=TAG + timedelta(hours=1, minutes=20))
    assert zeile['status'] == 'zugeordnet'     # 1 (Datei) + 2 (zwei Sprecher unter den Teilnehmern)


def test_entscheiden_ist_rein_und_speichert_nichts(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    t = lesen('2026-09-28 14.30 Jour fixe Winter.txt', MEETING.encode())
    termine = termine_zwischen(welt.episodes, TAG - timedelta(days=1), TAG + timedelta(days=1))
    assert entscheiden(t.hinweise(), termine).status == 'zugeordnet'
    assert entscheiden(t.hinweise(), termine, abgelehnt=[termine[0].key]).status == 'allein'


# -- Sprecher -----------------------------------------------------------------


def test_sprecher_nur_bei_eindeutigem_treffer():
    teilnehmer = [ANNA, 'Anna Kurz <anna.kurz@x.example>', BERT]
    ergebnis = sprecher_zu_teilnehmern(['Anna Berg', 'Anna', 'Bert', 'Carla Neu'], teilnehmer)
    assert ergebnis['Anna Berg'] == ANNA          # voller Name: eindeutig
    assert ergebnis['Anna'] is None               # zwei Annas: keine von beiden
    assert ergebnis['Bert'] == BERT               # Vorname, nur ein Bert
    assert ergebnis['Carla Neu'] is None          # kein Teilnehmer


def test_sprecher_aus_der_adresse_ohne_anzeigenamen():
    assert sprecher_zu_teilnehmern(['Anna Berg'], ['anna.berg@winter.example'])['Anna Berg'] == 'anna.berg@winter.example'


def test_zugeordnete_mitschrift_traegt_die_adresse_als_anker(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    assert welt.episodes.get(episode.id).contacts == []      # automatisch: nur ein Vorschlag, nichts wird geschrieben
    welt.zuordner.bestaetigen(episode.id, zeile['termin'])   # erst die Bestätigung trägt die Sprecher ein
    aktuell = welt.episodes.get(episode.id)
    adressen = {c['adresse'] for c in aktuell.contacts}
    assert adressen == {'anna.berg@winter.example', 'bert@winter.example'}
    assert all(not c['ich'] for c in aktuell.contacts)


def test_bei_einem_vorschlag_werden_keine_sprecher_zu_personen(welt):
    welt.termine(event('a', 'Fokuszeit'), event('b', 'Abstimmung'))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Notizen.txt')
    assert zeile['status'] == 'vorschlag'
    assert welt.episodes.get(episode.id).contacts == []


def test_zwei_gleiche_vornamen_bleiben_namen(welt):
    teilnehmer = ('Anna Berg <anna.berg@winter.example>', 'Anna Kurz <anna.kurz@x.example>', ICH)
    welt.termine(event('a', 'Jour fixe Winter', teilnehmer=teilnehmer))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt', 'Anna: Hallo\nCarl: Moin\nAnna: Weiter\nCarl: Ja\n')
    assert zeile['status'] == 'zugeordnet'
    welt.zuordner.bestaetigen(episode.id, zeile['termin'])
    kontakte = {c['name']: c['adresse'] for c in welt.episodes.get(episode.id).contacts}
    assert kontakte == {'Anna': '', 'Carl': ''}


# -- Entscheidungen des Nutzers ---------------------------------------------------


def test_klick_auf_einen_vorschlag_ordnet_zu_und_bleibt(welt):
    welt.termine(event('a', 'Fokuszeit', teilnehmer=()), event('b', 'Abstimmung Lieferant', teilnehmer=()))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Notizen.txt', 'Hallo\nWeiter\n')
    gewaehlt = zeile['kandidaten'][0]['key']
    neu = welt.zuordner.bestaetigen(episode.id, gewaehlt)
    assert neu['status'] == 'zugeordnet' and neu['von'] == 'nutzer' and neu['termin'] == gewaehlt
    # Neue Termine oder ein Abgleich ändern eine Entscheidung des Nutzers nicht.
    welt.termine(event('a', 'Fokuszeit', teilnehmer=()), event('b', 'Abstimmung Lieferant', teilnehmer=()),
                 event('c', 'Notizen', teilnehmer=()))
    assert welt.zuordner.abgleichen(episode.id)['termin'] == gewaehlt
    assert welt.zuordner.nachziehen() == 0


def test_loesen_nimmt_zurueck_und_schlaegt_denselben_termin_nicht_wieder_vor(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    gewesen = zeile['termin']
    geloest = welt.zuordner.loesen(episode.id)
    assert geloest['status'] == 'allein' and geloest['von'] == 'nutzer'
    assert welt.zuordner.fuer_termin(gewesen) == []
    assert welt.zuordner.abgleichen(episode.id)['status'] == 'allein'
    assert gewesen in welt.ablage.zeile(episode.id)['abgelehnt']


def test_von_hand_zu_einem_beliebigen_termin(welt):
    welt.termine(event('a', 'Jour fixe Winter'), event('z', 'Ganz anderer Tag', start=TAG + timedelta(days=3)))
    episode, _ = welt.mitschrift('Notizen.txt', 'Hallo\nWeiter\n')
    key = termine_zwischen(welt.episodes, TAG + timedelta(days=2), TAG + timedelta(days=4))[0].key
    assert termin_zu(welt.episodes, key) is not None
    assert welt.zuordner.bestaetigen(episode.id, key)['termin'] == key


def test_unbekannter_termin_wird_abgelehnt(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    episode, _ = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    with pytest.raises(Exception):
        welt.zuordner.bestaetigen(episode.id, 'gibt-es-nicht|2026-01-01T00:00:00+00:00')


# -- Entzug und Nachziehen -----------------------------------------------------------


def test_entzogene_mitschrift_zaehlt_nirgends_mehr(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    welt.episodes.ignore(episode.id, grund='ordner')
    assert welt.zuordner.fuer_termin(zeile['termin']) == []
    eintraege, zaehler = welt.zuordner.eintraege()
    assert eintraege == [] and zaehler['aufgenommen'] == 0
    assert welt.episodes.get(episode.id).state is EpisodeState.IGNORED


def test_termin_erscheint_erst_nach_der_mitschrift_nachziehen(welt):
    episode, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    assert zeile['status'] == 'allein'
    welt.termine(event('a', 'Jour fixe Winter'))
    assert welt.zuordner.nachziehen() == 1
    assert welt.ablage.zeile(episode.id)['status'] == 'zugeordnet'
    assert welt.zuordner.nachziehen() == 0     # nichts mehr zu tun


def test_zaehler_ueber_alle_mitschriften(welt):
    welt.termine(event('a', 'Jour fixe Winter'), event('b', 'Fokuszeit', start=TAG + timedelta(days=2), teilnehmer=()),
                 event('c', 'Abstimmung', start=TAG + timedelta(days=2), teilnehmer=()))
    welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    welt.mitschrift('2026-09-30 14.30 Notizen.txt', 'Hallo\nWeiter\n')
    welt.mitschrift('2026-11-30 14.30 Nichts.txt', 'Hallo\nWeiter\n')
    eintraege, zaehler = welt.zuordner.eintraege()
    assert zaehler == {'aufgenommen': 3, 'zugeordnet': 1, 'vorschlag': 1, 'offen': 2}
    assert len(eintraege) == 3


def test_datei_mit_anderem_tag_schliesst_den_termin_aus_auch_bei_gleichem_titel_und_sprechern(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    termine = termine_zwischen(welt.episodes, TAG - timedelta(days=1), TAG + timedelta(days=1))
    gleicher_tag = lesen('2026-09-28 09.00 Jour fixe Winter.txt', MEETING.encode())        # Uhrzeit passt nicht, Tag schon
    anderer_tag = lesen('2026-10-05 14.30 Jour fixe Winter.txt', MEETING.encode())
    nur_tag = lesen('Protokoll 2026-10-05 Jour fixe Winter.txt', MEETING.encode())
    assert entscheiden(gleicher_tag.hinweise(), termine).status == 'zugeordnet'            # Titel (3) + Sprecher (2) + Tag (1)
    assert entscheiden(anderer_tag.hinweise(), termine).status == 'allein'
    assert entscheiden(nur_tag.hinweise(), termine).status == 'allein'


def test_erneutes_einlesen_nach_der_zuordnung_legt_nichts_doppelt_an(welt):
    welt.termine(event('a', 'Jour fixe Winter'))
    erste, zeile = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    welt.zuordner.bestaetigen(erste.id, zeile['termin'])
    assert zeile['status'] == 'zugeordnet' and welt.episodes.get(erste.id).contacts    # Metadaten sind gewachsen
    zweite, _ = welt.mitschrift('2026-09-28 14.30 Jour fixe Winter.txt')
    assert zweite.id == erste.id
    assert len(welt.episodes.tagged('transkript')) == 1
