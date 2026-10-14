import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';

// Exercise the page with its real rendering and action handlers; only metadata
// reads and hook storage are deterministic. No browser, service or model runs.
const server = await createServer({cacheDir:`/private/tmp/kingfisher-ui-test-cache-${process.pid}-memory-status-overview.test`,root:fileURLToPath(new URL('..', import.meta.url)),
  plugins:[{name:'memory-overview-hook-driver', enforce:'pre',
    resolveId(id){if(id==='virtual:memory-overview-hooks')return '\0'+id;},
    load(id){if(id==='\0virtual:memory-overview-hooks')return `
      export const useState=(...a)=>globalThis.__memoryOverviewDriver.state(...a);
      export const useRef=(...a)=>globalThis.__memoryOverviewDriver.ref(...a);
      export const useEffect=(...a)=>globalThis.__memoryOverviewDriver.effect(...a);`;},
    transform(code,id){if(id.endsWith('/src/MemoryStatus.tsx'))return code.replace('from "react"','from "virtual:memory-overview-hooks"');},
  }], server:{middlewareMode:true, watch:null, ws:false, hmr:false}, appType:'custom'});
after(()=>server.close());
const {MemoryStatus} = await server.ssrLoadModule('/src/MemoryStatus.tsx');
const {api} = await server.ssrLoadModule('/src/api.ts');
const pause = 'Pausiert. Kingfisher lernt weiter, wenn du „Weiter“ wählst.';
const base = {
  total_sources:123, sampled_sources:10, truncated:true, truncated_sources:0,
  counts:{completed:2, pending:5, running:0, partial:1, failed:1, excluded:1},
  scope:'Synthetic source scope', detail:'Synthetic details',
  automation:{state:'unverified', requested:true, pending:9, model:null, execution_pause_reason:pause},
  working_memory_progress:{total:15, done:4, skipped:2, retry:1, remaining:9, estimate_seconds:1200},
  semantic_index:{status:'partial', total:40, indexed:0, pending:40, failed:0, source_pending:9,
    model_key:null, identity_checked_at:null, updated_at:null, pause_reason:pause},
};
function driver(){
  const states=[], refs=[], effects=[], pending=[];let s=0,r=0,e=0;
  const d={state(value){const i=s++;if(!(i in states))states[i]=value;return [states[i],next=>{states[i]=typeof next==='function'?next(states[i]):next;}];},
    ref(value){const i=r++;return refs[i]??={current:value};},
    effect(fn,deps){const i=e++;if(!effects[i]||deps.some((value,j)=>value!==effects[i].deps[j])){
      effects[i]?.cleanup?.();effects[i]={deps};pending.push(()=>{effects[i].cleanup=fn();});}},
    render(){s=r=e=0;globalThis.__memoryOverviewDriver=d;return MemoryStatus();},
    runEffects(){pending.splice(0).forEach(fn=>fn());}, close(){effects.forEach(x=>x.cleanup?.());}};
  return d;
}
const tick=async()=>{for(let i=0;i<3;i++)await new Promise(setImmediate);};
function nodes(node,match,result=[]){if(!node||typeof node!=='object')return result;
  if(match(node))result.push(node);
  for(const child of [node.props?.children].flat(10))nodes(child,match,result);return result;
}
const textOf=node=>[node.props.children].flat(5).join('');
const button=(tree,label)=>nodes(tree,node=>node.type==='button').find(node=>textOf(node)===label);
function overview(html){const match=html.match(/<section[^>]*aria-label="Gedächtnis im Überblick"[^>]*>([\s\S]*?)<\/section>/);
  assert.ok(match,'a concise memory overview must be present');return match[1];}
function stage(html,label){const match=html.match(new RegExp(`<article[^>]*aria-label="${label}"[^>]*>([\\s\\S]*?)<\\/article>`));
  assert.ok(match,`${label} must be a distinct stage`);return match[1];}
async function page(coverage,run){
  const previous={coverage:api.memoryCoverage,timeline:api.memoryTimeline,automation:api.setMemoryAutomation,background:api.hintergrundPausieren};
  const oldWindow=globalThis.window,oldDocument=globalThis.document;let fail=false;
  globalThis.window={setInterval:()=>1,clearInterval:()=>{}};
  globalThis.document={visibilityState:'visible',addEventListener:()=>{},removeEventListener:()=>{}};
  api.memoryCoverage=async()=>{if(fail)throw Error('synthetic metadata failure');return coverage;};
  api.memoryTimeline=async()=>({basis:'source',items:[],next_cursor:null});
  const mutations=[];
  api.setMemoryAutomation=async enabled=>{mutations.push(['automation',enabled]);return {...coverage.automation,requested:enabled};};
  api.hintergrundPausieren=async paused=>{mutations.push(['background',paused]);};
  const d=driver();
  try{d.render();d.runEffects();await tick();await run({d,mutations,failRefresh:()=>{fail=true;}});}
  finally{d.close();api.memoryCoverage=previous.coverage;api.memoryTimeline=previous.timeline;
    api.setMemoryAutomation=previous.automation;api.hintergrundPausieren=previous.background;
    globalThis.window=oldWindow;globalThis.document=oldDocument;delete globalThis.__memoryOverviewDriver;}
}

test('overview preserves source totals, sorted source counts and semantic sections as separate units',async()=>{
  await page(base,async({d,mutations})=>{
    const html=renderToStaticMarkup(d.render()),summary=overview(html);
    assert.match(stage(summary,'Aufnahme'),/123 Nachrichten und Dokumente/);
    assert.match(stage(summary,'Sortieren'),/4 von 15 Quellen sortiert/);
    assert.match(stage(summary,'Bedeutungssuche'),/0 von 40 Abschnitten/);
    assert.doesNotMatch(summary,/123.*vollständig|2 von 10 Quellen sortiert|0 von 40 Quellen/);
    assert.ok(html.indexOf('Gedächtnis im Überblick')<html.indexOf('Deine Informationsquellen'));
    const setup=nodes(d.render(),node=>node.type==='details'&&node.props.className==='memory-status-sources')[0];
    assert.ok(setup&&!setup.props.open,'bulky setup stays accessible in collapsed details');
    assert.deepEqual(mutations,[],'rendering metadata never starts or resumes processing');
  });
});

test('requested sorting with a global pause explains waiting and points to the existing settings control',async()=>{
  await page(base,async({d,mutations})=>{
    const tree=d.render(),summary=overview(renderToStaticMarkup(tree));
    assert.match(stage(summary,'Sortieren'),/eingeschaltet.*wartet/);
    assert.match(summary,/Pausiert.*Kingfisher lernt weiter/);
    assert.doesNotMatch(summary,/Noch etwa|wird im Hintergrund vorbereitet/);
    const link=nodes(tree,node=>node.type==='a'&&node.props.href==='/settings#technik-hintergrund')[0];
    assert.ok(link,'waiting state must link to the existing global processing settings');
    assert.match(renderToStaticMarkup(tree),/Ältere Mails einlesen.*Verarbeitung fortsetzen/);
    const off=button(tree,'Sortierautomatik ausschalten');assert.ok(off&&!off.props.disabled);
    off.props.onClick();await tick();
    assert.deepEqual(mutations,[['automation',false]],'the toggle only withdraws requested sorting, never resumes global processing');
  });
});

test('failed coverage refresh makes every retained stage unconfirmed and disables stale automation actions',async()=>{
  await page({...base,automation:{...base.automation,state:'active',execution_pause_reason:null},
    semantic_index:{...base.semantic_index,status:'indexed',indexed:40,pending:0,source_pending:0,pause_reason:null}},async({d,failRefresh})=>{
    failRefresh();button(d.render(),'Aktualisieren').props.onClick();d.render();d.runEffects();await tick();
    const tree=d.render(),summary=overview(renderToStaticMarkup(tree));
    for(const label of ['Aufnahme','Sortieren','Bedeutungssuche'])assert.match(stage(summary,label),/Letzter bekannter Stand/);
    assert.doesNotMatch(summary,/ist vorbereitet|Automatik läuft|Noch etwa/);
    assert.equal(button(tree,'Automatisches Sortieren pausieren').props.disabled,true);
    assert.doesNotMatch(summary,/<a[^>]*technik-hintergrund/,'obsolete pause state cannot suggest a current resume action');
  });
});

test('unknown semantic counts stay unknown; prepared sections with source backlog never imply complete memory',async()=>{
  await page({...base,semantic_index:{...base.semantic_index,status:'unavailable',total:null,indexed:null,pending:null,failed:null,source_pending:null,pause_reason:null}},async({d})=>{
    const semantic=stage(overview(renderToStaticMarkup(d.render())),'Bedeutungssuche');
    assert.match(semantic,/Abschnittszahl noch nicht verfügbar/);assert.match(semantic,/Nicht bereit/);
    assert.doesNotMatch(semantic,/0 von|vollständig vorbereitet/);
  });
  await page({...base,semantic_index:{...base.semantic_index,status:'indexed',indexed:40,pending:0,source_pending:9,pause_reason:null}},async({d})=>{
    const semantic=stage(overview(renderToStaticMarkup(d.render())),'Bedeutungssuche');
    assert.match(semantic,/40 von 40 Abschnitten/);assert.match(semantic,/Weitere Quellen.*sortiert/);
    assert.doesNotMatch(semantic,/vollständig vorbereitet|Alle Quellen/);
  });
});

test('semantic failures and disabled search never announce readiness, including fully counted indices',async()=>{
  for(const status of ['partial','disabled'])await page({...base,
    semantic_index:{...base.semantic_index,status,indexed:40,pending:0,failed:2,source_pending:0,pause_reason:null}},async({d})=>{
    const semantic=stage(overview(renderToStaticMarkup(d.render())),'Bedeutungssuche');
    if(status==='disabled')assert.match(semantic,/Ausgeschaltet/);
    else assert.match(semantic,/2.*fehlgeschlagen/);
    assert.doesNotMatch(semantic,/vollständig vorbereitet|ist vorbereitet/);
  });
});
