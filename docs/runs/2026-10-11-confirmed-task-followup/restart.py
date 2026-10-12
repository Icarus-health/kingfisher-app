import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend import app
root=Path(__file__).parent
previous=json.loads((root/'verification.json').read_text())
with TestClient(app) as client:
    files=client.get('/api/v1/sources/documents').json()['items']
    assert len(files)==1
    assert files[0]['id']==previous['source_id']
    source=client.get('/api/v1/episodes/'+previous['source_id']).json()
    assert source['body']=='# Künstliche Projektquelle\nAm 12. Oktober wird der Testbericht besprochen.\nKeine echten Personen oder Termine.\n'
    assert source['state']=='ignored'
    assert source['project_id']==previous['project_id']
    assert source['provenance']['source_ref']=='upload:synthetisch.txt'
    assert app.state.claims.all_claims()==[]
    assert app.state.agent.provider is None
    assert app.state.hintergrund.pausiert is True
proof={'scope':'Fresh process, same synthetic SQLite files after backend shutdown','source_count':1,'exact_body_preserved':True,'project_preserved':True,'original_provenance_preserved':True,'exclusion_preserved':True,'confirmed_claims_count':0,'model_provider':None,'background_paused':True}
(root/'restart-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof))

seed=json.loads((root/'task-seed.json').read_text())
task=app.state.tasks.get(seed['task_id'])
assert task.to_dict()==seed['task_before']
assert app.state.episodes.get(seed['reply_episode_id']).body=='Absage: Der künstliche Testauftrag entfällt.'
with TestClient(app) as client:
    status=client.get('/api/v1/tasks/'+task.id+'/source').json()
    assert status['source_review']['followup_episode_id']==seed['reply_episode_id']
    assert task.to_dict()==seed['task_before']
proof.update(task_unchanged_after_restart=True,followup_retained_after_restart=True,task_original_preserved=True)
(root/'restart-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof))
