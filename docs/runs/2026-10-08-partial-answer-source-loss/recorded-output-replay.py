"""Replay two recorded native model outputs; no model/service/network is called."""
import sys,json,hashlib,importlib.util,subprocess
from pathlib import Path
from datetime import datetime
from icarus_memory import satzantwort, satzpruefung_modell
from icarus_memory.providers import Reply
repo=Path('/Users/sorenkube/Documents/Codex/2026-09-19/github-plugin-github-openai-curated-remote-3/work/memory-activation-20260923')
raw=Path('/Users/sorenkube/Documents/Codex/Kingfisher-Testlaeufe/2026-10-08-native-sentence-probe/independent/answers.json').read_bytes()
report=json.loads(raw)
catalog=json.loads((repo/'docs/evaluations/memory-quality/retrieval-controls/catalog-20261008.json').read_text())
originals={s['id']:s for s in catalog['sources']}
old_path=Path('/private/tmp/kingfisher-satzantwort-before-source-guard.py')
old_path.write_bytes(subprocess.check_output(['git','show','f3794ebb6041c8c1b214c527be2a30ad397debce:sidecar/icarus_memory/satzantwort.py'],cwd=repo))
name='icarus_memory._baseline_satzantwort_source_guard'
spec=importlib.util.spec_from_file_location(name,old_path);before=importlib.util.module_from_spec(spec);sys.modules[name]=before;spec.loader.exec_module(before)
class Replay:
 is_local=True;name='recorded-native-output';model='qwen3.5:4b'
 def __init__(self,row):self.responses=iter([o['reply'] for o in row['model_outputs'][2:]]);self.calls=0
 def complete_json(self,*args,**kwargs):self.calls+=1;return Reply(text=next(self.responses))
rows=[]
for n in (8,11):
 row=report['rows'][n-1];outputs={}
 for label,module in [('before',before),('after',satzantwort)]:
  belege=[]
  for recorded in row['sentence_answer']['belege']:
   matches=[originals[s] for s in row['selected_sources'] if len(originals[s]['text'])==recorded['ref']['end']]
   assert len(matches)==1, 'Only the two frozen sources in each case; unique exact text lengths.'
   source=matches[0]
   belege.append(module.AntwortBeleg(nummer=recorded['nummer'],ref=recorded['ref'],rolle=recorded['rolle'],episode_id=recorded['ref']['episode_id'],titel=source['title'],kopf=source['title'],text=source['text'],zeit=None))
  provider=Replay(row)
  result=module.formulieren(row['q'],belege,provider,jetzt=datetime.fromisoformat(row['sentence_answer']['stichtag']),pruefung=satzpruefung_modell.tor('an',provider))
  outputs[label]={'status':result.status,'surviving_sentences':[s.text for s in result.saetze],'rejected':len(result.verworfen),'reasons':[list(s.gruende) for s in result.verworfen],'fallback_reason':result.grund,'replayed_calls':provider.calls}
 assert outputs['before']['status']=='saetze' and outputs['after']['status']=='zitate'
 assert outputs['before']['surviving_sentences']==[s['text'] for s in row['sentence_answer']['saetze']]
 assert outputs['before']['rejected']==outputs['after']['rejected']==1
 rows.append({'question_number_one_based':n,'question':row['q'],'selected_sources':row['selected_sources'],**outputs})
result={'method':'Offline replay of recorded native qwen3.5:4b outputs with frozen source originals; no new inference, no retrieval rerun. Existing validator behavior reproduced, then only source-loss fallback changes. Original rendering and saved-answer coverage separately tested.','native_raw_sha256':hashlib.sha256(raw).hexdigest(),'before_commit':'f3794ebb6041c8c1b214c527be2a30ad397debce','rows':rows}
Path('/private/tmp/kingfisher-partial-source-replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
