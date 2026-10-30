"""Neue Fristnachrichten machen alte Belege nicht zu aktuellen Aufträgen.

Nur künstliche Mails; keine Anbieteraufrufe. Der 2./4.-November-Fall stammt aus
unserer eingefrorenen synthetischen Vergleichsprobe.
"""
from datetime import datetime, timedelta, timezone
from threading import RLock
from types import SimpleNamespace

import pytest

from icarus_memory.aufgaben_von_selbst import Durchlauf
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import ProposalError, ProposalKind, ProposalState, ProposalStore
from icarus_memory.task_candidates import TaskCandidates
from icarus_memory.task_detection import candidate_batches, for_briefing
from icarus_memory.task_review import current_task_context
from icarus_memory.claims import ClaimStore
from icarus_memory.tasks import TaskStore
from icarus_memory.source_versions import track_source
from icarus_memory.workspace import WorkspaceStore

from tests.test_local_mail_workflow import env as saved_mail_env

NOW = datetime(2026, 10, 30, 14, tzinfo=timezone.utc)
OLD = 'Bitte schicke mir die Druckdaten für Projekt Atlas bis zum 2. November 2026 um 18 Uhr.'
NEW = 'Die Frist für die Druckdaten wurde geändert: Statt dem 2. November gilt jetzt der 4. November 2026 um 18 Uhr.'
OWNER = 'lena@repair.invalid'


@pytest.fixture
def world(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    workspace = WorkspaceStore(tmp_path / 'workspace.sqlite3')
    accept = TaskCandidates(episodes, proposals, tasks, workspace, RLock()).accept
    run = Durchlauf(tasks, episodes, proposals, workspace=workspace,
                    eigene=lambda: [OWNER], jetzt=lambda: NOW)
    yield SimpleNamespace(episodes=episodes, claims=claims, proposals=proposals, tasks=tasks, accept=accept, run=run)
    for store in (episodes, claims, proposals, tasks, workspace):
        store.close()


def mail(world, key, *, title='Projekt Atlas: Druckdaten', body=OLD,
         sender='winter@alpha.invalid', recipient=OWNER, at=None, source_key=None, account='work'):
    source = world.episodes.record(EpisodeKind.MESSAGE, title, body,
        Provenance(source_type=SourceType.EMAIL, source_ref=f'{account}:<{key}@repair.invalid>'),
        source_key=source_key or key, occurred_at=at or NOW - timedelta(hours=2),
        at=NOW, contacts=[{'rolle': 'von', 'adresse': sender, 'name': 'Alex Winter'},
                          {'rolle': 'an', 'adresse': recipient, 'ich': recipient == OWNER}])[0]
    track_source(world.episodes, world.claims, source_key or key, source)
    return source


def candidate(world, source):
    with world.proposals.transaction():
        world.proposals._record_task_candidates(source.id, source.digest,
            [{'title': 'Druckdaten bis 2. November 2026 senden', 'quote': source.body}],
            proposed_by='synthetic/local/task-review-v1',
            task_context=current_task_context(world.episodes, source.id))
    return next(p for p in world.proposals.pending(ProposalKind.TASK)
                if p.evidence[0].episode_id == source.id)


def changed_mail(world, **kwargs):
    return mail(world, 'change', title=kwargs.pop('title', 'Projekt Atlas: Frist geändert'),
                body=kwargs.pop('body', NEW), at=NOW - timedelta(hours=1), **kwargs)


def test_later_exact_party_deadline_correction_moves_original_to_visible_review(world):
    source = mail(world, 'request')
    proposal = candidate(world, source)
    before = proposal.to_dict()
    later = changed_mail(world)
    result = for_briefing(world.proposals, world.episodes, now=NOW)
    assert result['items'] == [] and result['review_pending'] == 1
    [[(visible, original, timing)]] = list(candidate_batches(world.proposals, world.episodes, now=NOW))
    assert visible.id == proposal.id and original.id == source.id
    assert timing['temporal_status'] == 'followup'
    assert timing['followup_episode_id'] == later.id
    assert timing['review_required'] is True
    assert world.proposals.get(proposal.id).to_dict() == before
    assert world.episodes.get(source.id).body == OLD


def test_stale_accept_button_cannot_create_old_deadline_task_before_any_list_refresh(world):
    proposal = candidate(world, mail(world, 'request'))
    changed_mail(world)
    with pytest.raises(ProposalError, match='Frist'):
        world.accept(proposal.id, title=proposal.statement,
                     due=datetime(2026, 11, 2, 18, tzinfo=timezone.utc))
    assert world.tasks.all_tasks() == []
    assert world.proposals.get(proposal.id).state is ProposalState.PENDING


def test_blind_group_acceptance_leaves_conflicting_candidate_for_review(world):
    proposal = candidate(world, mail(world, 'request'))
    changed_mail(world)
    result = world.run.alle_uebernehmen([proposal.id], annehmen=world.accept)
    assert result['aufgaben'] == [] and result['fehler'][0]['id'] == proposal.id
    assert world.tasks.all_tasks() == []
    assert world.run.vorbefuellt(proposal)['frist_vorschlag'] is None


def test_automatic_creation_cannot_use_superseded_deadline(world):
    candidate(world, mail(world, 'request'))
    changed_mail(world)
    assert world.run.schritt()['angelegt'] == 0
    assert world.tasks.all_tasks() == []


@pytest.mark.parametrize('variation', ['other_address', 'other_recipient', 'other_project',
    'other_task', 'older', 'ignored', 'archived', 'replaced', 'quoted', 'other_account'])
def test_unrelated_or_withdrawn_correction_does_not_join_people_or_suppress_request(world, variation):
    source = mail(world, 'request')
    proposal = candidate(world, source)
    kwargs = {}
    if variation == 'other_address': kwargs['sender'] = 'winter@home.invalid'
    if variation == 'other_recipient': kwargs['recipient'] = 'someone@repair.invalid'
    if variation == 'other_project': kwargs['title'] = 'Projekt Birke: Frist geändert'
    if variation == 'other_task': kwargs['body'] = NEW.replace('Druckdaten', 'Vertragsunterlagen')
    if variation == 'older': kwargs['at'] = NOW - timedelta(days=1)
    if variation == 'other_account': kwargs['account'] = 'other'
    if variation == 'quoted':
        kwargs['body'] = 'Danke.\n\nAm 29. Oktober 2026 schrieb Alex:\n> ' + NEW
    # Deliberately use the same displayed name throughout.
    later = mail(world, 'change', title=kwargs.pop('title', 'Projekt Atlas: Frist geändert'),
                 body=kwargs.pop('body', NEW), at=kwargs.pop('at', NOW-timedelta(hours=1)), **kwargs)
    if variation == 'ignored': world.episodes.ignore(later.id)
    if variation == 'archived':
        world.episodes.mark_consolidated(later.id)
        world.episodes.archive_before(NOW + timedelta(days=1))
    if variation == 'replaced':
        mail(world, 'new-version', source_key='change', body='Vielen Dank, keine neue Frist.',
             at=NOW-timedelta(minutes=30))
    result = for_briefing(world.proposals, world.episodes, now=NOW)
    assert [item['id'] for item in result['items']] == [proposal.id]


def test_rechecking_after_correction_withdrawal_restores_original_without_rewriting(world):
    proposal = candidate(world, mail(world, 'request'))
    later = changed_mail(world)
    assert for_briefing(world.proposals, world.episodes, now=NOW)['review_pending'] == 1
    world.episodes.ignore(later.id)
    assert for_briefing(world.proposals, world.episodes, now=NOW)['pending'] == 1
    assert world.accept(proposal.id, title=proposal.statement).title == proposal.statement


def test_historical_proposal_is_review_only_and_never_an_active_task(world):
    source = mail(world, 'historical', at=datetime(2020, 10, 1, 9, tzinfo=timezone.utc),
                  body='Bitte bringe den Bericht bis zum 5. Oktober 2020 mit.')
    proposal = candidate(world, source)
    result = for_briefing(world.proposals, world.episodes, now=NOW)
    assert result['items'] == [] and result['review_pending'] == 1
    assert world.tasks.all_tasks() == []
    assert world.proposals.get(proposal.id).state is ProposalState.PENDING


def test_incomplete_scan_is_visible_and_cannot_silently_adopt_old_due(world, monkeypatch):
    from icarus_memory import task_deadline_review
    proposal = candidate(world, mail(world, 'request'))
    changed_mail(world)
    mail(world, 'unrelated', title='Projekt Birke: Hallo', body='Vielen Dank.',
         at=NOW-timedelta(minutes=30))
    monkeypatch.setattr(task_deadline_review, 'MAX_MAILS', 1)
    [[(_, _, timing)]] = list(candidate_batches(world.proposals, world.episodes, now=NOW))
    assert timing['temporal_status'] == 'context_limit' and timing['review_required'] is True
    with pytest.raises(ProposalError, match='unvollständig'):
        world.accept(proposal.id, title=proposal.statement)
    assert world.tasks.all_tasks() == []


def test_accepted_task_is_user_decision_and_is_preserved_after_later_correction(world):
    proposal = candidate(world, mail(world, 'request'))
    task = world.accept(proposal.id, title='Meine ausdrücklich angelegte Aufgabe')
    changed_mail(world)
    assert world.accept(proposal.id, title='Andere Eingabe').id == task.id
    assert world.tasks.get(task.id).title == 'Meine ausdrücklich angelegte Aufgabe'


def test_saved_source_view_shows_correction_context_without_preparing_a_model(saved_mail_env):
    from tests.test_local_mail_workflow import root
    app, client, _, calls, _ = saved_mail_env
    world = SimpleNamespace(episodes=app.state.episodes, claims=None, proposals=app.state.proposals)
    source = mail(world, 'request')
    proposal = candidate(world, source)
    later = changed_mail(world)
    result = client.get(root(source)).json()
    assert result['temporal_status'] == 'followup'
    assert result['followup_episode_id'] == later.id
    assert result['items'][0]['id'] == proposal.id
    assert result['items'][0]['review_required'] is True
    assert calls == []


def test_explicit_other_project_in_current_correction_paragraph_is_not_this_task(world):
    proposal = candidate(world, mail(world, 'request'))
    changed_mail(world, body=NEW.replace('Druckdaten', 'Druckdaten für Projekt Birke'))
    assert [item['id'] for item in for_briefing(world.proposals, world.episodes, now=NOW)['items']] == [proposal.id]


def test_query_budget_exhaustion_is_review_only_not_clean_acceptance(world, monkeypatch):
    from icarus_memory import task_deadline_review
    proposal = candidate(world, mail(world, 'request'))
    for i in range(30):
        mail(world, f'noise-{i}', at=NOW-timedelta(minutes=30))
    monkeypatch.setattr(task_deadline_review, 'MAX_QUERY_STEPS', 0, raising=False)
    [[(_, _, timing)]] = list(candidate_batches(world.proposals, world.episodes, now=NOW))
    assert timing['temporal_status'] == 'context_limit'
    assert timing['review_required'] is True
    assert world.tasks.all_tasks() == []
