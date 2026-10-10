import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

const server = await createServer({root:fileURLToPath(new URL('..',import.meta.url)),
  plugins:[{name:'project-overview-hooks',enforce:'pre',
    resolveId(id){if(id==='virtual:project-hooks')return '\0'+id;},
    load(id){if(id==='\0virtual:project-hooks')return `
      export const useState=(...a)=>globalThis.__projectDriver.state(...a);
      export const useEffect=(...a)=>globalThis.__projectDriver.effect(...a);`;},
    transform(code,id){if(id.endsWith('/src/ProjectOverview.tsx'))return code.replace(/from (["'])react\1/,'from "virtual:project-hooks"');}
  }],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {api}=await server.ssrLoadModule('/src/api.ts');
const tick=async()=>{for(let i=0;i<3;i++)await new Promise(setImmediate);};
const task=(id,title,due=null)=>({id,title,due,wartet_auf:null,overdue:false});
const summary=(project_id='p')=>({project_id,as_of:'2030-01-02T12:00:00+00:00',
  counts:{mine:206,waiting:4,done:2,dropped:1,overdue:1,undated:205},
  next_tasks:[task('t','Angebot prüfen')],waiting_tasks:[{...task('w','Antwort erhalten'),wartet_auf:'Anna',wartet_tage:3}]});
function nodes(node,type,out=[]){if(!node||typeof node!=='object')return out;
  if(node.type===type)out.push(node);
  for(const child of [node.props?.children].flat(10))nodes(child,type,out);return out;}
function button(tree,text){return nodes(tree,'button').find(n=>renderToStaticMarkup(n).includes(text));}
async function driver(props){
  assert.ok(existsSync(new URL('../src/ProjectOverview.tsx',import.meta.url)),'projects need an actionable overview');
  const {ProjectOverview}=await server.ssrLoadModule('/src/ProjectOverview.tsx');
  const states=[],effects=[],pending=[];let s=0,e=0;
  const d={props,state(v){const i=s++;if(!(i in states))states[i]=typeof v==='function'?v():v;
      return [states[i],next=>{states[i]=typeof next==='function'?next(states[i]):next;}];},
    effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){
      effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>{effects[i].cleanup=fn();});}},
    render(){s=e=0;globalThis.__projectDriver=d;return ProjectOverview(d.props);},
    runEffects(){pending.splice(0).forEach(fn=>fn());},close(){effects.forEach(x=>x.cleanup?.());delete globalThis.__projectDriver;}};
  return d;
}
async function withApi(run,fetch=async()=>summary()){
  const old=api.projectOverview;api.projectOverview=fetch;
  try{await run();}finally{api.projectOverview=old;}
}
const props=()=>({projectId:'p',revision:0,onView(){},onTask(){}});

test('full counts, missing dates, waiting names and completed counts stay explicit',async()=>withApi(async()=>{
  const d=await driver(props());try{d.render();d.runEffects();await tick();
    const html=renderToStaticMarkup(d.render());assert.match(html,/206/);assert.match(html,/205 ohne Termin/);
    assert.match(html,/Anna/);assert.match(html,/<strong>2<\/strong>Erledigte Aufgaben/);assert.match(html,/1 verworfen/);
    assert.match(html,/Ohne Termin/);assert.doesNotMatch(html,/100%|Heute|Projektfortschritt/);
  }finally{d.close();}
}));

test('one click opens the correct task or the entire matching view',async()=>withApi(async()=>{
  let opened,view;const d=await driver({...props(),onTask:(...args)=>opened=args,onView:value=>view=value});
  try{d.render();d.runEffects();await tick();const tree=d.render();
    button(tree,'Angebot prüfen').props.onClick();assert.deepEqual(opened,['t','mine']);
    button(tree,'Antwort erhalten').props.onClick();assert.deepEqual(opened,['w','waiting']);
    button(tree,'Warte auf andere').props.onClick();assert.equal(view,'waiting');
  }finally{d.close();}
}));

test('late responses and errors cannot show the previous project or overwrite a newer result',async()=>{
  const pending=[];await withApi(async()=>{const d=await driver(props());
    try{d.render();d.runEffects();d.props={...props(),projectId:'q'};
      assert.doesNotMatch(renderToStaticMarkup(d.render()),/Angebot prüfen/);d.runEffects();
      pending[1].resolve({...summary('q'),next_tasks:[task('qtask','Neues Projekt')]});await tick();
      pending[0].resolve(summary('p'));await tick();assert.match(renderToStaticMarkup(d.render()),/Neues Projekt/);
      d.props={...d.props,revision:1};d.render();d.runEffects();pending[2].reject(Error('offline'));await tick();
      assert.match(renderToStaticMarkup(d.render()),/nicht erreichbar/);
      assert.doesNotMatch(renderToStaticMarkup(d.render()),/Neues Projekt/);
    }finally{d.close();}
  },()=>new Promise((resolve,reject)=>pending.push({resolve,reject})));
});

test('no project selection loads nothing; empty project never implies complete',async()=>{
  let calls=0;await withApi(async()=>{const d=await driver({...props(),projectId:''});
    try{d.render();d.runEffects();await tick();assert.equal(calls,0);
      d.props=props();d.render();d.runEffects();await tick();const html=renderToStaticMarkup(d.render());
      assert.match(html,/Keine eigenen offenen Aufgaben/);assert.match(html,/Keine wartenden Aufgaben/);
      assert.doesNotMatch(html,/100%|Projekt abgeschlossen/);
    }finally{d.close();}
  },async()=>{calls++;return {...summary(),counts:{mine:0,waiting:0,done:0,dropped:0,overdue:0,undated:0},next_tasks:[],waiting_tasks:[]};});
});

test('refresh uses new data and does not write any task',async()=>{
  let calls=0;await withApi(async()=>{const d=await driver(props());
    try{d.render();d.runEffects();await tick();button(d.render(),'Überblick aktualisieren').props.onClick();
      d.render();d.runEffects();await tick();assert.equal(calls,2);
    }finally{d.close();}
  },async()=>{calls++;return summary();});
});
