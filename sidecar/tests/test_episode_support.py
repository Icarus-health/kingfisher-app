"""Synthetic M1d acceptance, revocation and authorization contracts."""
from datetime import datetime, timezone
import pytest
from icarus_memory import SelfModelStore, MemoryBackend, SqliteBackend
from icarus_memory.model import Kind, Provenance, SourceType
from icarus_memory.episodes import EpisodeStore, EpisodeKind, EpisodeState, EpisodeError
from icarus_memory.proposals import ProposalStore, ProposalKind, Evidence, ProposalError
from icarus_memory.consolidation import Consolidator

AT = datetime(2026,9,14,tzinfo=timezone.utc)


def fixture(tmp_path, backend=None):
    store = SelfModelStore(backend or MemoryBackend(), 'synthetic')
    episodes = EpisodeStore(tmp_path/'episodes.sqlite')
    proposals = ProposalStore(tmp_path/'proposals.sqlite')
    sources = [episodes.record(EpisodeKind.DOCUMENT, f'Synthetic {n}', f'ORION Beleg {n}.',
                              Provenance(SourceType.DOCUMENT), at=AT)[0] for n in range(2)]
    proposal,_ = proposals.propose(ProposalKind.ASSERTION, 'ORION ist finanziert.', 'Synthetic evidence',
        assertion_kind=Kind.STATE, evidence=[Evidence(e.id,e.body,e.digest) for e in sources], at=AT)
    consolidator = Consolidator(store, episodes, proposals)
    return store, episodes, proposals, sources, proposal, consolidator


def test_future_acceptance_captures_every_original_and_local_commitment(tmp_path):
    store, episodes, proposals, sources, proposal, consolidator = fixture(tmp_path)
    assertion = consolidator.accept(proposal.id, at=AT)
    assert len(assertion.episode_support['episodes']) == 2
    assert proposals.support_authorization(proposal.id)['assertion_id'] == assertion.id
    assert proposals.accepted_self_model_support(assertion.id)[0].id == proposal.id


def test_withdrawal_generation_survives_reopen_and_stale_consolidation(tmp_path):
    store, episodes, proposals, sources, proposal, consolidator = fixture(tmp_path)
    assert episodes.support_snapshot(sources[0].id).generation == 0
    stale = episodes.get(sources[0].id)
    episodes.ignore(stale.id); episodes.ignore(stale.id)
    assert episodes.support_snapshot(stale.id).generation == 1
    with pytest.raises(EpisodeError): episodes.mark_consolidated(stale.id)
    assert episodes.get(stale.id).state is EpisodeState.IGNORED
    episodes.reopen(stale.id)
    assert episodes.support_snapshot(stale.id).generation == 2


def test_failure_after_record_rolls_back_existing_supersession(tmp_path, monkeypatch):
    store, episodes, proposals, sources, proposal, consolidator = fixture(tmp_path, SqliteBackend(tmp_path/'self.sqlite'))
    old = store.record('Old valid statement.',Kind.STATE,Provenance(SourceType.USER_STATED),at=AT)
    proposal.supersedes = [old.id]
    proposals._put(proposal)
    original = store.record
    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError('after assertion creation')
    monkeypatch.setattr(store,'record',fail)
    with pytest.raises(RuntimeError): consolidator.accept(proposal.id,at=AT)
    assert store.get(old.id).is_usable(AT)
    assert store.get(old.id).superseded_by is None
    assert len(store.alles()) == 1

from icarus_memory.self_model_support import EpisodeSupportResolver
from icarus_memory.support_review import SupportReview, SupportReviewConflict
from icarus_memory.model import Sensitivity, Status
from icarus_memory.self_model_basis import FrozenBuild, digest


def assessment(store, episodes, proposals, assertion, local=True, prospective=None):
    resolver = EpisodeSupportResolver(proposals, episodes)
    return FrozenBuild(store, at=AT, max_sensitivity=Sensitivity.SPECIAL_CATEGORY,
        support_build=resolver.build(at=AT, local=local, max_sensitivity=Sensitivity.SPECIAL_CATEGORY,
                                     prospective=prospective)).assess(assertion)


def legacy(tmp_path):
    store, episodes, proposals, sources, proposal, consolidator = fixture(tmp_path)
    assertion = store.record(proposal.statement,Kind.STATE,Provenance(SourceType.INFERENCE),at=AT)
    proposals.accept(proposal.id, produced=assertion.id, at=AT)
    return store, episodes, proposals, sources, proposal, assertion


def test_legacy_reassessment_preserves_factual_document_and_replay_fails(tmp_path):
    store, episodes, proposals, sources, proposal, assertion = legacy(tmp_path)
    assert assessment(store,episodes,proposals,assertion) is None
    review=SupportReview(store,proposals,episodes,clock=lambda:AT)
    assert review.list()['items'][0]['eligible']
    preview=review.preview(assertion.id)
    assert len(preview['evidence']) == 2
    before=assertion.to_dict()
    result=review.submit(assertion.id,preview['preview_token'],True)
    after=store.get(assertion.id).to_dict(); after.pop('episode_support')
    assert before == after
    assert result['item']['support_status']=='supported'
    assert assessment(store,episodes,proposals,store.get(assertion.id)) is not None
    assert assessment(store,episodes,proposals,store.get(assertion.id),local=False) is None
    with pytest.raises(SupportReviewConflict): review.submit(assertion.id,preview['preview_token'],True)


def test_second_source_withdrawal_and_reopen_require_new_explicit_review(tmp_path):
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    review=SupportReview(store,proposals,episodes,clock=lambda:AT)
    token=review.preview(assertion.id)['preview_token']
    episodes.ignore(sources[1].id)
    assert assessment(store,episodes,proposals,assertion) is None
    assert review.preview(assertion.id)['preview_token'] is None
    with pytest.raises(SupportReviewConflict): review.submit(assertion.id,token,True)
    episodes.reopen(sources[1].id)
    assert assessment(store,episodes,proposals,assertion) is None
    token=review.preview(assertion.id)['preview_token']
    review.submit(assertion.id,token,True)
    assert assessment(store,episodes,proposals,store.get(assertion.id)) is not None


def test_missing_ancestor_support_cannot_be_waived_by_root_preview(tmp_path):
    store, episodes, proposals, sources, proposal, assertion=legacy(tmp_path)
    child=store.record('ORION Entscheidung',Kind.DECISION,Provenance(SourceType.INFERENCE),derived_from=[assertion.id],at=AT)
    # Vollständige, aber zurückgezogene Basis darf eine historische Entscheidung qualifizieren.
    result=assessment(store,episodes,proposals,child)
    assert result is not None and result.basis['state']=='review'
    proposals._conn.execute('DELETE FROM proposals WHERE id=?',(proposal.id,)); proposals._conn.commit()
    assert assessment(store,episodes,proposals,child) is None


def test_audit_failure_reports_durable_authorization_honestly(tmp_path):
    store, episodes, proposals, sources, proposal, assertion=legacy(tmp_path)
    class BrokenAudit:
        def record(self,*args,**kwargs): raise OSError('synthetic audit failure')
    review=SupportReview(store,proposals,episodes,BrokenAudit(),clock=lambda:AT)
    result=review.submit(assertion.id,review.preview(assertion.id)['preview_token'],True)
    assert result['ok'] and result['audit_warning']
    assert assessment(store,episodes,proposals,store.get(assertion.id)) is not None


def test_stale_generic_writer_cannot_undo_support_and_redaction_clears_quotes(tmp_path):
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path,SqliteBackend(tmp_path/'self.sqlite'))
    assertion=consolidator.accept(proposal.id,at=AT)
    stale=store.get(assertion.id)
    second=SelfModelStore(SqliteBackend(tmp_path/'self.sqlite'),'synthetic')
    episodes.ignore(sources[0].id); episodes.reopen(sources[0].id)
    review=SupportReview(second,proposals,episodes,clock=lambda:AT)
    review.submit(assertion.id,review.preview(assertion.id)['preview_token'],True)
    stale.last_confirmed_at=AT
    from icarus_memory.backends import ImmutableContentError
    with pytest.raises(ImmutableContentError): store._backend.put(stale)
    current=second.get(assertion.id)
    store.redact(assertion.id,at=AT)
    assert store.get(assertion.id).episode_support is None
    with pytest.raises(ImmutableContentError): second._backend.put(current)


def test_two_connections_accept_once_with_reciprocal_supersession(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    store, episodes, proposals, sources, proposal, first=fixture(tmp_path,SqliteBackend(tmp_path/'self.sqlite'))
    old=store.record('Vorher',Kind.STATE,Provenance(SourceType.USER_STATED),at=AT)
    proposal.supersedes=[old.id]; proposals._put(proposal)
    second=Consolidator(SelfModelStore(SqliteBackend(tmp_path/'self.sqlite'),'synthetic'),
                        EpisodeStore(tmp_path/'episodes.sqlite'),ProposalStore(tmp_path/'proposals.sqlite'))
    barrier=Barrier(2)
    def attempt(consolidator):
        barrier.wait()
        try: return consolidator.accept(proposal.id,at=AT)
        except ProposalError: return None
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(attempt,[first,second]))
    winners=[x for x in results if x is not None]
    assert len(winners)==1
    assert len(store.alles())==2
    assert store.get(old.id).superseded_by==winners[0].id
    assert proposals.get(proposal.id).produced==winners[0].id


def test_copied_typed_support_cannot_grant_import_authority(tmp_path):
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    copied=store.record(assertion.statement,Kind.STATE,Provenance(SourceType.INFERENCE),episode_support=assertion.episode_support,at=AT)
    assert assessment(store,episodes,proposals,copied) is None
    commitment=proposals.support_authorization(proposal.id)
    proposal=proposals.get(proposal.id)
    proposal.statement='Anderes Dokument'; proposals._put(proposal)
    assert proposals.support_authorization(proposal.id)==commitment
    assert assessment(store,episodes,proposals,assertion) is None


def test_all_distinct_quotes_validated_and_bounds_reject_whole_capture(tmp_path):
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    proposal.evidence.append(Evidence(sources[0].id,'Erfundenes Zitat',sources[0].digest)); proposals._put(proposal)
    with pytest.raises(ProposalError): consolidator.accept(proposal.id,at=AT)
    assert not store.alles()
    proposal.evidence=[Evidence(sources[0].id,sources[0].body,sources[0].digest)]*17; proposals._put(proposal)
    with pytest.raises(ProposalError): consolidator.accept(proposal.id,at=AT)
    assert not store.alles()


def test_source_and_authorization_survive_timezone_change_and_restart(tmp_path):
    import os, time
    previous=os.environ.get('TZ')
    try:
        os.environ['TZ']='Europe/Berlin'; time.tzset()
        store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path,SqliteBackend(tmp_path/'self.sqlite'))
        assertion=consolidator.accept(proposal.id,at=AT)
        assert assessment(store,episodes,proposals,assertion) is not None
        os.environ['TZ']='UTC'; time.tzset()
        reopened_episodes=EpisodeStore(tmp_path/'episodes.sqlite')
        reopened_proposals=ProposalStore(tmp_path/'proposals.sqlite')
        reopened_store=SelfModelStore(SqliteBackend(tmp_path/'self.sqlite'),'synthetic')
        assert reopened_episodes.support_snapshot(sources[0].id) is not None
        assert assessment(reopened_store,reopened_episodes,reopened_proposals,reopened_store.get(assertion.id)) is not None
        review=SupportReview(reopened_store,reopened_proposals,reopened_episodes,clock=lambda:AT)
        assert review.submit(assertion.id,review.preview(assertion.id)['preview_token'],True)['ok']
        os.environ['TZ']='Europe/Berlin'; time.tzset()
        assert assessment(store,episodes,proposals,store.get(assertion.id)) is not None
    finally:
        if previous is None: os.environ.pop('TZ',None)
        else: os.environ['TZ']=previous
        time.tzset()


def test_projection_cannot_be_hidden_or_forged_and_delete_is_maintained(tmp_path):
    import sqlite3
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    with pytest.raises(sqlite3.IntegrityError):
        with episodes._conn:
            episodes._conn.execute('DELETE FROM episode_produced_assertions WHERE assertion_id=?',(assertion.id,))
    with pytest.raises(sqlite3.IntegrityError):
        with proposals._conn:
            proposals._conn.execute("UPDATE proposals SET state='pending' WHERE id=?",(proposal.id,))
    with episodes._conn: episodes._conn.execute('DELETE FROM episodes WHERE id=?',(sources[0].id,))
    assert sources[0].id not in episodes.produced_support_links(assertion.id)
    assert assessment(store,episodes,proposals,assertion) is None


def test_actual_api_requires_auth_and_strict_explicit_confirmation(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app, TOKEN_ENV
    from icarus_memory.agent import Agent
    from icarus_memory.policy import Policy
    from icarus_memory.audit import AuditLog
    store, episodes, proposals, sources, proposal, assertion=legacy(tmp_path)
    monkeypatch.setenv(TOKEN_ENV,'synthetic-token')
    audit=AuditLog(tmp_path/'audit.sqlite')
    agent=Agent(store,Policy(),audit,{},support_resolver=EpisodeSupportResolver(proposals,episodes),episodes=episodes)
    app=create_app(store=store,agent=agent,episodes=episodes,proposals=proposals,audit=audit)
    client=TestClient(app)
    assert client.get('/api/v1/assertions/support-review').status_code==401
    client.headers['x-icarus-token']='synthetic-token'
    base=f'/api/v1/assertions/{assertion.id}/support-reassessment'
    preview=client.post(base+'/preview').json()
    assert preview['preview_token']
    for confirmed in (False,1,'true'):
        assert client.post(base,json={'preview_token':preview['preview_token'],'confirmed':confirmed}).status_code==422
    assert client.post(base,json={'preview_token':preview['preview_token'],'confirmed':True,'support':{}}).status_code==422
    assert client.post(base,json={'preview_token':preview['preview_token'],'confirmed':True}).status_code==200
    assert client.post(base,json={'preview_token':preview['preview_token'],'confirmed':True}).status_code==409


@pytest.mark.parametrize('failure',['producer','assertion'])
def test_commit_failure_preserves_old_supersession_and_never_grants_usable_orphan(tmp_path,failure):
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path,SqliteBackend(tmp_path/'self.sqlite'))
    old=store.record('Vorher gültig',Kind.STATE,Provenance(SourceType.USER_STATED),at=AT)
    proposal.supersedes=[old.id]; proposals._put(proposal)
    owner=proposals if failure=='producer' else store._backend
    original=owner._conn
    class CommitFailure:
        def __getattr__(self,key): return getattr(original,key)
        def commit(self): raise OSError('synthetic commit failure')
    owner._conn=CommitFailure()
    with pytest.raises(OSError): consolidator.accept(proposal.id,at=AT)
    owner._conn=original
    assert store.get(old.id).is_usable(AT)
    assert store.get(old.id).superseded_by is None
    assert len(store.alles())==1
    producer=proposals.get(proposal.id)
    if failure=='producer':
        assert producer.state.value=='pending'
        assert proposals.support_authorization(proposal.id) is None
    else:
        assert producer.state.value=='accepted'
        assert store.get(producer.produced) is None


def test_accept_versus_reject_share_real_database_pending_reservation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path,SqliteBackend(tmp_path/'self.sqlite'))
    old=store.record('Vorher',Kind.STATE,Provenance(SourceType.USER_STATED),at=AT)
    proposal.supersedes=[old.id]; proposals._put(proposal)
    competitor=ProposalStore(tmp_path/'proposals.sqlite')
    barrier=Barrier(2)
    def accept():
        barrier.wait()
        try: return consolidator.accept(proposal.id,at=AT)
        except ProposalError: return None
    def reject():
        barrier.wait()
        try: return competitor.reject(proposal.id,at=AT)
        except ProposalError: return None
    with ThreadPoolExecutor(2) as pool:
        a=pool.submit(accept); b=pool.submit(reject); result=a.result(); b.result()
    decision=proposals.get(proposal.id)
    if decision.state.value=='accepted':
        assert result is not None and store.get(old.id).superseded_by==result.id
    else:
        assert result is None and store.get(old.id).superseded_by is None and len(store.alles())==1


@pytest.mark.parametrize('state',['pending','accepted'])
def test_generic_proposal_import_rejects_forged_authority(tmp_path,state,monkeypatch):
    import json
    from icarus_memory.proposals import ProposalError
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    document=proposal.to_dict(); document['state']=state
    document['support_authorization']={'version':1,'operation':'acceptance','support_hash':'fake'}
    with pytest.raises(ProposalError): ProposalStore._from_row({'document':json.dumps(document)})
    monkeypatch.setattr(proposal,'to_dict',lambda:document)
    with pytest.raises(ProposalError): proposals._put(proposal)
    assert proposals.support_authorization(proposal.id) is None
    with pytest.raises(TypeError): proposals.accept(proposal.id,support_authorization=document['support_authorization'])
    assert proposals.get(proposal.id).state.value=='pending'


def test_existing_producer_cannot_import_replacement_authority(tmp_path,monkeypatch):
    from icarus_memory.proposals import ProposalError
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    commitment=proposals.support_authorization(proposal.id)
    proposal=proposals.get(proposal.id); document=proposal.to_dict()
    document['support_authorization']={**commitment,'authorization_id':'x'*32}
    monkeypatch.setattr(proposal,'to_dict',lambda:document)
    with pytest.raises(ProposalError): proposals._put(proposal)
    assert proposals.support_authorization(proposal.id)==commitment
    assert assessment(store,episodes,proposals,assertion)


def test_index_finds_old_producer_behind_5001_unrelated_proposals_and_rejects_duplicate(tmp_path):
    from copy import deepcopy
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    with proposals.transaction():
        for number in range(5001):
            unrelated=deepcopy(proposal); unrelated.id=f'p-unrelated-{number:05d}'
            unrelated.statement=f'Unrelated {number}'
            proposals._put(unrelated)
    assert assessment(store,episodes,proposals,assertion)
    assert SupportReview(store,proposals,episodes,clock=lambda:AT).list()['items'][0]['id']==assertion.id
    duplicate=deepcopy(proposals.get(proposal.id)); duplicate.id='p-duplicate'
    proposals._put(duplicate)
    assert assessment(store,episodes,proposals,assertion) is None
    assert SupportReview(store,proposals,episodes,clock=lambda:AT).preview(assertion.id)['preview_token'] is None


def test_tracked_metadata_head_and_archive_contract(tmp_path):
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    tracked,_=episodes.record(EpisodeKind.DOCUMENT,'Tracked original','ORION Originaltext',
                              Provenance(SourceType.DOCUMENT),source_key='synthetic:tracked',at=AT)
    episodes.advance_source_head('synthetic:tracked',None,tracked.id)
    proposal.evidence=[Evidence(tracked.id,tracked.body,tracked.digest)]; proposals._put(proposal)
    assertion=consolidator.accept(proposal.id,at=AT)
    archived=episodes.get(tracked.id); archived.state=EpisodeState.ARCHIVED; episodes._put(archived)
    assert assessment(store,episodes,proposals,assertion)
    changed,_=episodes.record(EpisodeKind.DOCUMENT,'Changed metadata',tracked.body,
                              Provenance(SourceType.DOCUMENT),source_key='synthetic:tracked',at=AT)
    assert changed.id != tracked.id and changed.digest==tracked.digest
    episodes.advance_source_head('synthetic:tracked',tracked.id,changed.id)
    assert assessment(store,episodes,proposals,assertion) is None
    assert SupportReview(store,proposals,episodes,clock=lambda:AT).preview(assertion.id)['preview_token'] is None


@pytest.mark.parametrize('mutation',['confirm','retract','redact'])
def test_preview_cas_detects_concurrent_mutation_on_another_sqlite_connection(tmp_path,monkeypatch,mutation):
    from datetime import timedelta
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from icarus_memory.backends import ImmutableContentError
    from icarus_memory.store import ConflictError
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path,SqliteBackend(tmp_path/'self.sqlite'))
    assertion=consolidator.accept(proposal.id,at=AT)
    second=SelfModelStore(SqliteBackend(tmp_path/'self.sqlite'),'synthetic')
    episodes.ignore(sources[1].id); episodes.reopen(sources[1].id)
    review=SupportReview(store,proposals,episodes,clock=lambda:AT)
    token=review.preview(assertion.id)['preview_token']
    commitment=proposals.support_authorization(proposal.id)
    paused,proceed=Event(),Event(); original=store.reassess_support
    def race(*args,**kwargs):
        paused.set(); assert proceed.wait(3)
        return original(*args,**kwargs)
    monkeypatch.setattr(store,'reassess_support',race)
    with ThreadPoolExecutor(1) as pool:
        job=pool.submit(review.submit,assertion.id,token,True)
        assert paused.wait(3)
        getattr(second,mutation)(assertion.id,at=AT+timedelta(seconds=1))
        proceed.set()
        with pytest.raises((ImmutableContentError,ConflictError)): job.result(timeout=3)
    assert proposals.support_authorization(proposal.id)==commitment
    assert assessment(store,episodes,proposals,store.get(assertion.id)) is None


def test_token_expiry_capacity_and_paginated_orphan_scan_are_bounded(tmp_path):
    from datetime import timedelta
    store, episodes, proposals, sources, proposal, assertion=legacy(tmp_path)
    clock=[AT]; review=SupportReview(store,proposals,episodes,clock=lambda:clock[0])
    first=review.preview(assertion.id)['preview_token']
    for number in range(256): review.preview(assertion.id)
    assert len(review.tokens)==256 and first not in review.tokens
    token=review.preview(assertion.id)['preview_token']; clock[0]+=timedelta(minutes=11)
    with pytest.raises(SupportReviewConflict): review.submit(assertion.id,token,True)
    assert not review.tokens
    # Fehlende kanonische Wurzeln dürfen die Fortsetzung nicht verschlucken.
    source=episodes.get(sources[0].id); source.produced=[f'0-orphan-{i:03}' for i in range(101)]; episodes._put(source)
    page=review.list(limit=1)
    assert not page['items'] and page['truncated'] and page['next_cursor']
    page=review.list(cursor=page['next_cursor'],limit=1)
    assert page['items'][0]['id']==assertion.id


@pytest.mark.parametrize('route',['same','scoped','restart','external'])
def test_actual_provider_revalidates_secondary_episode_and_persisted_history(tmp_path,monkeypatch,route):
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.policy import Policy
    from icarus_memory.providers import Reply
    for module in ('model','context','currency','store'):
        monkeypatch.setattr(f'icarus_memory.{module}.now',lambda:AT)
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path,SqliteBackend(tmp_path/'self.sqlite'))
    assertion=consolidator.accept(proposal.id,at=AT)
    class RecordingProvider:
        name=model='synthetic'
        is_local=True
        def __init__(self): self.messages=[]
        def complete(self,messages,tools): self.messages.append(messages); return Reply(text='OLD_EPISODE_DERIVATION')
    provider=RecordingProvider(); audit=AuditLog(tmp_path/'audit.sqlite')
    def build_agent(store,episodes,proposals):
        return Agent(store,Policy(),audit,{},provider=provider,episodes=episodes,
                     support_resolver=EpisodeSupportResolver(proposals,episodes))
    agent=build_agent(store,episodes,proposals)
    first=agent.send('ORION?')
    assert assertion.id in first.context['self_model_inputs']
    assert first.context['self_model_lineage_version']==3
    history=[{'role':'user','content':'ORION?'},{'role':'assistant','content':first.reply,'context':first.context}]
    if route=='scoped': agent=agent.scoped(provider,frozenset()); agent.load_history(history)
    if route=='restart':
        agent=build_agent(SelfModelStore(SqliteBackend(tmp_path/'self.sqlite'),'synthetic'),
            EpisodeStore(tmp_path/'episodes.sqlite'),ProposalStore(tmp_path/'proposals.sqlite'))
        agent.load_history(history)
    if route=='external': provider.is_local=False
    else: episodes.ignore(sources[1].id)
    second=agent.send('ORION?')
    assert second.context['self_model_history_reset']
    assert assertion.statement not in str(provider.messages[-1])
    assert 'OLD_EPISODE_DERIVATION' not in str(provider.messages[-1])
    assert not second.context['self_model_inputs']


def test_withdrawn_complete_episode_basis_can_qualify_decision_history_but_missing_cannot(tmp_path,monkeypatch):
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.policy import Policy
    from icarus_memory.providers import Reply
    for module in ('model','context','currency','store'):
        monkeypatch.setattr(f'icarus_memory.{module}.now',lambda:AT)
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    parent=consolidator.accept(proposal.id,at=AT)
    child=store.record('ZEUS wird begonnen.',Kind.DECISION,Provenance(SourceType.INFERENCE),derived_from=[parent.id],at=AT)
    class Provider:
        name=model='synthetic'
        is_local=True
        def complete(self,messages,tools): return Reply(text='DECISION_REPLY')
    agent=Agent(store,Policy(),AuditLog(tmp_path/'audit.sqlite'),{},provider=Provider(),episodes=episodes,
                support_resolver=EpisodeSupportResolver(proposals,episodes))
    agent.send('ZEUS?'); episodes.ignore(sources[1].id)
    reviewed=agent.send('ZEUS?')
    assert reviewed.context['items'][0]['assertion_id']==child.id
    assert reviewed.context['items'][0]['basis']['state']=='review'
    agent.load_history([{'role':'assistant','content':reviewed.reply,'context':reviewed.context}])
    assert not agent.send('ZEUS?').context['self_model_history_reset']
    with episodes._conn: episodes._conn.execute('DELETE FROM episodes WHERE id=?',(sources[1].id,))
    assert not agent.send('ZEUS?').context['items']


def test_ambiguous_legacy_heads_never_authorize_acceptance_or_review(tmp_path):
    from icarus_memory.proposals import ProposalError
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    episodes.advance_source_head('file:A',None,sources[0].id)
    episodes.advance_source_head('file:B',None,sources[0].id)
    with pytest.raises(ProposalError): consolidator.accept(proposal.id,at=AT)
    assertion=store.record(proposal.statement,Kind.STATE,Provenance(SourceType.INFERENCE),at=AT)
    proposals.accept(proposal.id,produced=assertion.id,at=AT)
    assert assessment(store,episodes,proposals,assertion) is None
    assert SupportReview(store,proposals,episodes,clock=lambda:AT).preview(assertion.id)['preview_token'] is None


@pytest.mark.parametrize('changed',['root','producer','ancestor','scope'])
def test_preview_binding_rejects_changes_without_new_authorization(tmp_path,changed):
    from datetime import timedelta
    store, episodes, proposals, sources, proposal, assertion=legacy(tmp_path)
    parent=store.record('Ursprüngliche Grundlage',Kind.STATE,Provenance(SourceType.USER_STATED),at=AT)
    # Vorhandene historische Ableitung, nicht während einer Freigabe erfunden.
    stored=store.get(assertion.id); stored.derived_from=[parent.id]; store._backend.put(stored)
    review=SupportReview(store,proposals,episodes,clock=lambda:AT)
    token=review.preview(assertion.id)['preview_token']; assert token
    if changed=='root': store.confirm(assertion.id,at=AT+timedelta(seconds=1))
    if changed=='producer':
        value=proposals.get(proposal.id); value.rationale='Geänderte Erklärung'; proposals._put(value)
    if changed=='ancestor': store.confirm(parent.id,at=AT+timedelta(seconds=1))
    if changed=='scope': review.ceiling=Sensitivity.SENSITIVE
    with pytest.raises(SupportReviewConflict): review.submit(assertion.id,token,True)
    assert store.get(assertion.id).episode_support is None
    assert proposals.support_authorization(proposal.id) is None


def test_age_outdated_root_keeps_original_factual_date_and_qualification(tmp_path):
    from datetime import timedelta
    store, episodes, proposals, sources, proposal, assertion=legacy(tmp_path)
    review=SupportReview(store,proposals,episodes,clock=lambda:AT+timedelta(days=400))
    preview=review.preview(assertion.id)
    assert preview['item']['currency']=='outdated' and preview['item']['eligible']
    result=review.submit(assertion.id,preview['preview_token'],True)
    assert result['item']['currency']=='outdated'
    assert result['item']['factual_at']==preview['item']['factual_at']
    assert store.get(assertion.id).last_confirmed_at==assertion.last_confirmed_at


def test_portable_support_roundtrip_is_data_not_authorization(tmp_path):
    from icarus_memory.backends import assertion_from_dict
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    document=store.export().to_dict()['assertions'][0]
    copied=assertion_from_dict(document)
    assert copied.episode_support==assertion.episode_support
    imported_store=SelfModelStore(MemoryBackend(),'imported'); imported_store._backend.put(copied)
    empty_proposals=ProposalStore(tmp_path/'imported-proposals.sqlite')
    assert assessment(imported_store,episodes,empty_proposals,copied) is None
    # Dasselbe Dokument gegen die tatsächlich lokale Entscheidung ist zulässig.
    assert assessment(imported_store,episodes,proposals,copied)
    document['episode_support']['unexpected']='authority'
    with pytest.raises(ValueError): assertion_from_dict(document)


def test_legacy_migration_creates_no_support_or_authorization_and_keeps_ambiguous_identity_blocked(tmp_path):
    import sqlite3
    from icarus_memory.support_schema import EPISODE_TRIGGERS,PROPOSAL_TRIGGERS
    store, episodes, proposals, sources, proposal, assertion=legacy(tmp_path)
    episodes.advance_source_head('legacy:A',None,sources[0].id)
    episodes.advance_source_head('legacy:B',None,sources[0].id)
    episodes.close(); proposals.close()
    with sqlite3.connect(tmp_path/'episodes.sqlite') as conn:
        from tests.working_memory_legacy import drop_intake_extensions
        drop_intake_extensions(conn)
        for table in ('working_memory_terms', 'working_memory_items', 'working_memory_sources', 'working_memory_scan'):
            conn.execute('DROP TABLE '+table)
        for trigger in EPISODE_TRIGGERS: conn.execute('DROP TRIGGER '+trigger)
        conn.execute('DROP INDEX idx_source_heads_episode')
        conn.execute('DROP TABLE episode_produced_assertions')
        conn.execute('ALTER TABLE episodes DROP COLUMN support_generation')
        conn.execute('PRAGMA user_version=5')
    with sqlite3.connect(tmp_path/'proposals.sqlite') as conn:
        for trigger in PROPOSAL_TRIGGERS: conn.execute('DROP TRIGGER '+trigger)
        conn.execute('DROP INDEX idx_proposals_produced')
        conn.execute('ALTER TABLE proposals DROP COLUMN produced_assertion_id')
        conn.execute('ALTER TABLE proposals DROP COLUMN support_authorization')
        conn.execute('PRAGMA user_version=4')
    episodes=EpisodeStore(tmp_path/'episodes.sqlite'); proposals=ProposalStore(tmp_path/'proposals.sqlite')
    assert proposals.support_authorization(proposal.id) is None
    assert store.get(assertion.id).episode_support is None
    assert assessment(store,episodes,proposals,assertion) is None
    assert not SupportReview(store,proposals,episodes,clock=lambda:AT).preview(assertion.id)['evidence']


def test_failed_commitment_publication_keeps_intermediate_reassessment_unusable(tmp_path,monkeypatch):
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    old=proposals.support_authorization(proposal.id)
    episodes.ignore(sources[1].id); episodes.reopen(sources[1].id)
    review=SupportReview(store,proposals,episodes,clock=lambda:AT)
    token=review.preview(assertion.id)['preview_token']
    def fail(*args): raise RuntimeError('synthetic second database failure')
    monkeypatch.setattr(proposals,'_issue_support_authorization',fail)
    with pytest.raises(RuntimeError,match='second database'): review.submit(assertion.id,token,True)
    assert store.get(assertion.id).episode_support != assertion.episode_support
    assert proposals.support_authorization(proposal.id)==old
    assert assessment(store,episodes,proposals,store.get(assertion.id)) is None


def test_current_cards_drop_secondary_withdrawal_without_erasing_historical_message(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory.server import create_app
    from icarus_memory.agent import Agent
    from icarus_memory.policy import Policy
    from icarus_memory.audit import AuditLog
    from icarus_memory.providers import Reply
    for module in ('model','context','currency','store'):
        monkeypatch.setattr(f'icarus_memory.{module}.now',lambda:AT)
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    class Provider:
        name=model='synthetic'
        is_local=True
        def complete(self,messages,tools): return Reply(text='HISTORICAL_EPISODE_REPLY')
    audit=AuditLog(tmp_path/'audit.sqlite')
    agent=Agent(store,Policy(),audit,{},provider=Provider(),episodes=episodes,
                support_resolver=EpisodeSupportResolver(proposals,episodes))
    app=create_app(store,agent=agent,audit=audit,episodes=episodes,proposals=proposals)
    conversation=app.state.conversations.create('Synthetic support history')
    client=TestClient(app); url=f'/api/v1/conversations/{conversation.id}'
    first=client.post(url+'/messages',json={'message':'ORION?','answer_mode':'chat'}).json()
    assert first['context']['items'][0]['assertion_id']==assertion.id
    episodes.ignore(sources[1].id)
    current=client.get(url).json()
    assert not current['context']['items']
    assert current['messages'][-1]['content']=='HISTORICAL_EPISODE_REPLY'
    episodes.reopen(sources[1].id)
    assert not client.get(url).json()['context']['items']


@pytest.mark.parametrize('mode',['active','withdrawn','external','reload'])
def test_model_recall_tool_enforces_support_and_tracks_tool_only_history(tmp_path,monkeypatch,mode):
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.policy import Policy
    from icarus_memory.providers import Reply,ToolCall
    from icarus_memory.tools import build_registry
    for module in ('model','context','currency','store'):
        monkeypatch.setattr(f'icarus_memory.{module}.now',lambda:AT)
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    class Provider:
        name=model='synthetic'
        is_local=mode!='external'
        def __init__(self): self.messages=[]
        def complete(self,messages,tools):
            self.messages.append(messages)
            if len(self.messages)==1:
                assert assertion.statement not in str(messages)
                return Reply(tool_calls=[ToolCall('recall','gedaechtnis_suchen',{'query':'ORION'})])
            return Reply(text='TOOL_ONLY_DERIVATION')
    provider=Provider()
    agent=Agent(store,Policy(),AuditLog(tmp_path/'audit.sqlite'),build_registry(store),provider=provider,
                episodes=episodes,support_resolver=EpisodeSupportResolver(proposals,episodes))
    if mode=='withdrawn': episodes.ignore(sources[1].id)
    result=agent.send('Hallo.')
    expected=mode in ('active','reload')
    assert (assertion.statement in str(provider.messages[-1])) is expected
    assert (assertion.id in result.context['self_model_inputs']) is expected
    if expected:
        if mode=='reload':
            agent=agent.scoped(provider,frozenset({'gedaechtnis_suchen'}))
            agent.load_history([{'role':'assistant','content':result.reply,'context':result.context}])
        episodes.ignore(sources[1].id)
        followup=agent.send('Weiter.')
        assert followup.context['self_model_history_reset']
        assert assertion.statement not in str(provider.messages[-1])
        assert 'TOOL_ONLY_DERIVATION' not in str(provider.messages[-1])


def test_direct_memory_tool_does_not_inherit_local_provider_permission(tmp_path):
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.policy import Policy
    from icarus_memory.tools import build_registry
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    assertion=consolidator.accept(proposal.id,at=AT)
    private=store.record('ORION private Nutzerangabe',Kind.PREFERENCE,Provenance(SourceType.USER_STATED),sensitivity=Sensitivity.SENSITIVE)
    class LocalProvider:
        name=model='synthetic'
        is_local=True
    agent=Agent(store,Policy(),AuditLog(tmp_path/'audit.sqlite'),build_registry(store),provider=LocalProvider(),
                episodes=episodes,support_resolver=EpisodeSupportResolver(proposals,episodes))
    text=agent.invoke('gedaechtnis_suchen',{'query':'ORION'})['text']
    assert assertion.statement not in text
    assert private.statement not in text


@pytest.mark.parametrize('scenario',['during_completion','qualified_decision'])
def test_tool_only_lineage_guards_completion_and_keeps_historical_qualifier(tmp_path,monkeypatch,scenario):
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.policy import Policy
    from icarus_memory.providers import Reply,ToolCall
    from icarus_memory.tools import build_registry
    for module in ('model','context','currency','store'):
        monkeypatch.setattr(f'icarus_memory.{module}.now',lambda:AT)
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    parent=consolidator.accept(proposal.id,at=AT)
    query='ORION'
    if scenario=='qualified_decision':
        child=store.record('ZEUS wird begonnen.',Kind.DECISION,Provenance(SourceType.INFERENCE),derived_from=[parent.id],at=AT)
        episodes.ignore(sources[1].id); query='ZEUS'
    class Provider:
        name=model='synthetic'
        is_local=True
        def __init__(self): self.messages=[]
        def complete(self,messages,tools):
            self.messages.append(messages)
            if len(self.messages)==1: return Reply(tool_calls=[ToolCall('find','gedaechtnis_suchen',{'query':query})])
            if scenario=='during_completion': episodes.ignore(sources[1].id)
            return Reply(text='TOOL_DERIVED_ANSWER')
    provider=Provider()
    agent=Agent(store,Policy(),AuditLog(tmp_path/'audit.sqlite'),build_registry(store),provider=provider,
                episodes=episodes,support_resolver=EpisodeSupportResolver(proposals,episodes))
    turn=agent.send('Hallo.')
    if scenario=='during_completion':
        assert turn.context['invalidated'] and turn.reply!='TOOL_DERIVED_ANSWER'
    else:
        assert 'Grundlage prüfen' in str(provider.messages[-1])
        assert turn.context['self_model_inputs'][child.id]['basis']['state']=='review'
        agent.load_history([{'role':'assistant','content':turn.reply,'context':turn.context}])
        assert not agent.send('Weiter.').context['self_model_history_reset']


@pytest.mark.parametrize('mode',['withdrawn','external','invoke'])
def test_restrictive_policy_does_not_quote_unavailable_constraint_into_provider_or_tool_result(tmp_path,monkeypatch,mode):
    from icarus_memory.agent import Agent
    from icarus_memory.audit import AuditLog
    from icarus_memory.policy import Policy
    from icarus_memory.providers import Reply,ToolCall
    from icarus_memory.tools import build_registry
    for module in ('model','context','currency','store'):
        monkeypatch.setattr(f'icarus_memory.{module}.now',lambda:AT)
    store, episodes, proposals, sources, proposal, consolidator=fixture(tmp_path)
    proposal.statement='PRIVATE_ORION_RULE keine aktuelle_zeit ausführen'
    proposal.assertion_kind=Kind.CONSTRAINT; proposals._put(proposal)
    assertion=consolidator.accept(proposal.id,at=AT)
    class Provider:
        name=model='synthetic'
        is_local=mode!='external'
        def __init__(self): self.messages=[]
        def complete(self,messages,tools):
            self.messages.append(messages)
            if len(self.messages)==1: return Reply(tool_calls=[ToolCall('time','aktuelle_zeit',{})])
            return Reply(text='Kein Werkzeug ausgeführt.')
    provider=Provider()
    agent=Agent(store,Policy(),AuditLog(tmp_path/'audit.sqlite'),build_registry(store),provider=provider,
                episodes=episodes,support_resolver=EpisodeSupportResolver(proposals,episodes))
    if mode=='withdrawn': episodes.ignore(sources[1].id)
    if mode=='invoke':
        result=agent.invoke('aktuelle_zeit',{})
        assert 'PRIVATE_ORION_RULE' not in str(result)
        assert 'Abgelehnt' in result['text']
    else:
        turn=agent.send('Hallo.')
        assert 'PRIVATE_ORION_RULE' not in str(provider.messages)
        assert 'PRIVATE_ORION_RULE' not in str(turn.notices)
        assert 'aktuelle_zeit' not in turn.used_tools


@pytest.mark.parametrize('value',[
    '2026-09-14T00:00:00Z',
    '2026-09-14T00:00:00+00:00',
    '2026-09-14T02:00:00+02:00',
])
def test_canonical_instant_accepts_equivalent_aware_iso_offsets(value):
    from icarus_memory.source_snapshot import canonical_instant
    assert canonical_instant(value)=='2026-09-14T00:00:00+00:00'
    assert canonical_instant(None) is None


@pytest.mark.parametrize('value',[
    '2026-09-14T00:00:00', '2026-09-14', '', 'invalid',
    '2026-09-14T00:00:00ZZ', '2026-09-14T00:00:00Zsuffix',
    '2026-09-14T00:00:00+00:00Z',
])
def test_canonical_instant_rejects_naive_and_malformed_iso_times(value):
    from icarus_memory.source_snapshot import canonical_instant
    with pytest.raises(ValueError): canonical_instant(value)
