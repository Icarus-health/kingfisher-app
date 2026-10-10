import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

// Exercise the real component handlers, not a browser or React-runtime test.
const server = await createServer({root:fileURLToPath(new URL('..', import.meta.url)),
  plugins:[{name:'category-correction-hook-driver', enforce:'pre',
    resolveId(id){if(id==='virtual:category-hooks')return '\0'+id;},
    load(id){if(id==='\0virtual:category-hooks')return `
      export const useState=(...a)=>globalThis.__categoryDriver.state(...a);
      export const useRef=(...a)=>globalThis.__categoryDriver.ref(...a);
      export const useEffect=(...a)=>globalThis.__categoryDriver.effect(...a);`;},
    transform(code,id){if(['/src/CategoryCorrection.tsx','/src/SourceCategories.tsx','/src/MemoryAreas.tsx'].some(path=>id.endsWith(path)))
      return code.replace(/from (["'])react\1/,'from "virtual:category-hooks"');},
  }],server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {api, ApiError} = await server.ssrLoadModule('/src/api.ts');
const annotation = (id='one', categories=[]) => ({episode_id:id,status:'pending',categories,
  entities:[],correction:null,automatic:true,revision:'a'.repeat(64)});
const taxonomy = {version:1,items:[{id:'work',label:'Arbeit / Projekte'},
  {id:'information',label:'Information / Newsletter'}]};
const tick = async()=>{for(let i=0;i<3;i++)await new Promise(setImmediate);};
function nodes(node,type,out=[]){if(!node||typeof node!=='object')return out;
  if(node.type===type)out.push(node);
  for(const child of [node.props?.children].flat(10))nodes(child,type,out);
  return out;}
function button(tree,label){return nodes(tree,'button').find(x=>[x.props.children].flat(5).join('')===label);}
async function driver(props, componentName='CategoryCorrection'){
  assert.ok(existsSync(new URL(`../src/${componentName}.tsx`,import.meta.url)),
    'the source overview needs a direct, explicit category feedback control');
  const Component = (await server.ssrLoadModule(`/src/${componentName}.tsx`))[componentName];
  const states=[],refs=[],effects=[],pending=[];let s=0,r=0,e=0;
  const d={props,
    state(value){const i=s++;if(!(i in states))states[i]=typeof value==='function'?value():value;
      return [states[i],next=>{states[i]=typeof next==='function'?next(states[i]):next;}];},
    ref(value){const i=r++;return refs[i]??={current:value};},
    effect(fn,deps){const i=e++;if(!effects[i]||deps.some((v,j)=>v!==effects[i].deps[j])){
      effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>{effects[i].cleanup=fn();});}},
    render(){s=r=e=0;globalThis.__categoryDriver=d;return Component(d.props);},
    runEffects(){pending.splice(0).forEach(fn=>fn());},
    close(){effects.forEach(x=>x.cleanup?.());delete globalThis.__categoryDriver;},
  };
  return d;
}
async function withApi(run, overrides={}){
  const old={sourceCategories:api.sourceCategories,categoryTaxonomy:api.categoryTaxonomy,
    correctSourceCategories:api.correctSourceCategories};
  Object.assign(api,{sourceCategories:async id=>annotation(id),categoryTaxonomy:async()=>taxonomy,
    correctSourceCategories:async()=>{throw Error('unexpected write');}},overrides);
  try{await run();}finally{Object.assign(api,old);}
}
async function open(d){let tree=d.render();d.runEffects();tree=d.render();
  button(tree,'Zuordnung ändern').props.onClick();await tick();return d.render();}

test('collapsed feedback loads nothing; selecting a topic alone never writes', async()=>{
  let reads=0,writes=0;
  await withApi(async()=>{const d=await driver({id:'one',title:'Newsletter'});
    try{d.render();d.runEffects();await tick();assert.equal(reads,0);
      const tree=await open(d);assert.equal(reads,1);
      nodes(tree,'input').find(x=>x.props.value==='information').props.onChange({target:{checked:true}});
      assert.equal(writes,0);button(d.render(),'Abbrechen').props.onClick();assert.equal(writes,0);
    }finally{d.close();}}, {sourceCategories:async id=>{reads++;return annotation(id);},
      correctSourceCategories:async()=>{writes++;return annotation();}});
});

test('explicit save carries the reviewed revision and reports user categories', async()=>{
  let sent,saved;
  await withApi(async()=>{const d=await driver({id:'one',title:'Newsletter',onSaved:value=>{saved=value;}});
    try{const tree=await open(d);
      nodes(tree,'input').find(x=>x.props.value==='information').props.onChange({target:{checked:true}});
      nodes(d.render(),'form')[0].props.onSubmit({preventDefault(){}});await tick();
      assert.deepEqual(sent,['one',['information'],'a'.repeat(64)]);
      assert.equal(saved.categories[0].origin,'user');
      assert.match(renderToStaticMarkup(d.render()),/Zuordnung ändern/);
    }finally{d.close();}}, {correctSourceCategories:async(...args)=>{sent=args;
      return {...annotation(),categories:[{id:'information',label:'Information / Newsletter',origin:'user'}]};}});
});

test('changed source or feedback keeps selection, blocks save and offers fresh review', async()=>{
  let saved=0;
  await withApi(async()=>{const d=await driver({id:'one',title:'Newsletter',onSaved:()=>saved++});
    try{const tree=await open(d);
      nodes(tree,'input').find(x=>x.props.value==='information').props.onChange({target:{checked:true}});
      nodes(d.render(),'form')[0].props.onSubmit({preventDefault(){}});await tick();
      const current=d.render();assert.equal(saved,0);
      assert.equal(nodes(current,'input').find(x=>x.props.value==='information').props.checked,true);
      assert.equal(button(current,'Zuordnung speichern').props.disabled,true);
      assert.match(renderToStaticMarkup(current),/geändert/);
      assert.ok(button(current,'Aktuellen Stand prüfen'));
    }finally{d.close();}}, {correctSourceCategories:async()=>{throw new ApiError(409);}});
});

test('excluded or older service without a revision cannot be saved', async()=>{
  for(const data of [{...annotation(),status:'excluded',revision:null}, {...annotation(),revision:undefined}]){
    await withApi(async()=>{const d=await driver({id:'one',title:'Newsletter'});
      try{const tree=await open(d);assert.equal(nodes(tree,'form').length,0);
        assert.equal(button(tree,'Zuordnung speichern'),undefined);
      }finally{d.close();}}, {sourceCategories:async()=>data});
  }
});

test('cancelled or previous source read never opens a stale editor', async()=>{
  let finish;
  await withApi(async()=>{const d=await driver({id:'one',title:'First'});
    try{d.render();d.runEffects();button(d.render(),'Zuordnung ändern').props.onClick();
      button(d.render(),'Abbrechen').props.onClick();
      finish(annotation());await tick();assert.equal(nodes(d.render(),'form').length,0);
      d.props={id:'two',title:'Second'};d.render();d.runEffects();await tick();
      assert.equal(nodes(d.render(),'form').length,0);
    }finally{d.close();}}, {sourceCategories:()=>new Promise(resolve=>{finish=resolve;})});
});

test('a failed load remains visibly unsaved and can be retried', async()=>{
  await withApi(async()=>{const d=await driver({id:'one',title:'Newsletter'});
    try{const tree=await open(d);assert.equal(nodes(tree,'form').length,0);
      assert.match(renderToStaticMarkup(tree),/nicht geladen/);
      assert.ok(button(tree,'Erneut versuchen'));
    }finally{d.close();}}, {categoryTaxonomy:async()=>{throw Error('offline');}});
});

test('the existing source editor cannot silently adopt a new revision while editing', async()=>{
  let poll,latest=annotation(),sent;
  const oldWindow=globalThis.window,oldDocument=globalThis.document;
  globalThis.window={setInterval:fn=>{poll=fn;return 1;},clearInterval:()=>{}};
  globalThis.document={hidden:false};
  try{await withApi(async()=>{const d=await driver({id:'one'},'SourceCategories');
    try{d.render();d.runEffects();await tick();
      button(d.render(),'Themen korrigieren').props.onClick();
      latest={...annotation(),revision:'b'.repeat(64)};
      await poll();
      nodes(d.render(),'form')[0].props.onSubmit({preventDefault(){}});await tick();
      assert.equal(sent[2],'a'.repeat(64),'editing must retain the version originally reviewed');
      assert.match(renderToStaticMarkup(d.render()),/geändert/);
    }finally{d.close();}}, {sourceCategories:async()=>latest,
      correctSourceCategories:async(...args)=>{sent=args;throw new ApiError(409);}});
  }finally{globalThis.window=oldWindow;globalThis.document=oldDocument;}
});

test('save completed after navigation refreshes the newly selected area without the old editor', async()=>{
  const oldWindow=globalThis.window,oldFetch=globalThis.fetch,oldRead=api.memoryAreas;
  const target=new EventTarget();
  Object.assign(target,{location:{search:'?area=work'},history:{replaceState(_state,_title,url){
    target.location.search=new URL(url,'http://synthetic.local').search;}}});
  globalThis.window=target;
  const reads=[];let finish;
  api.memoryAreas=async(_limit,_cursor,area)=>{reads.push(area);return {area,areas:[],sources:[],
    taxonomy_version:1,scanned_count:0,counts_scope:'page',next_cursor:null,truncated:false};};
  globalThis.fetch=()=>new Promise(resolve=>{finish=()=>resolve(new Response(JSON.stringify(annotation()),{status:200}));});
  const d=await driver({},'MemoryAreas');
  try{
    d.render();d.runEffects();await tick();d.render();d.runEffects();
    const write=api.correctSourceCategories('one',['information'],'a'.repeat(64));
    button(d.render(),'Finanzen & Verträge').props.onClick();
    d.render();d.runEffects();await tick();d.render();d.runEffects();
    assert.deepEqual(reads,['work','finance']);
    finish();await write;await tick();
    assert.deepEqual(reads,['work','finance','finance'],
      'a late committed correction refreshes the active view, not the old source view');
  }finally{d.close();api.memoryAreas=oldRead;globalThis.window=oldWindow;globalThis.fetch=oldFetch;}
});

test('failed correction emits no successful-change notification', async()=>{
  const oldWindow=globalThis.window,oldFetch=globalThis.fetch;
  let events=0;
  globalThis.window={dispatchEvent:()=>{events++;}};
  globalThis.fetch=async()=>new Response(JSON.stringify({detail:'conflict'}),{status:409});
  try{await assert.rejects(api.correctSourceCategories('one',['information'],'a'.repeat(64)),error=>error.status===409);
    assert.equal(events,0);
  }finally{globalThis.window=oldWindow;globalThis.fetch=oldFetch;}
});
