import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {test} from 'node:test';
import {build} from 'vite';
const require=createRequire(import.meta.url);
async function editor({save=async input=>({id:'e-new',...input}),observation=null}={}) {
  assert.ok(existsSync(new URL('../src/HealthObservationEditor.tsx', import.meta.url)), 'Own-health save and preview control is missing');
  const compiled=await build({configFile:false,logLevel:'silent',build:{write:false,minify:false,
    lib:{entry:fileURLToPath(new URL('../src/HealthObservationEditor.tsx',import.meta.url)),formats:['cjs']},
    rollupOptions:{external:['react','react/jsx-runtime','./api','./healthObservationForm']}}});
  const code=[compiled].flat().flatMap(r=>r.output).find(x=>x.type==='chunk').code;
  const slots=[],calls=[],saved=[]; let index=0;
  const hooks={useState(value){const i=index++;if(!(i in slots))slots[i]=typeof value==='function'?value():value;return [slots[i],next=>slots[i]=typeof next==='function'?next(slots[i]):next];},
    useRef(value){const i=index++;return slots[i]??={current:value};}};
  const module={exports:{}};
  const helper=await import('../src/healthObservationForm.ts');
  new Function('require','module','exports',code)(name=>{
    if(name==='react')return hooks;
    if(name==='./healthObservationForm')return helper;
    if(name==='./api')return {api:{saveHealthObservation:async input=>{calls.push(['create',input]);return save(input);},correctHealthObservation:async(id,input)=>{calls.push([id,input]);return save(input);}}};
    return require(name);
  },module,module.exports);
  const render=()=>{index=0;return module.exports.HealthObservationEditor({observation,onSaved:item=>saved.push(item),onCancel(){}});};
  const nodes=node=>!node||typeof node!=='object'?[]:[node,...[node.props?.children].flat(Infinity).flatMap(nodes)];
  const byId=id=>nodes(render()).find(n=>n.props?.id===id);
  const click=async text=>{const button=nodes(render()).find(n=>n.type==='button'&&String(n.props.children).includes(text));assert.ok(button,`button ${text}`);if(button.props.type==='submit')nodes(render()).find(n=>n.type==='form').props.onSubmit({preventDefault(){}});else await button.props.onClick?.();};
  return {calls,saved,render,nodes,byId,click,edit(id,value){byId(id).props.onChange({target:{value}});},own(value){byId('health-own').props.onChange({target:{checked:value}});}};
}
async function fill(ui) {ui.edit('health-metric','Gewicht');ui.edit('health-value','072,50');ui.edit('health-unit','kg');ui.edit('health-time','2023-07-02T09:30');ui.edit('health-offset','+02:00');ui.own(true);}

test('preview never saves; explicit confirmation writes one literal source',async()=>{
  const ui=await editor();await fill(ui);
  await ui.click('Angabe prüfen');assert.equal(ui.calls.length,0);
  assert.ok(ui.nodes(ui.render()).some(n=>n.props?.role==='status'&&JSON.stringify(n.props.children).includes('072,50')));
  await ui.click('Quelle speichern');assert.equal(ui.calls.length,1);assert.equal(ui.saved.length,1);
  assert.equal(ui.calls[0][1].value,'072,50');assert.equal(ui.calls[0][1].observed_at,'2023-07-02T09:30:00+02:00');
});

test('failed send retains edits and same replay nonce; changing input clears preview',async()=>{
  const ui=await editor({save:async()=>{throw new Error('connection lost');}});await fill(ui);
  await ui.click('Angabe prüfen');await ui.click('Quelle speichern');await ui.click('Quelle speichern');
  assert.equal(ui.calls[0][1].request_id,ui.calls[1][1].request_id);
  assert.equal(ui.byId('health-value').props.value,'072,50');assert.equal(ui.saved.length,0);
  ui.edit('health-value','73');
  assert.equal(ui.nodes(ui.render()).some(n=>n.type==='button'&&n.props.children==='Quelle speichern'),false);
});

test('stale correction shows error, retains draft and never overwrites current version',async()=>{
  const original={id:'e-original',support_fingerprint:'a'.repeat(64),subject:'self',metric:'Gewicht',value:'72',unit:'kg',observed_at:'2023-07-02T09:30:00+02:00',note:''};
  const ui=await editor({observation:original,save:async()=>{throw Object.assign(new Error('HTTP 409'),{status:409});}});
  ui.edit('health-value','73');ui.own(true);await ui.click('Angabe prüfen');await ui.click('Quelle speichern');
  assert.equal(ui.calls[0][0],'e-original');assert.equal(ui.calls[0][1].expected_support_fingerprint,original.support_fingerprint);
  assert.equal(ui.byId('health-value').props.value,'73');assert.equal(ui.saved.length,0);
  assert.ok(ui.nodes(ui.render()).some(n=>n.props?.role==='alert'&&JSON.stringify(n.props.children).includes('inzwischen')));
});

test('double-click during an unresolved save cannot create another request',async()=>{
  let resolve;
  const ui=await editor({save:()=>new Promise(r=>resolve=r)});await fill(ui);await ui.click('Angabe prüfen');
  const button=ui.nodes(ui.render()).find(n=>n.type==='button'&&n.props.children==='Quelle speichern');
  const pending=button.props.onClick();const again=button.props.onClick();
  assert.equal(ui.calls.length,1);resolve({id:'e-new'});await pending;await again;
  assert.equal(ui.saved.length,1);
});
