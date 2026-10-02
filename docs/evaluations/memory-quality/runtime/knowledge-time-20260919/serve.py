"""Synthetic HTTP fixture with real persistence and a recording local provider."""
import json
import os
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import uvicorn
from icarus_memory import SelfModelStore, SqliteBackend
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.policy import Policy
from icarus_memory.proposals import ProposalStore, Evidence
from icarus_memory.providers import Reply
from icarus_memory.server import create_app
from icarus_memory.secrets import Keychain

root = Path(os.environ['ICARUS_DATA_DIR'])
root.mkdir(parents=True, exist_ok=True)
Keychain._detect = lambda self: 'none'
utc = lambda value: datetime.fromisoformat(value.replace('Z', '+00:00'))
store = SelfModelStore(SqliteBackend(root/'self-model.sqlite3'), 'synthetic-m2c')
episodes = EpisodeStore(root/'episodes.sqlite3')
proposals = ProposalStore(root/'proposals.sqlite3')
claims = ClaimStore(root/'knowledge.sqlite3')
audit = AuditLog(root/'audit.sqlite3')
if not (root/'state.json').exists():
    claims.entities.create('person', 'Synthetische Person', explicit_id='person:orion-casey')
    claims.entities.create('project', 'Synthetisches Projekt', explicit_id='project:orion')
    service = KnowledgeService(episodes=episodes, proposals=proposals, claims=claims)
    state = {}
    for label, event in [('ORION', '2024-09-14T09:00:00Z'), ('NEBEL', None)]:
        body = f'Im Projekt {label} übernimmt Casey die Koordination.'
        originals = [episodes.record(EpisodeKind.MESSAGE, f'{label} Beleg {n}', body,
            Provenance(SourceType.EMAIL, source_ref=f'synthetic:{label}:{n}'),
            occurred_at=utc(event) if event else None, at=utc('2026-09-18T10:00:00Z'))[0]
            for n in range(2)]
        proposal, _ = service.propose(subject_ref='person:orion-casey', predicate='role', value='Koordination',
            statement=f'{label} ist vermerkt.', rationale='Expliziter synthetischer Prüfbestand',
            evidence=[Evidence(e.id, body, e.digest) for e in originals], target_ref='project:orion',
            valid_from=utc('2026-09-01T00:00:00Z'), valid_until=utc('2030-10-01T00:00:00Z'))
        claim = service.accept(proposal.id, supersedes=[], at=utc('2026-09-19T10:00:00Z'))
        # Expected values frozen before any Agent invocation; no production projector.
        expected = {'format':'knowledge-context-v3','assertion_id':'claim:'+claim.id,
            'statement':f'{label} ist vermerkt.','subject_ref':'person:orion-casey',
            'target_ref':'project:orion','scope_ref':None,'predicate':'role','value':'Koordination',
            'claim_created_at':'2026-09-19T10:00:00+00:00','valid_from':'2026-09-01T00:00:00+00:00',
            'valid_until':'2030-10-01T00:00:00+00:00','primary_evidence':{
                'episode_id':originals[0].id,'digest':originals[0].digest,'source_type':'email',
                'source_ref':f'synthetic:{label}:0','occurred_at':'2024-09-14T09:00:00+00:00' if event else None,
                'recorded_at':'2026-09-18T10:00:00+00:00'}}
        state[label] = {'claim_id':claim.id,'episode_ids':[e.id for e in originals], 'expected':expected}
    (root/'state.json').write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n')
if not (root/'mode').exists():
    (root/'mode').write_text('local')

class RecordingProvider:
    name = 'synthetic-recording'
    model = 'deterministic-m2c'
    @property
    def is_local(self):
        return (root/'mode').read_text().strip() == 'local'
    def complete(self, messages, tools):
        path = root/'provider.jsonl'
        number = len(path.read_text().splitlines())+1 if path.exists() else 1
        with path.open('a') as file:
            file.write(json.dumps({'local':self.is_local,'messages':deepcopy(messages),'tools':tools}, ensure_ascii=False)+'\n')
        return Reply(text=f'SYNTHETIC_RESPONSE_{number}', model=self.model)

agent = Agent(store, Policy(), audit, {}, provider=RecordingProvider(), knowledge=claims, episodes=episodes)
app = create_app(store=store, agent=agent, audit=audit, episodes=episodes, proposals=proposals, knowledge=claims)
uvicorn.run(app, host=os.environ.get('QA_HOST', '127.0.0.1'), port=int(os.environ.get('QA_PORT', '18994')),
            access_log=False, log_level='warning')
