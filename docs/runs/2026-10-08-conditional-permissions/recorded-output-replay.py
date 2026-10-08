"""Replays native Q5's frozen output, without inference/retrieval/network."""
import sys,json,hashlib,importlib.util,subprocess
from pathlib import Path
from datetime import datetime
from icarus_memory import satzantwort,satzpruefung_modell
from icarus_memory.providers import Reply
repo=Path.cwd()
base='ae3e695c32aa910e18fa611b2064447690fd7b82'
def baseline(module):
 path=Path('/private/tmp')/('kingfisher-baseline-conditional-'+module+'.py')
 path.write_bytes(subprocess.check_output(['git','show',base+':sidecar/icarus_memory/'+module+'.py']))
 name='icarus_memory._conditional_baseline_'+module
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
before=baseline('satzantwort');before.satzpruefung=baseline('satzpruefung')
raw=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Testlaeufe/2026-10-08-native-sentence-probe/independent/answers.json').read_bytes()
row=json.loads(raw)['rows'][4]
catalog=json.loads((repo/'docs/evaluations/memory-quality/retrieval-controls/catalog-20261008.json').read_text())
source=next(s for s in catalog['sources'] if s['id']==row['selected_sources'][0])
class Replay:
 is_local=True;name='recorded-native-output';model='qwen3.5:4b'
 def __init__(self):self.responses=iter([o['reply'] for o in row['model_outputs'][2:]]);self.calls=0
 def complete_json(self,*args,**kwargs):self.calls+=1;return Reply(text=next(self.responses))
outputs={}
for label,module in [('before',before),('after',satzantwort)]:
 recorded=row['sentence_answer']['belege'][0];assert recorded['ref']['end']==len(source['text'])
 beleg=module.AntwortBeleg(nummer=recorded['nummer'],ref=recorded['ref'],rolle=recorded['rolle'],episode_id=recorded['ref']['episode_id'],titel=source['title'],kopf=source['title'],text=source['text'],zeit=None)
 provider=Replay();result=module.formulieren(row['q'],[beleg],provider,jetzt=datetime.fromisoformat(row['sentence_answer']['stichtag']),pruefung=satzpruefung_modell.tor('an',provider))
 outputs[label]={'status':result.status,'surviving_sentences':[s.text for s in result.saetze],'rejected':len(result.verworfen),'reasons':[list(s.gruende) for s in result.verworfen],'fallback_reason':result.grund,'replayed_calls':provider.calls}
assert outputs['before']['status']=='saetze' and outputs['after']['status']=='zitate'
assert outputs['before']['surviving_sentences']==[s['text'] for s in row['sentence_answer']['saetze']]
assert outputs['before']['rejected']==outputs['after']['rejected']==1
result={'method':'Recorded native Q5 unchanged model outputs and original source; offline replay only. Not a new model/retrieval/ingestion evaluation. Original rendering and JSON-restoration separately tested.','before_commit':base,'native_raw_sha256':hashlib.sha256(raw).hexdigest(),'question':row['q'],'source':source['id'],**outputs}
Path('/private/tmp/kingfisher-conditional-rule-replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
