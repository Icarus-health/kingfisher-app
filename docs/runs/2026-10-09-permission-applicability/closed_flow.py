"""Synthetic answer-generation/verification ONLY; no intake, index or personal data."""
import sys,json,time,hashlib,inspect
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import asdict
REPO=Path(sys.argv[1]); ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(REPO/'sidecar'),str(REPO/'scripts')]
from icarus_memory import satzantwort,satzpruefung
from icarus_memory.local_model_guard import VerifiedLocalProvider
from icarus_memory.satzpruefung_modell import tor
from probe_working_memory_end_to_end import Meter,local_provider
provider=Meter(VerifiedLocalProvider(local_provider('qwen3.5:4b','http://127.0.0.1:11439/v1')))
catalog=json.loads((ROOT/'catalog.json').read_text())
report={'synthetic_only':True,'stage':'answer generation and verification only; no retrieval/intake qualification','catalog_sha256':hashlib.sha256((ROOT/'catalog.json').read_bytes()).hexdigest(),'code':{m.__name__:hashlib.sha256(Path(inspect.getfile(m)).read_bytes()).hexdigest() for m in [satzantwort,satzpruefung]},'cases':[]}
for case in catalog['cases']:
    belege=[satzantwort.AntwortBeleg(n,{},'Quelle',source['id'],source['id'],source['id'],source['text'],None) for n,source in enumerate(case['sources'],1)]
    start=provider.calls;t=time.monotonic()
    result=satzantwort.formulieren(case['question'],belege,provider,jetzt=datetime(2026,10,9,tzinfo=timezone.utc),pruefung=tor('an',provider))
    row={'id':case['id'],'status':result.status,'accepted':[asdict(s) for s in result.saetze],'rejected':[asdict(s) for s in result.verworfen],'reason':result.grund,'seconds':round(time.monotonic()-t,3),'model_events':provider.events[start:]}
    report['cases'].append(row);(ROOT/'answers.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n'); print(case['id'],result.status,flush=True)
