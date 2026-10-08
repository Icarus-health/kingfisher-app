import json,sqlite3,tempfile
from pathlib import Path
from icarus_memory import EpisodeStore,EpisodeKind,Provenance,SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_semantic_index import DurableSemanticIndex
with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'episodes.sqlite3'
    episodes=EpisodeStore(path)
    item,_=episodes.record(EpisodeKind.MESSAGE,'Synthetic','Die Karte liegt im Tresor.',Provenance(SourceType.CHAT,source_ref='chat:synthetic'))
    store=WorkingMemoryStore(episodes)
    assert store.commit(store.pending()[0],[{'start':0,'end':len(item.body),'kind':'fact'}],model='synthetic')
    cache=DurableSemanticIndex(episodes,'synthetic:'+'a'*64)
    assert cache.commit(cache.pending(64),[[1.,0.,0.]])==1
    cache.close();episodes.close()
    with sqlite3.connect(path) as db: assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    episodes=EpisodeStore(path);cache=DurableSemanticIndex(episodes,'synthetic:'+'a'*64)
    assert cache.pending(64).refs==()
    assert cache.search([1.,0.,0.]).refs[0]['episode_id']==item.id
    episodes.ignore(item.id)
    assert cache.search([1.,0.,0.]).refs==()
    assert cache.prune(64)==1
    cache.close();episodes.close()
print(json.dumps({'synthetic_only':True,'linux_storage_restart':True,'source_withdrawal':True,'original_quick_check':True,'no_network':True}))
