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

for(const scenario of ['hidden-success','hidden-failure','hidden-then-visible-success']) {
  test(`coverage poll discards obsolete ${scenario} and starts a fresh visible read without overlap`,async()=>{
    const previous={coverage:api.memoryCoverage,timeline:api.memoryTimeline};
    const oldWindow=globalThis.window,oldDocument=globalThis.document;
    let poll,visibility;const requests=[];
    globalThis.window={setInterval:fn=>{poll=fn;return 1;},clearInterval:()=>{}};
    globalThis.document={visibilityState:'visible',addEventListener:(_name,fn)=>{visibility=fn;},removeEventListener:()=>{}};
    api.memoryCoverage=signal=>new Promise((resolve,reject)=>requests.push({resolve,reject,signal}));
    api.memoryTimeline=async()=>({basis:'source',items:[],next_cursor:null});
    const d=driver();
    try{
      d.render();d.runEffects();requests[0].resolve(initial);await tick();
      poll();poll();assert.equal(requests.length,2,'one in-flight read');
      globalThis.document.visibilityState='hidden';visibility();poll();
      assert.equal(requests.length,2,'no hidden read');
      if(scenario==='hidden-then-visible-success'){
        globalThis.document.visibilityState='visible';visibility();
        assert.equal(requests.length,2,'old request must settle before replacement');
      }
      if(scenario==='hidden-failure')requests[1].reject(Error('synthetic late failure'));
      else requests[1].resolve({...initial,total_sources:888,automation:{...initial.automation,requested:true,state:'active'}});
      await tick();
      const tree=d.render(),html=renderToStaticMarkup(tree);
      assert.doesNotMatch(html,/888 Nachrichten/,'obsolete counts must not replace the retained source count');
      assert.doesNotMatch(html,/Der Fortschritt konnte gerade nicht aktualisiert/,'hidden failure must not publish');
      assert.ok(button(tree,'Automatisches Sortieren einschalten'),'obsolete automation must not publish');
      assert.equal(requests[1].signal?.aborted,true,'hide aborts the metadata request');
      if(globalThis.document.visibilityState==='hidden'){
        assert.equal(requests.length,2);globalThis.document.visibilityState='visible';visibility();
      }
      assert.equal(requests.length,3,'return immediately refreshes without waiting fifteen seconds');
      requests[2].resolve({...initial,total_sources:12});await tick();
      assert.match(renderToStaticMarkup(d.render()),/12 Nachrichten und Dokumente/);
    }finally{
      d.close();api.memoryCoverage=previous.coverage;api.memoryTimeline=previous.timeline;
      globalThis.window=oldWindow;globalThis.document=oldDocument;delete globalThis.__memoryStatusDriver;
    }
  });
}

for(const actionFailed of [false,true]){
  test(`coverage reread after automation ${actionFailed?'failure':'success'} cannot publish after hiding`,async()=>{
    const previous={coverage:api.memoryCoverage,timeline:api.memoryTimeline,automation:api.setMemoryAutomation};
    const oldWindow=globalThis.window,oldDocument=globalThis.document;let visibility,finish;
    globalThis.window={setInterval:()=>1,clearInterval:()=>{}};
    globalThis.document={visibilityState:'visible',addEventListener:(_name,fn)=>{visibility=fn;},removeEventListener:()=>{}};
    api.memoryCoverage=async()=>initial;
    api.memoryTimeline=async()=>({basis:'source',items:[],next_cursor:null});
    api.setMemoryAutomation=async()=>{if(actionFailed)throw Error('synthetic unconfirmed change');return {...initial.automation,requested:true,state:'active'};};
    const d=driver();
    try{
      d.render();d.runEffects();await tick();
      api.memoryCoverage=()=>new Promise(resolve=>{finish=resolve;});
      button(d.render(),'Automatisches Sortieren einschalten').props.onClick();await tick();
      assert.equal(typeof finish,'function');
      globalThis.document.visibilityState='hidden';visibility();
      finish({...initial,total_sources:888});await tick();
      assert.doesNotMatch(renderToStaticMarkup(d.render()),/888 Nachrichten/);
    }finally{
      d.close();api.memoryCoverage=previous.coverage;api.memoryTimeline=previous.timeline;api.setMemoryAutomation=previous.automation;
      globalThis.window=oldWindow;globalThis.document=oldDocument;delete globalThis.__memoryStatusDriver;
    }
  });
}

test('coverage interval preserves timeline and unmount aborts and discards its pending read',async()=>{
  const previous={coverage:api.memoryCoverage,timeline:api.memoryTimeline};
  const oldWindow=globalThis.window,oldDocument=globalThis.document;let poll,intervalMs,cleared,removed,timelineReads=0;
  const requests=[];
  globalThis.window={setInterval:(fn,ms)=>{poll=fn;intervalMs=ms;return 7;},clearInterval:id=>{cleared=id;}};
  globalThis.document={visibilityState:'visible',addEventListener:()=>{},removeEventListener:name=>{removed=name;}};
  api.memoryCoverage=signal=>new Promise(resolve=>requests.push({resolve,signal}));
  api.memoryTimeline=async()=>{timelineReads++;return {basis:'source',items:[],next_cursor:null};};
  const d=driver();
  try{
    d.render();d.runEffects();requests[0].resolve(initial);await tick();
    assert.equal(intervalMs,15000);poll();poll();assert.equal(requests.length,2);assert.equal(timelineReads,1);
    d.close();assert.equal(cleared,7);assert.equal(removed,'visibilitychange');assert.equal(requests[1].signal.aborted,true);
    requests[1].resolve({...initial,total_sources:888});await tick();poll();
    assert.equal(requests.length,2);assert.doesNotMatch(renderToStaticMarkup(d.render()),/888 Nachrichten/);
  }finally{
    d.close();api.memoryCoverage=previous.coverage;api.memoryTimeline=previous.timeline;
    globalThis.window=oldWindow;globalThis.document=oldDocument;delete globalThis.__memoryStatusDriver;
  }
});
