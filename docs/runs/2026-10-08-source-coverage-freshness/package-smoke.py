from pathlib import Path
from tempfile import TemporaryDirectory
import json
from icarus_memory import EpisodeStore, EpisodeKind, Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_semantic_index import DurableSemanticIndex
from icarus_memory.working_memory_semantic_service import SemanticService

with TemporaryDirectory() as tmp:
    episodes=EpisodeStore(Path(tmp)/'episodes.sqlite3')
    source,_=episodes.record(EpisodeKind.MESSAGE,'Original','Die Zugangskarte liegt im Tresor.',Provenance(SourceType.CHAT,source_ref='synthetic:local'))
    memory=WorkingMemoryStore(episodes)
    def classify():
        snapshot=memory.pending(episode_ids=[source.id])[0]
        assert memory.commit(snapshot,[{'start':0,'end':len(source.body),'kind':'fact'}],model='synthetic')
    classify()
    index=DurableSemanticIndex(episodes,'local-test:'+'a'*64)
    service=SemanticService(episodes,lambda: (_ for _ in ()).throw(AssertionError('No model permitted')))
    assert index.commit(index.pending(1),[[1.,0.]])==1
    assert index.coverage()['indexed']==1
    reference=memory.search('Zugangskarte')['refs'][0]
    with episodes.transaction():
        episodes._conn.execute('DELETE FROM mail_intake_analysis WHERE episode_id=?',(source.id,))
    assert memory.progress()['remaining']==1 and service._source_pending()==1
    assert index.coverage()['indexed']==0
    assert memory.pending(episode_ids=[source.id])==[]
    assert index.coverage()['indexed']==1
    assert memory.resolve(reference).episode.body==source.body
    episodes.add_contacts(source.id,[{'name':'Nora Beispiel','adresse':'nora@example.test','rolle':'sender'}],['Nora Beispiel'])
    assert memory.progress()['done']==0 and memory.progress()['remaining']==1
    assert service._source_pending()==1 and index.coverage()['indexed']==0
    assert index.pending(1).refs==()
    classify()
    assert index.commit(index.pending(1),[[1.,0.]])==1
    assert memory.progress()['done']==1 and service._source_pending()==0
    assert index.search([1.,0.]).refs
    episodes.ignore(source.id)
    assert index.search([1.,0.]).refs==()
    assert memory.resolve(reference) is None
    service.close();index.close();episodes.close()
print(json.dumps({'synthetic_only':True,'metadata_reopens_progress':True,'stale_items_not_embedded':True,'legacy_vector_reused_without_inference':True,'withdrawal_blocks':True,'model_calls':0}))
