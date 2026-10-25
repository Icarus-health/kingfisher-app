"""V1 (25.10.2026): „Neu eingegangen“ auf Heute nennt nur, was wirklich neu ist, nicht den Altbestand aus dem ersten
Einlesen. Regel in `neu_eingegangen.py`; nur synthetische Daten."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.morning import compose
from icarus_memory.neu_eingegangen import (FENSTER_TAGE, anzahl_neu_von_aussen, aus_bestandsaufnahme, ist_neu,
                                           neue_quellen)
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import _api

BERLIN = ZoneInfo('Europe/Berlin')
JETZT = datetime(2026, 9, 29, 7, 30, tzinfo=BERLIN)


# -- Die Regel ---------------------------------------------------------------------------------------------------

def test_mit_quelldatum_zaehlt_das_quelldatum_heute_gestern_vorgestern():
    assert FENSTER_TAGE == 2
    for tage in range(FENSTER_TAGE + 1):
        assert ist_neu(JETZT - timedelta(days=tage), JETZT, jetzt=JETZT), tage
    assert not ist_neu(datetime(2026, 9, 26, 12, tzinfo=BERLIN), JETZT, jetzt=JETZT), 'drei Tage alt ist nicht neu'
    assert not ist_neu(datetime(2026, 6, 21, 9, tzinfo=BERLIN), JETZT, jetzt=JETZT), 'heute erfasst macht Juni nicht neu'
    assert not ist_neu('2025-04-15T10:00:00+02:00', JETZT.isoformat(), jetzt=JETZT)
    # Auch ein Quelldatum in den Fenstertagen bleibt neu, wenn die Quelle aus der Bestandsaufnahme kam.
    assert ist_neu(datetime(2026, 9, 28, 9, 10, tzinfo=BERLIN), JETZT, jetzt=JETZT, aus_bestand=True)


def test_kalendertag_in_der_zone_des_briefings_nicht_utc():
    # 26.9. 22:30 UTC ist in Berlin schon der 27.9.: vorgestern, also neu.
    assert ist_neu(datetime(2026, 9, 26, 22, 30, tzinfo=timezone.utc), None, jetzt=JETZT)
    assert not ist_neu(datetime(2026, 9, 26, 21, 30, tzinfo=timezone.utc), None, jetzt=JETZT)


def test_spaeter_datiert_als_heute_ist_nicht_eingegangen():
    assert not ist_neu(datetime(2026, 9, 30, 10, tzinfo=BERLIN), JETZT, jetzt=JETZT)
    assert ist_neu(datetime(2026, 9, 29, 23, 0, tzinfo=BERLIN), JETZT, jetzt=JETZT), 'derselbe Kalendertag zählt'


def test_ohne_quelldatum_zaehlt_die_erfassung_ausser_aus_der_bestandsaufnahme():
    assert ist_neu(None, JETZT - timedelta(hours=2), jetzt=JETZT)
    assert ist_neu('kein Datum', JETZT, jetzt=JETZT), 'ein unlesbares Quelldatum zählt wie keines'
    assert not ist_neu(None, JETZT - timedelta(days=4), jetzt=JETZT)
    assert not ist_neu(None, JETZT, jetzt=JETZT, aus_bestand=True)
    assert not ist_neu(None, None, jetzt=JETZT), 'ohne jede Zeit sagt nichts, dass es neu ist'


# -- Heute (compose) --------------------------------------------------------------------------------------------

def _bericht(titel, *, entstanden, erfasst=JETZT, art='email'):
    return {'episode_id': titel, 'title': titel, 'kinds': ['commitment'], 'source_type': art, 'source_ref': f'x:{titel}',
            'occurred_at': entstanden.isoformat() if entstanden else None, 'recorded_at': erfasst.isoformat()}


def _dashboard(**teile):
    return {'briefing': {'punkte': []}, 'tasks': {}, 'mail': {'items': []}, 'calendar': {'items': []},
            'episodes': {}, 'proposals': {}, **teile}


def test_heute_zeigt_altbestand_nicht_als_neu_eingegangen():
    ergebnis = compose(_dashboard(working_memory={'items': [
        _bericht('Re: Papas Geburtstag', entstanden=datetime(2026, 6, 21, 9, tzinfo=BERLIN)),
        _bericht('Angebot Speiseplanung', entstanden=datetime(2025, 4, 15, 9, tzinfo=BERLIN)),
        _bericht('Rückfrage zum Fachtag', entstanden=datetime(2026, 9, 28, 9, 10, tzinfo=BERLIN)),
    ], 'truncated': False}), now=JETZT, target=date(2026, 9, 29))
    assert [z['title'] for z in ergebnis['happening_now']] == ['Rückfrage zum Fachtag']
    assert ergebnis['happening_now'][0]['occurred_at'] != ergebnis['happening_now'][0]['recorded_at'], \
        'Quelldatum und Erfassung bleiben unterscheidbar'
    assert ergebnis['working_memory_more'] is False, 'Altbestand zählt auch nicht als „Mehr“'


def test_heute_ohne_neues_laesst_den_abschnitt_leer():
    ergebnis = compose(_dashboard(working_memory={'items': [
        _bericht('Re: Fahrt zum Augenarzt', entstanden=datetime(2026, 9, 3, 9, tzinfo=BERLIN))], 'truncated': False}),
        now=JETZT, target=date(2026, 9, 29))
    assert ergebnis['happening_now'] == []


def test_ungelesene_alte_mail_im_posteingang_ist_nicht_neu():
    mail = lambda uid, datum: {'uid': uid, 'subject': uid, 'from': 'Anna', 'unread': True, 'date': datum}  # noqa: E731
    ergebnis = compose(_dashboard(mail={'items': [mail('Juni', '2026-06-21T09:00:00+02:00'),
                                                  mail('Gestern', '2026-09-28T16:00:00+02:00')]}),
                       now=JETZT, target=date(2026, 9, 29))
    assert [z['title'] for z in ergebnis['happening_now']] == ['Gestern']


def test_neue_zuerst_nach_quelldatum():
    ergebnis = compose(_dashboard(working_memory={'items': [
        _bericht('Vorgestern', entstanden=datetime(2026, 9, 27, 9, tzinfo=BERLIN)),
        _bericht('Heute früh', entstanden=datetime(2026, 9, 29, 6, tzinfo=BERLIN)),
        _bericht('Gestern', entstanden=datetime(2026, 9, 28, 9, tzinfo=BERLIN)),
    ], 'truncated': False}), now=JETZT, target=date(2026, 9, 29))
    assert [z['title'] for z in ergebnis['happening_now']] == ['Heute früh', 'Gestern', 'Vorgestern']


# -- Im Sidecar: Auswahl vor der Begrenzung, Bestandsaufnahme der Post -----------------------------------------------

def _quelle(app, titel, *, entstanden, ref, art=SourceType.EMAIL, index=True):
    text = f'{titel}: Nora liefert den Entwurf nur nach Freigabe.'
    episode, _ = app.state.episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(art, source_ref=ref),
                                           occurred_at=entstanden)
    if index:
        assert WorkingMemoryStore(app.state.episodes).commit(app.state.episodes.support_snapshot(episode.id),
                                                             [{'start': 0, 'end': len(text), 'kind': 'conditional'}],
                                                             model='synthetic')
    return episode


def _spur(app, episode, spur, uid):
    with app.state.episodes.transaction():
        app.state.episodes._conn.execute(
            "INSERT INTO mail_intake_items(account,folder,generation,uid,lane,status,episode_id) "
            "VALUES('probe','INBOX','1',?,?,'captured',?)", (uid, spur, episode.id))


def test_sidecar_waehlt_nur_neues_und_erkennt_die_bestandsaufnahme(core, tmp_path, monkeypatch):  # noqa: F811
    app, client, _provider = _api(core, tmp_path, monkeypatch)
    try:
        jetzt = datetime.now().astimezone()
        alt = _quelle(app, 'Angebot vom Vorjahr', entstanden=jetzt - timedelta(days=400), ref='imap:probe:INBOX:1')
        neu = _quelle(app, 'Rückfrage von heute', entstanden=jetzt - timedelta(minutes=30), ref='imap:probe:INBOX:2')
        ohne_bestand = _quelle(app, 'Undatiert aus dem Bestand', entstanden=None, ref='imap:probe:INBOX:3')
        ohne_live = _quelle(app, 'Undatiert, eben gekommen', entstanden=None, ref='imap:probe:INBOX:4')
        eigene = _quelle(app, 'Eigene Zeile', entstanden=jetzt, ref='conversation:c:message:m', art=SourceType.CHAT)
        for nummer, (episode, spur) in enumerate([(alt, 'history'), (neu, 'history'), (ohne_bestand, 'history'),
                                                   (ohne_live, 'live')], start=1):
            _spur(app, episode, spur, nummer)
        assert aus_bestandsaufnahme(app.state.episodes, [alt.id, ohne_bestand.id, ohne_live.id]) == {
            alt.id, ohne_bestand.id}
        gewaehlt = neue_quellen(app.state.episodes, jetzt=jetzt)
        assert set(gewaehlt) == {neu.id, ohne_live.id}, 'kein Altbestand, keine eigene Zeile'
        assert eigene.id not in gewaehlt
        assert anzahl_neu_von_aussen(app.state.episodes, jetzt=jetzt) == 2
        assert app.state.episodes.neue_von_aussen() == 4, 'gespeichert und gezählt bleibt alles, nur Heute wählt aus'

        heute = client.get('/api/v1/morning-briefing').json()
        titel = [z['title'] for z in heute['happening_now'] if z['source'] == 'working_memory']
        assert sorted(titel) == sorted(['Rückfrage von heute', 'Undatiert, eben gekommen'])
        assert all('Vorjahr' not in z['title'] and 'Bestand' not in z['title'] for z in heute['happening_now'])
    finally:
        client.close()
        _close_app(app)


def test_viel_altbestand_verdraengt_die_neue_post_nicht(core, tmp_path, monkeypatch):  # noqa: F811
    app, client, _provider = _api(core, tmp_path, monkeypatch)
    try:
        jetzt = datetime.now().astimezone()
        neu = _quelle(app, 'Die eine neue Mail', entstanden=jetzt - timedelta(hours=1), ref='imap:probe:INBOX:0')
        # Danach erfasst (also in der Erfassungsreihenfolge vorn): 70 alte Mails aus dem ersten Einlesen.
        for nummer in range(1, 71):
            _quelle(app, f'Alte Mail {nummer}', entstanden=jetzt - timedelta(days=30 + nummer),
                    ref=f'imap:probe:INBOX:{nummer}')
        heute = client.get('/api/v1/morning-briefing').json()
        assert [z['title'] for z in heute['happening_now'] if z['source'] == 'working_memory'] == ['Die eine neue Mail']
        assert heute['working_memory_more'] is False
        assert neue_quellen(app.state.episodes, jetzt=jetzt) == [neu.id]
    finally:
        client.close()
        _close_app(app)


# -- Braucht dich: die Aufgabe selbst für die Zeile der Aufgabenliste ---------------------------------------------

def test_aufgabenpunkt_bringt_die_aufgabe_und_den_projektnamen_mit():
    aufgabe = {'id': 't1', 'title': 'Flyer-Layout nachfassen', 'status': 'open', 'due': '2026-09-26T17:00:00+02:00',
               'overdue': True, 'project_id': 'p1', 'wartet_auf': None,
               'source_review': {'reason': 'Weitere Nachricht im selben Verlauf.', 'followup_episode_id': 'e9'}}
    ergebnis = compose(_dashboard(
        briefing={'punkte': [{'quelle': 'aufgabe', 'ref': 't1', 'text': 'Flyer-Layout ist überfällig.'},
                             {'quelle': 'aufgabe', 'ref': 'fehlt', 'text': 'Unbekannte Aufgabe'}]},
        tasks={'items': [aufgabe]}, projects={'items': [{'id': 'p1', 'name': 'Fachtag'}]}),
        now=JETZT, target=date(2026, 9, 29))
    erster, zweiter = ergebnis['needs_you']
    assert erster['task']['id'] == 't1' and erster['task']['due'] == aufgabe['due'] and erster['task']['overdue'] is True
    assert 'source_review' not in erster['task'], 'die Prüfung steht schon am Punkt (Grund, Verlauf ungeprüft)'
    assert erster['project_name'] == 'Fachtag'
    assert erster['action'] == 'Verlauf prüfen' and erster['episode_id'] == 'e9'
    assert 'task' not in zweiter, 'ohne bekannte Aufgabe nichts erfinden'
