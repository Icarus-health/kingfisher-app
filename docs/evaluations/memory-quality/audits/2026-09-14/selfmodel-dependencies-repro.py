import copy, json, tempfile
from pathlib import Path
from datetime import timedelta
from icarus_memory import MemoryBackend, SelfModelStore
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.policy import Policy
from icarus_memory.providers import Reply
from icarus_memory.model import Kind, Provenance, SourceType, now
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory import entscheidungen

class Capture:
    name='synthetic'; model='capture'; is_local=True
    def __init__(self): self.calls=[]
    def complete(self, messages, tools):
        self.calls.append(copy.deepcopy(messages)); return Reply(text='SYNTHETIC_PRIOR_DERIVATION')

def setup(folder):
    store=SelfModelStore(MemoryBackend(),subject_id='synthetic')
    provider=Capture()
    agent=Agent(store,Policy(),AuditLog(folder/'audit.sqlite3'),{},provider)
    return store,provider,agent

def prov(ref='synthetic', at=None, inferred=False):
    return Provenance(source_type=SourceType.INFERENCE if inferred else SourceType.USER_STATED,source_ref=ref,captured_at=at or now())

results={}
with tempfile.TemporaryDirectory(prefix='selfmodel-dependencies-') as root:
    root=Path(root)
    for kind in (Kind.STATE,Kind.DECISION):
        folder=root/kind.value; folder.mkdir()
        store,p,a=setup(folder)
        parent=store.record('Budget authorization.',Kind.STATE,prov())
        child=store.record('ORION ist finanziert.',kind,prov(inferred=True),derived_from=[parent.id])
        first=a.send('ORION')
        assert [i['assertion_id'] for i in first.context['items']]==[child.id]
        store.retract(parent.id)
        a.load_history([{'role':'user','content':'ORION'},{'role':'assistant','content':'SYNTHETIC_PRIOR_DERIVATION','context':first.context}])
        second=a.send('ORION')
        results[kind.value]={'parent_status':store.get(parent.id).status.value,'child_status':store.get(child.id).status.value,'context_items':second.context['items'],'history_reset':second.context.get('self_model_history_reset'),'prior_answer_retained':any(m.get('content')=='SYNTHETIC_PRIOR_DERIVATION' for m in p.calls[-1]),'actual_provider_context':p.calls[-1][1]['content']}
        if kind is Kind.DECISION: results[kind.value]['existing_decision_projection_shaken']=entscheidungen.alle(store)[0].erschuettert
    folder=root/'source'; folder.mkdir()
    store,p,a=setup(folder)
    episodes=EpisodeStore(folder/'episodes.sqlite3'); a._episodes=episodes
    episode,_=episodes.record(kind=EpisodeKind.DOCUMENT,title='Synthetic evidence',body='Synthetic evidence body.',provenance=prov())
    child=store.record('VEGA ist finanziert.',Kind.STATE,prov(episode.id,inferred=True))
    episodes.mark_consolidated(episode.id,produced=[child.id])
    first=a.send('VEGA'); episodes.ignore(episode.id)
    second=a.send('VEGA')
    results['source_ignore']={'source_state':episodes.get(episode.id).state.value,'source_produced':episodes.get(episode.id).produced,'child_status':store.get(child.id).status.value,'context_items':second.context['items'],'history_reset':second.context.get('self_model_history_reset'),'prior_answer_retained':any(m.get('content')=='SYNTHETIC_PRIOR_DERIVATION' for m in p.calls[-1]),'actual_provider_context':p.calls[-1][1]['content']}
    folder=root/'control'; folder.mkdir()
    store,p,a=setup(folder)
    store.record('ALTAIR ist finanziert.',Kind.STATE,prov(at=now()-timedelta(days=400)),at=now()-timedelta(days=400))
    turn=a.send('ALTAIR')
    results['age_control']={'state':turn.context['items'][0]['state'],'actual_provider_context':p.calls[-1][1]['content']}
print(json.dumps(results,ensure_ascii=False,indent=2))
