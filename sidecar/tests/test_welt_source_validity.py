"""Öffentliche Briefingmeldung bleibt an eine gültige Quellenfassung gebunden."""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import threading

import pytest

from icarus_memory.config import Settings
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.claims import ClaimStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.world_monitor import WorldMonitor
from icarus_memory.welt_meldungen import WeltDienst
from tests.test_welt_meldungen import Bezuege

NOW = datetime(2026, 10, 9, 8, tzinfo=timezone.utc)
TEXT = 'Das Klinikum Falken erhält einen neuen Küchenleiter im Herbst.'


@pytest.fixture
def public_world(tmp_path, monkeypatch):
    monkeypatch.setattr('icarus_memory.world_monitor._validate_url', lambda url: url)
    with ExitStack() as stack:
        episodes = EpisodeStore(tmp_path/'episodes.sqlite3');stack.callback(episodes.close)
        claims = ClaimStore(tmp_path/'claims.sqlite3');stack.callback(claims.close)
        settings = Settings()
        fetched = {'text':TEXT,'captured_at':NOW.isoformat(),'url':'https://example.org/final'}
        monitor = WorldMonitor(settings,episodes,claims,lambda _:None,threading.RLock(),fetch=lambda _:dict(fetched))
        source = monitor.add('https://example.org/start','Fachportal',[])
        source = monitor.refresh(source['id'])
        own,_ = episodes.record(EpisodeKind.MESSAGE,'Eigene Korrespondenz','Wir arbeiten mit Klinikum Falken.',Provenance(SourceType.EMAIL),occurred_at=NOW)
        links = Bezuege({'organisation:falken':('Klinikum Falken',[own.id])})
        settings.welt = {'aktiv':True,'weltquellen':[source['id']]}
        def save(value):settings.welt=value
        def no_fetch(*args):raise AssertionError('Briefing darf die öffentliche Quelle nicht neu abrufen')
        dienst = WeltDienst(lesen=lambda:settings.welt,speichern=save,bezuege=lambda:links,episodes=lambda:episodes,
                           weltquellen=lambda:settings.world_sources,abrufen=no_fetch,jetzt=lambda:NOW)
        yield dienst, monitor, episodes, source, fetched


@pytest.mark.parametrize('withdraw', ['disable','ignore'])
def test_withdrawn_source_is_not_read_for_first_briefing(public_world, withdraw):
    dienst,monitor,episodes,source,_ = public_world
    if withdraw=='disable':monitor.disable(source['id'])
    else:episodes.ignore(source['episode_id'])
    assert dienst.aktualisieren() is None
    assert dienst.heute() is None


@pytest.mark.parametrize('withdraw', ['disable','ignore','new_version'])
def test_cached_daily_title_disappears_after_source_withdrawal(public_world, withdraw):
    dienst,monitor,episodes,source,fetched = public_world
    original = episodes.get(source['episode_id'])
    message = dienst.aktualisieren();assert message and message['titel']==TEXT
    if withdraw=='disable':monitor.disable(source['id'])
    elif withdraw=='ignore':episodes.ignore(source['episode_id'])
    else:
        fetched['text']='Das Klinikum Falken hat den Küchenleiterwechsel abgesagt.'
        monitor.refresh(source['id'])
    assert dienst.heute() is None
    assert dienst.aktualisieren() is None
    assert episodes.get(original.id).body==original.body


@pytest.mark.parametrize('stamp', [None,'not-a-date','2026-10-09T08:00:00',
    (NOW-timedelta(hours=25)).isoformat(),(NOW+timedelta(minutes=1)).isoformat()])
def test_unverified_or_stale_public_capture_is_not_daily_news(public_world, stamp):
    dienst,monitor,_,source,_ = public_world
    monitor.settings.world_sources[0]['last_success']=stamp
    assert dienst.aktualisieren() is None


def test_repeated_success_of_unchanged_source_keeps_daily_message(public_world):
    dienst,monitor,episodes,source,fetched = public_world
    message = dienst.aktualisieren();assert message
    assert message['link']=='https://example.org/final'
    assert message['quelle_fassung']['episode_id']==source['episode_id']
    fetched['captured_at']=(NOW-timedelta(minutes=1)).isoformat()
    assert monitor.refresh(source['id'])['episode_id']==source['episode_id']
    assert dienst.heute()==message
    assert episodes.get(source['episode_id']).body==TEXT


def test_version_without_cached_binding_is_not_represented_as_current(public_world):
    dienst,_,_,_,_ = public_world
    message = dienst.aktualisieren();assert message
    dienst._lesen()['heute']['meldung'].pop('quelle_fassung',None)
    assert dienst.heute() is None


def test_cached_relevance_reason_disappears_after_own_evidence_withdrawal(public_world):
    dienst,_,episodes,source,_ = public_world
    message=dienst.aktualisieren();assert message
    own=next(e for e in episodes.all_episodes() if e.provenance.source_type is SourceType.EMAIL)
    episodes.ignore(own.id)
    assert dienst.heute() is None
    assert dienst.aktualisieren() is None
    assert episodes.get(source['episode_id']).body==TEXT


def test_source_withdrawn_between_candidate_selection_and_commit_is_not_shown(public_world):
    dienst,monitor,_,source,_ = public_world
    def before_selection():
        monitor.disable(source['id'])
        return None
    dienst._anbieter=before_selection
    assert dienst.aktualisieren() is None
    assert dienst.heute() is None
    assert dienst.welt().heute.get('meldung') is None


@pytest.mark.parametrize('changed', ['stale','error'])
def test_cached_source_rechecks_refresh_status_on_every_read(public_world, changed):
    dienst,monitor,_,_,_ = public_world
    assert dienst.aktualisieren()
    source=monitor.settings.world_sources[0]
    if changed=='stale':source['last_success']=(NOW-timedelta(hours=25)).isoformat()
    else:source['error']='refresh_failed'
    assert dienst.heute() is None
    assert dienst.aktualisieren() is None
