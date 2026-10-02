import json, subprocess, tempfile, time, statistics
from pathlib import Path
from icarus_memory.providers import OpenAICompatible
from memory_probe_support import RecordingProvider
from memory_probe_fixtures import build_fixture,business_clock,case_hash
from probe_everyday_memory import cases

import argparse
parser=argparse.ArgumentParser(description='Synthetic alternating transport comparison; installed local model only.')
parser.add_argument('--output',required=True)
args=parser.parse_args()
REPO=Path(__file__).resolve().parents[5]
OUT=Path(args.output)

class Legacy(OpenAICompatible): complete_json=None
report=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
 model='qwen3.5:4b',status='started',semantic_qualification=False,content_retries=0,
 limitations='Frozen prepared-source development cases, one observation per arm per case, alternating order, shared model cache. Not a cold-start, isolated hardware or semantic qualification.',
 manifest=[dict(case_id=c['id'],sha256=case_hash(c)) for c in cases('meaning')],results=[])
with OUT.open('x') as f, tempfile.TemporaryDirectory(prefix='kf-paired-') as tmp:
 def save():
  f.seek(0);json.dump(report,f,ensure_ascii=False,indent=2);f.truncate();f.flush()
 save()
 try:
  for i,c in enumerate(cases('meaning')):
   for arm in (('legacy','bounded') if i%2==0 else ('bounded','legacy')):
    p=(Legacy if arm=='legacy' else OpenAICompatible)(report['model'],api_key='synthetic',base_url='http://127.0.0.1:11434/v1')
    rec=RecordingProvider(p);fx=build_fixture(c,Path(tmp)/(c['id']+arm),rec)
    try:
     with business_clock(c):
      t=time.monotonic();turn=fx.agent.answer_memory(c['question']);elapsed=time.monotonic()-t
     report['results'].append(dict(case_id=c['id'],arm=arm,seconds=elapsed,contract=turn.context['answer_contract'],reply=turn.reply,calls=rec.calls,
       original=c['sources'][0]['text'],side_effect_free=not(turn.used_tools or turn.approvals or turn.memory_candidate_drafts)))
     save();print(c['id'],arm,round(elapsed,3),turn.context['answer_contract']['status'],flush=True)
    finally:fx.close()
  report['status']='completed'
 except BaseException as e:
  report.update(status='failed',error_type=type(e).__name__);raise
 finally:save()
for arm in ('legacy','bounded'):
 rows=[r for r in report['results'] if r['arm']==arm and r['calls']]
 print(arm, 'median',statistics.median(r['seconds'] for r in rows),'max',max(r['seconds'] for r in rows))
