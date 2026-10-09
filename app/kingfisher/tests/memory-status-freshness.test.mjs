import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

// Drive the real component's existing handlers with deterministic hook storage.
// This is a component boundary test, not a browser/window or React-runtime test.
const server=await createServer({root:fileURLToPath(new URL('..',import.meta.url)),
  plugins:[{name:'memory-status-hook-driver',enforce:'pre',
    resolveId(id){if(id==='virtual:memory-status-hooks')return '\0'+id;},
    load(id){if(id==='\0virtual:memory-status-hooks')return `
      export const useState=(...a)=>globalThis.__memoryStatusDriver.state(...a);
      export const useRef=(...a)=>globalThis.__memoryStatusDriver.ref(...a);
      export const useEffect=(...a)=>globalThis.__memoryStatusDriver.effect(...a);`;},
    transform(code,id){if(id.endsWith('/src/MemoryStatus.tsx'))return code.replace('from "react"','from "virtual:memory-status-hooks"');},
  }],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {MemoryStatus}=await server.ssrLoadModule('/src/MemoryStatus.tsx');
const {api}=await server.ssrLoadModule('/src/api.ts');
const initial={total_sources:10,sampled_sources:10,truncated:false,counts:{completed:3,pending:6,running:0,partial:0,failed:1,excluded:0},
  scope:'Synthetic',detail:'Synthetic',automation:{state:'paused',requested:false,pending:7,model:null},
  working_memory_progress:{total:10,done:3,remaining:7,retry:1,skipped:0,estimate_seconds:1200}};
function driver(){
  const states=[],refs=[],effects=[],pending=[];let s=0,r=0,e=0;
  const d={state(value){const i=s++;if(!(i in states))states[i]=value;return [states[i],next=>{states[i]=typeof next==='function'?next(states[i]):next;}];},
    ref(value){const i=r++;return refs[i]??=( {current:value});},
    effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){
      effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>{effects[i].cleanup=fn();});}},
    render(){s=r=e=0;globalThis.__memoryStatusDriver=d;return MemoryStatus();},
    runEffects(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(x=>x.cleanup?.());}};
  return d;
}
const tick=async()=>{for(let i=0;i<3;i++)await new Promise(setImmediate);};
function buttons(node,result=[]){if(!node||typeof node!=='object')return result;if(node.type==='button')result.push(node);
  for(const child of [node.props?.children].flat(10))buttons(child,result);return result;}
const button=(tree,label)=>buttons(tree).find(x=>[x.props.children].flat(5).join('')===label);

test('failed refresh after enabling marks the retained counts stale and disables stale toggles; retry restores them',async()=>{
  const previous={coverage:api.memoryCoverage,automation:api.setMemoryAutomation,timeline:api.memoryTimeline};
  const oldWindow=globalThis.window,oldDocument=globalThis.document;
  globalThis.window={setInterval:()=>1,clearInterval:()=>{}};
  globalThis.document={visibilityState:'visible',addEventListener:()=>{},removeEventListener:()=>{}};
  let fail=false;
  api.memoryCoverage=async()=>{if(fail)throw Error('synthetic unavailable');return initial;};
  api.memoryTimeline=async()=>({basis:'source',items:[],next_cursor:null});
  api.setMemoryAutomation=async()=>({state:'active',requested:true,pending:7,model:null});
  const d=driver();
  try{
    d.render();d.runEffects();await tick();
    let tree=d.render();const on=button(tree,'Automatisches Sortieren einschalten');assert.ok(on&&!on.props.disabled);
    fail=true;on.props.onClick();await tick();tree=d.render();
    let html=renderToStaticMarkup(tree);
    assert.match(html,/letzten bekannten Stand/);
    assert.doesNotMatch(html,/Noch etwa|fertig durchgesehen|versucht es von selbst|7 Quellen warten noch darauf/);
    assert.equal(button(tree,'Automatisches Sortieren pausieren').props.disabled,true);
    fail=false;button(tree,'Aktualisieren').props.onClick();d.render();d.runEffects();await tick();tree=d.render();
    html=renderToStaticMarkup(tree);
    assert.doesNotMatch(html,/letzten bekannten Stand|aktuellen Automatikstand/);
    assert.equal(button(tree,'Automatisches Sortieren einschalten').props.disabled,false);
  }finally{d.close();api.memoryCoverage=previous.coverage;api.setMemoryAutomation=previous.automation;api.memoryTimeline=previous.timeline;
    globalThis.window=oldWindow;globalThis.document=oldDocument;delete globalThis.__memoryStatusDriver;}
});
