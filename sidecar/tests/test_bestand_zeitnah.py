"""Befund A5 der Persona-Prüfung: Bitten von gestern und heute heißen nicht „Historisch“, nur weil das erste Einlesen sie holte.

Nachgestellt mit echter Uhr (Mails relativ zum Einlesen): Die Ärztin richtete Kingfisher am Abend ein; die Bitte um
ein Folgerezept von gestern stand als „Historisch · Aktualität prüfen“, Heute zählte „8 Vorschläge sind zeitlich
ungeklärt“ und sagte zugleich „Nichts wartet auf dich“. Die eingefrorene Uhr der Prüfung war daran nicht schuld (die
Uhr des Sidecars lief echt): Die Zeitprüfung stufte **jede** Mail der Bestandsaufnahme als `history` ein, auch eine
von vor einer Stunde. Jetzt gilt eine Mail aus dem ersten Einlesen, die höchstens drei Tage vor dem Einlesen ankam, als
zeitnah wie neue Post (Vorschlag, kein Auftrag); ältere bleiben zur Prüfung. Selbst angelegt wird aus dem ersten
Einlesen weiterhin nichts (`aufgaben_von_selbst`, Grund `bestand`).
"""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.mail_timeline import INVENTAR_ZEITNAH, timings
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalStore
from icarus_memory.task_detection import for_briefing

EINLESEN = datetime(2026, 10, 26, 18, 30, tzinfo=timezone.utc)


@pytest.fixture
def stores(tmp_path):
    episodes, proposals = EpisodeStore(tmp_path / 'e.sqlite3'), ProposalStore(tmp_path / 'p.sqlite3')
    yield episodes, proposals
    episodes.close()
    proposals.close()


def bestand(stores, stunden, *, uid=1, eingelesen=EINLESEN, lane='history'):
    """Eine Bitte, die die Bestandsaufnahme (`lane='history'`) oder neue Post (`live`) geholt hat."""
    episodes, proposals = stores
    e, _ = episodes.record(EpisodeKind.MESSAGE, f'Rezept {uid}', f'Könnten Sie mir bitte ein Folgerezept {uid} ausstellen?',
                           Provenance(SourceType.EMAIL), occurred_at=eingelesen - timedelta(hours=stunden), at=eingelesen,
                           source_key=f'm{uid}')
    with episodes.transaction():
        episodes._conn.execute('INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) '  # noqa: SLF001
                               "VALUES('praxis','INBOX','1',?,?,'captured',?)", (uid, lane, e.id))
    proposals.record_task_analysis(e.id, e.digest, [{'title': f'Folgerezept {uid} ausstellen', 'quote': e.body}],
                                   proposed_by='test/local/task-review-v1')
    return e


@pytest.mark.parametrize('stunden', [1, 20, 30, 71])
def test_bitte_von_gestern_aus_dem_ersten_einlesen_ist_zeitnah(stores, stunden):
    e = bestand(stores, stunden)
    [zeit] = timings(stores[0], [e], now=EINLESEN + timedelta(minutes=50)).values()
    assert zeit['temporal_status'] == 'recent', 'Vorher: history, also „Historisch · Aktualität prüfen“'


@pytest.mark.parametrize('stunden', [73, 24 * 5])
def test_aeltere_post_aus_dem_ersten_einlesen_bleibt_zur_pruefung(stores, stunden):
    e = bestand(stores, stunden)
    [zeit] = timings(stores[0], [e], now=EINLESEN + timedelta(minutes=50)).values()
    assert zeit['temporal_status'] == 'history'
    assert INVENTAR_ZEITNAH == timedelta(days=3)


def test_zeitnah_altert_wie_neue_post(stores):
    e = bestand(stores, 20)
    [zeit] = timings(stores[0], [e], now=EINLESEN + timedelta(days=7)).values()
    assert zeit['temporal_status'] == 'old'


def test_heute_zaehlt_frische_bitten_als_vorschlag_und_aeltere_zur_pruefung(stores):
    for uid, stunden in enumerate((3, 20, 26, 30), 1):
        bestand(stores, stunden, uid=uid)
    bestand(stores, 24 * 6, uid=9)
    ergebnis = for_briefing(*reversed(stores), now=EINLESEN + timedelta(minutes=50))
    assert ergebnis['pending'] == 4 and ergebnis['review_pending'] == 1
    assert {item['temporal_status'] for item in ergebnis['items']} == {'recent'}


def test_eine_spaetere_mail_im_verlauf_haelt_auch_die_frische_bitte_zur_pruefung(stores):
    from icarus_memory.mail_timeline import REPLY, SELF, _token
    episodes, _ = stores
    e = bestand(stores, 20)
    antwort, _ = episodes.record(EpisodeKind.MESSAGE, 'Re: Rezept', 'Ist erledigt.', Provenance(SourceType.EMAIL),
                                 occurred_at=EINLESEN - timedelta(hours=2), at=EINLESEN, source_key='antwort',
                                 tags=[REPLY + _token('praxis', '<rezept@example.test>')])
    with episodes.transaction():
        episodes._conn.execute('UPDATE episodes SET document=json_set(document, "$.tags", json(?)) WHERE id=?',  # noqa: SLF001
                               (f'["{SELF + _token("praxis", "<rezept@example.test>")}"]', e.id))
    [zeit] = timings(episodes, [episodes.get(e.id)], now=EINLESEN + timedelta(minutes=50)).values()
    assert zeit['temporal_status'] == 'followup' and zeit['followup_episode_id'] == antwort.id
