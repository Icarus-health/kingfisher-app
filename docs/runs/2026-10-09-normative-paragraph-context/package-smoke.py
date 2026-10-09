import hashlib,json,os
from pathlib import Path
from icarus_memory import satzantwort as sa
expected=json.loads(Path('/tmp/expected.json').read_text())
assert os.environ['KINGFISHER_FASSUNG']==expected['version']
base=Path(sa.__file__).parent.parent
for name,digest in expected['python_files'].items():assert hashlib.sha256((base/name).read_bytes()).hexdigest()==digest,name
for name,digest in expected['ui_files'].items():assert hashlib.sha256((Path('/opt/kingfisher/ui')/name).read_bytes()).hexdigest()==digest,name
print(json.dumps({'version':expected['version'],'python_sources_verified':len(expected['python_files']),'ui_files_verified':len(expected['ui_files'])}))

from datetime import datetime,timezone
from dataclasses import replace
from icarus_memory.providers import Reply
class Selector:
 is_local=True;name=model='synthetic-selector'
 def __init__(self,output):self.output=output
 def complete_json(self,messages,**kwargs):return Reply(text=json.dumps(self.output))
now=datetime(2026,10,9,tzinfo=timezone.utc)
rule='Die Klappe darf geöffnet werden.'
qualifier='Dies gilt ausschließlich nach schriftlicher Freigabe.'
body=rule+' '+qualifier
other='Der Schalter darf umgelegt werden.'
def evidence(text,**kwargs):return sa.AntwortBeleg(1,{},'conditional','synthetic-1','Regel','',text,None,**kwargs)
def answer(text,belege=None):
 return sa.formulieren('Was gilt?',belege or [evidence(body)],Selector({'status':'antwort','saetze':[{'text':text,'belege':[b.nummer for b in belege] if belege else [1]}]}),jetzt=now)
assert answer(rule).status=='zitate'
assert answer(body).status=='saetze'
assert answer(qualifier+' '+rule).status=='zitate'
belege=[evidence(body),replace(evidence(other),nummer=2,episode_id='synthetic-2')]
assert answer(rule+' '+other+' '+qualifier+' '+body,belege).status=='zitate'
for source in ['Entwurf\n\n'+rule+' '+qualifier,rule+' Dies darf ausschließlich nach schriftlicher Freigabe erfolgen.']:
 result=sa.formulieren('Was gilt?',[evidence(source)],Selector({'status':'antwort','originalstellen':[{'beleg':1,'satz':1}]}),jetzt=now)
 assert result.status=='saetze' and [s.text for s in result.saetze]==[source]
assert answer('Der Bericht liegt im Tresor.',[evidence('Der Bericht liegt im Tresor. Der Schlüssel steckt in der Tasche.')]).status=='saetze'
assert answer(other,[evidence(other)]).status=='saetze'
assert answer(rule,[evidence(rule+' […]',pruef_text=body,gekuerzt=True)]).status=='zitate'
print(json.dumps({'complete_rule_context':True,'header_and_normative_companion_atomic':True,'reversed_and_repeated_fragment_rejected':True,'ordinary_fact_and_single_rule_positive':True,'hidden_context_rejected':True,'network':'none','private_sources_used':False,'real_model_test':False}))
