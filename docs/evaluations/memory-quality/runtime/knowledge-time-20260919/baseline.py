"""Independent synthetic provider-payload probe, no application data or model."""
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
import json,tempfile
from icarus_memory import MemoryBackend,SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore,KnowledgeService
from icarus_memory.episodes import EpisodeStore,EpisodeKind
from icarus_memory.model import Provenance,SourceType
from icarus_memory.policy import Policy
from icarus_memory.proposals import ProposalStore,Evidence
from icarus_memory.providers import Reply

ROOT=Path(__file__).parent
utc=lambda value:datetime.fromisoformat(value.replace('Z','+00:00'))
class Recorder:
    name=model='synthetic-m2c';is_local=True
    def __init__(self):self.calls=[]
    def complete(self,messages,tools):
        self.calls.append(deepcopy(messages))
        return Reply(text='SYNTHETIC_OLD_ORION_RESPONSE')
with tempfile.TemporaryDirectory(dir=ROOT,prefix='baseline-data-') as directory:
    data=Path(directory)
    episodes=EpisodeStore(data/'episodes.sqlite3');proposals=ProposalStore(data/'proposals.sqlite3')
    claims=ClaimStore(data/'knowledge.sqlite3');audit=AuditLog(data/'audit.sqlite3')
    claims.entities.create('person','Synthetische Person',explicit_id='person:orion-casey')
    claims.entities.create('project','Synthetisches Projekt',explicit_id='project:orion')
    body='Im Projekt ORION übernimmt Casey die Koordination.'
    original,_=episodes.record(EpisodeKind.MESSAGE,'ORION Original',body,
        Provenance(SourceType.EMAIL,source_ref='synthetic:orion:original'),
        occurred_at=utc('2024-09-14T09:00:00Z'),at=utc('2026-09-18T10:00:00Z'))
    service=KnowledgeService(episodes=episodes,proposals=proposals,claims=claims)
    proposal,_=service.propose(subject_ref='person:orion-casey',predicate='role',value='Koordination',
        statement='ORION ist vermerkt.',rationale='Expliziter synthetischer Prüfbestand',
        evidence=[Evidence(original.id,body,original.digest)],target_ref='project:orion',
        valid_from=utc('2026-09-01T00:00:00Z'),valid_until=utc('2030-10-01T00:00:00Z'))
    claim=service.accept(proposal.id,supersedes=[],at=utc('2026-09-19T10:00:00Z'))
    # Frozen before invocation, literal independently checked meanings/dates.
    expected={'format':'knowledge-context-v3','assertion_id':'claim:'+claim.id,
      'statement':'ORION ist vermerkt.','subject_ref':'person:orion-casey',
      'target_ref':'project:orion','scope_ref':None,'predicate':'role','value':'Koordination',
      'claim_created_at':'2026-09-19T10:00:00+00:00','valid_from':'2026-09-01T00:00:00+00:00',
      'valid_until':'2030-10-01T00:00:00+00:00','primary_evidence':{
        'episode_id':original.id,'digest':original.digest,'source_type':'email',
        'source_ref':'synthetic:orion:original','occurred_at':'2024-09-14T09:00:00+00:00',
        'recorded_at':'2026-09-18T10:00:00+00:00'}}
    provider=Recorder();agent=Agent(SelfModelStore(MemoryBackend(),'synthetic'),Policy(),audit,{},
                                  provider=provider,knowledge=claims,episodes=episodes)
    turn=agent.send('Was ist über ORION vermerkt?')
    rows=[json.loads(line[len('- [knowledge] '):]) for msg in provider.calls[-1]
          if isinstance(msg.get('content'),str) for line in msg['content'].splitlines()
          if line.startswith('- [knowledge] ')]
    assert len(rows)==1,rows
    actual={key:value for key,value in rows[0].items() if key!='reason'}
    result={'expected':expected,'actual':actual,'missing_fields':sorted(set(expected)-set(actual)),
            'exact_projection_matches':expected==actual,'raw_messages':provider.calls[-1],
            'context_items':turn.context['items'],'synthetic_only':True}
    (ROOT/'baseline-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('missing_fields','exact_projection_matches','synthetic_only')}))
    for store in (audit,claims,proposals,episodes):store.close()
