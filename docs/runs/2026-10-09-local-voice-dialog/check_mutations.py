"""Exercise the real controller on copied source, without browser/native/model I/O."""
from pathlib import Path
import json, shutil, subprocess, sys
root=Path(sys.argv[1]).resolve()
output=Path(sys.argv[2]).resolve(); output.mkdir(parents=True,exist_ok=True)
base=(root/'app/kingfisher/src/nativeVoice.ts').read_text(); results=[]
mutations={
    'old_callbacks':('if(event.id!==id || !mode)return;','if(!mode)return;'),
    'hidden_callbacks':("if(!alive || !options.active() || !value || typeof value!=='object')return;","if(!alive || !value || typeof value!=='object')return;"),
    'source_freshness':('if(voiceAnswerKey(fresh)!==key || voiceAnswerKey(current())!==key)','if(false)'),
    'uncertainty':("${nebensatz(s) ? ` (${nebensatz(s)})` : ''}",''),
}
for name,(before,after) in mutations.items():
    assert before in base,name
    folder=output/name;folder.mkdir(exist_ok=True)
    shutil.copytree(root/'app/kingfisher/src',folder/'src',dirs_exist_ok=True)
    (folder/'tests').mkdir(exist_ok=True)
    shutil.copy2(root/'app/kingfisher/tests/native-voice.test.mjs',folder/'tests/native-voice.test.mjs')
    (folder/'src/nativeVoice.ts').write_text(base.replace(before,after,1))
    (folder/'package.json').write_text('{"type":"module"}')
    run=subprocess.run(['node','--experimental-strip-types','--test','tests/native-voice.test.mjs'],cwd=folder,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (folder/'test.log').write_text(run.stdout)
    failures=[line for line in run.stdout.splitlines() if line.startswith('not ok')]
    assert run.returncode!=0 and failures,(name,run.stdout)
    results.append({'mutation':name,'exit':run.returncode,'failures':failures})
(output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results))
