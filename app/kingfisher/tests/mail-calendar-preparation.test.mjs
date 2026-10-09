import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {build} from 'vite';

const compiled = await build({configFile:false, logLevel:'silent', build:{write:false, minify:false,
  lib:{entry:fileURLToPath(new URL('../src/MailCalendarPreparation.tsx', import.meta.url)),formats:['cjs']},
  rollupOptions:{external:['react','react/jsx-runtime','./api','./mailCalendarInput','./CalendarActionForm']}}});
const code = [compiled].flat().flatMap(result => result.output).find(item => item.type === 'chunk').code;
const require = createRequire(import.meta.url);
const binding = 'a'.repeat(64), stand = 'b'.repeat(64);
const record = overrides => ({id:'mp-one',uid:'mail:1',binding,stand,status:'preparation',reviewed:false,
  fields:{title:'Einladung',start:'2026-10-12T09:30:00+02:00',end:'2026-10-12T10:30:00+02:00'},
  origins:{title:{kind:'source',quote:'Einladung'},start:{kind:'source',quote:'09:30 bis 10:30'},end:{kind:'source',quote:'09:30 bis 10:30'}},
  context:{items:[{episode_id:'ep1',current:true,title:'Einladung',sender:'A',occurred_at:null,recorded_at:'2026-10-09',text:'Originaltext mit Termin',truncated:false}],limited:true,detail:'Gespeicherter Verlauf',warnings:['Unvollständiger Verlauf']},...overrides});

function form({expectedBinding=binding,prepare=async () => record({}),save=async (_id,input) => record({...input,stand:'c'.repeat(64)}),
  read=async()=>record({}),
  sources=async () => ({sources:[{id:'g1',label:'Privat',user:'me',calendar_id:'primary',can_write:true,reason:null}]}),
  preview=async () => ({id:'draft-1',status:'preview',kind:'create',source_id:'g1',stand:'d'.repeat(64),preview:{title:'Einladung',attendees:[],send_updates:'none'}})}={}) {
  const slots=[], calls={prepare:[],read:[],save:[],sources:0,preview:[]}; let index=0, props={uid:'mail:1',expectedBinding};
  const hooks={useState(value){const slot=index++;if(!(slot in slots))slots[slot]=typeof value==='function'?value():value;return [slots[slot],next=>{slots[slot]=typeof next==='function'?next(slots[slot]):next;}];},
    useRef(value){const slot=index++;return slots[slot]??=( {current:value});},useEffect(){}};
  const module={exports:{}};
  function CalendarActionForm(props){return {type:'CalendarActionFormMock',props};}
  new Function('require','module','exports',code)(name=>{
    if(name==='react')return hooks;
    if(name==='./api')return {api:{mailCalendarPrepare:async(...args)=>{calls.prepare.push(args);return prepare(...args);},
      mailCalendarRead:async(...args)=>{calls.read.push(args);return read(...args);},
      mailCalendarSave:async(...args)=>{calls.save.push(args);return save(...args);},
      calendarActionSources:async()=>{calls.sources++;return sources();},
      mailCalendarPreview:async(...args)=>{calls.preview.push(args);return preview(...args);}}};
    if(name==='./mailCalendarInput')return {splitIsoOffset:value=>({local:value.slice(0,16),offset:value.slice(19)}),
      buildIsoOffset:(local,offset,original)=>local===original?.slice(0,16)&&offset===original?.slice(19)?original:`${local}:00${offset}`,
      offsetOptions:()=>[{value:'Z',label:'UTC'},{value:'+01:00',label:'MEZ'},{value:'+02:00',label:'MESZ'}]};
    if(name==='CalendarActionForm')return {CalendarActionForm};
    if(name==='./CalendarActionForm')return {CalendarActionForm};
    return require(name);
  },module,module.exports);
  function render(next){if(next)props={...props,...next};index=0;return module.exports.MailCalendarPreparation(props);}
  function nodes(node){return !node||typeof node!=='object'?[]:[node,...[node.props?.children].flat(Infinity).flatMap(nodes)];}
  function findText(value){return nodes(render()).find(n=>n.type==='button'&&String(n.props.children).includes(value));}
  function input(label){return nodes(render()).find(n=>n.type==='label'&&String(n.props.children?.[0]||'').includes(label))?.props.children?.find?.(child=>child?.type==='input');}
  function byId(id){return nodes(render()).find(n=>n.props?.id===id);}
  function selectWithOption(value){return nodes(render()).find(n=>n.type==='select'&&nodes(n).some(child=>child.type==='option'&&child.props.value===value));}
  async function submitSave(){const f=nodes(render()).find(n=>n.type==='form');await f.props.onSubmit({preventDefault(){}});await new Promise(resolve=>setImmediate(resolve));}
  async function click(value){const button=findText(value);assert.ok(button,`button ${value} exists`);if(button.props.type==='submit')await submitSave();else await button.props.onClick?.();await new Promise(resolve=>setImmediate(resolve));}
  return {render,nodes,findText,byId,selectWithOption,click,calls,edit(id,value){byId(id).props.onChange({target:{value}});},setChecked(id,checked){byId(id).props.onChange({target:{checked}});},
    prepare,save,sourceFetch:sources,submitSave(){const f=nodes(render()).find(n=>n.type==='form');return f.props.onSubmit({preventDefault(){}});}};
}

test('local preparation happens only after explicit click and displays original plus warnings', async () => {
  const ui=form();
  assert.equal(ui.calls.prepare.length,0);
  await ui.click('Termin vorbereiten');
  assert.equal(ui.calls.prepare.length,1);
  assert.deepEqual(ui.calls.prepare[0],['mail:1',binding]);
  const tree=ui.nodes(ui.render());
  assert.ok(tree.some(n=>n.type==='pre'&&String(n.props.children).includes('Originaltext mit Termin')));
  assert.ok(tree.some(n=>n.props?.role==='status'&&String(n.props.children).includes('Unvollständiger Verlauf')));
});

test('missing or changed binding blocks preparation and never loses hand-edited values', async () => {
  const absent=form({expectedBinding:null});
  await absent.click('Termin vorbereiten');
  assert.equal(absent.calls.prepare.length,0);
  assert.ok(absent.nodes(absent.render()).some(n=>n.props?.role==='alert'));

  const ui=form(); await ui.click('Termin vorbereiten');
  ui.edit('mail-calendar-title','Mein Titel');
  ui.render({expectedBinding:'c'.repeat(64)});
  await ui.click('Speichern');
  assert.equal(ui.calls.save.length,0);
  assert.equal(ui.byId('mail-calendar-title').props.value,'Mein Titel');
});

test('failed refresh clears old source DOM but preserves edits', async () => {
  let opens=0;
  const ui=form({prepare:async()=>{opens++;return record({fields:{title:opens===1?'Einladung':'Serverwert',start:'2026-10-12T09:30:00+02:00',end:'2026-10-12T10:30:00+02:00'}});},
    read:async()=>{throw new Error('Quelle nicht mehr aktuell');}});
  await ui.click('Termin vorbereiten');
  ui.edit('mail-calendar-title','Mein Entwurf');
  await ui.click('Quelle erneut prüfen');
  const tree=ui.nodes(ui.render());
  assert.equal(tree.some(n=>n.type==='pre'&&String(n.props.children).includes('Originaltext mit Termin')),false);
  assert.equal(ui.byId('mail-calendar-title').props.value,'Mein Entwurf');
  assert.equal(ui.calls.read.length,1);
  await ui.click('Quelle erneut prüfen');
  assert.equal(ui.byId('mail-calendar-title').props.value,'Mein Entwurf');
  assert.ok(ui.nodes(ui.render()).some(n=>n.props?.role==='status'&&String(n.props.children).includes('Änderungen sind noch nicht gespeichert')));
});

test('field edits clear review; save errors retain edits and cannot reach calendar preview', async () => {
  const ui=form({save:async()=>{throw new Error('Speichern fehlgeschlagen');}});
  await ui.click('Termin vorbereiten');
  ui.setChecked('mail-calendar-reviewed',true);
  ui.edit('mail-calendar-title','Bearbeitet');
  assert.equal(ui.byId('mail-calendar-reviewed').props.checked,false);
  await ui.click('Speichern');
  assert.equal(ui.calls.save.length,1);
  assert.equal(ui.byId('mail-calendar-title').props.value,'Bearbeitet');
  assert.equal(ui.calls.sources,0);
  assert.equal(ui.calls.preview.length,0);
});

test('saving unchanged source times preserves seconds and the exact source offsets', async () => {
  const ui=form(); await ui.click('Termin vorbereiten');
  ui.edit('mail-calendar-start','2026-10-12T09:31');
  ui.edit('mail-calendar-start','2026-10-12T09:30');
  ui.setChecked('mail-calendar-reviewed',true);
  await ui.click('Speichern');
  assert.equal(ui.calls.save[0][1].fields.start,'2026-10-12T09:30:00+02:00');
  assert.equal(ui.calls.save[0][1].fields.end,'2026-10-12T10:30:00+02:00');
  assert.equal(ui.calls.save[0][1].reviewed,true);
});

test('rapid repeated prepare click makes only one local request', async () => {
  let release;
  const ui=form({prepare:()=>new Promise(resolve=>{release=resolve;})});
  const button=ui.findText('Termin vorbereiten');
  button.props.onClick();button.props.onClick();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.calls.prepare.length,1);
  release(record({}));
  await new Promise(resolve=>setImmediate(resolve));
  assert.ok(ui.nodes(ui.render()).some(n=>n.type==='pre'));
});

test('handoff requires saved reviewed complete values and uses existing calendar preview path', async () => {
  const ui=form(); await ui.click('Termin vorbereiten');
  ui.setChecked('mail-calendar-reviewed',true);
  await ui.click('Speichern');
  await ui.click('Kalender für Vorschau laden');
  assert.equal(ui.calls.sources,1);
  await ui.click('Kalendervorschau erstellen');
  assert.equal(ui.calls.preview.length,1);
  assert.equal(ui.calls.preview[0][0],'mp-one');
  assert.equal(ui.calls.preview[0][1].source_id,'g1');
  assert.ok(ui.nodes(ui.render()).some(n=>n.type?.name==='CalendarActionForm'));
});

test('editing after a saved preview choice cannot submit the prior reviewed stand', async () => {
  const ui=form();await ui.click('Termin vorbereiten');ui.setChecked('mail-calendar-reviewed',true);await ui.click('Speichern');
  await ui.click('Kalender für Vorschau laden');
  ui.edit('mail-calendar-title','Andere Zeit');
  await ui.click('Kalendervorschau erstellen');
  assert.equal(ui.calls.preview.length,0);
  assert.ok(ui.nodes(ui.render()).some(n=>n.props?.role==='alert'));
});

test('changed source binding hides a previously prepared Google preview immediately', async () => {
  const ui=form();await ui.click('Termin vorbereiten');ui.setChecked('mail-calendar-reviewed',true);await ui.click('Speichern');
  await ui.click('Kalender für Vorschau laden');await ui.click('Kalendervorschau erstellen');
  assert.ok(ui.nodes(ui.render()).some(n=>n.type?.name==='CalendarActionForm'));
  ui.render({expectedBinding:'e'.repeat(64)});
  assert.equal(ui.nodes(ui.render()).some(n=>n.type?.name==='CalendarActionForm'),false);
});

test('failed later preview discards the older Google preview and calendar choices', async () => {
  let attempts=0;
  const ui=form({preview:async()=>{
    if(++attempts>1)throw new Error('Quellenprüfung fehlgeschlagen');
    return {id:'draft-1',status:'preview',kind:'create',source_id:'g1',stand:'d'.repeat(64),preview:{title:'Einladung',attendees:[],send_updates:'none'}};
  }});
  await ui.click('Termin vorbereiten');ui.setChecked('mail-calendar-reviewed',true);await ui.click('Speichern');
  await ui.click('Kalender für Vorschau laden');await ui.click('Kalendervorschau erstellen');
  const oldDraft=ui.nodes(ui.render()).find(n=>n.type?.name==='CalendarActionForm');assert.ok(oldDraft);
  oldDraft.props.onClose();
  await ui.click('Kalendervorschau erstellen');
  const tree=ui.nodes(ui.render());
  assert.equal(tree.some(n=>n.type?.name==='CalendarActionForm'),false);
  assert.equal(tree.some(n=>n.type==='option'&&n.props.value==='g1'),false);
  assert.equal(tree.some(n=>n.type==='pre'&&String(n.props.children).includes('Originaltext mit Termin')),false);
});

test('changing calendar or notification policy unmounts the old preview before the next preview', async () => {
  let attempts=0;
  const ui=form({sources:async()=>({sources:[
    {id:'g1',label:'Privat',user:'me',calendar_id:'primary',can_write:true,reason:null},
    {id:'g2',label:'Arbeit',user:'me',calendar_id:'work',can_write:true,reason:null},
  ]}),preview:async(_id,input)=>({id:`draft-${++attempts}`,status:'preview',kind:'create',source_id:input.source_id,stand:'d'.repeat(64),preview:{title:'Einladung',attendees:[],send_updates:input.send_updates}})});
  await ui.click('Termin vorbereiten');ui.setChecked('mail-calendar-reviewed',true);await ui.click('Speichern');
  await ui.click('Kalender für Vorschau laden');await ui.click('Kalendervorschau erstellen');
  let old=ui.nodes(ui.render()).find(n=>n.type?.name==='CalendarActionForm');assert.equal(old.props.preparedDraft.id,'draft-1');
  ui.selectWithOption('g2').props.onChange({target:{value:'g2'}});
  assert.equal(ui.nodes(ui.render()).some(n=>n.type?.name==='CalendarActionForm'),false);
  ui.selectWithOption('all').props.onChange({target:{value:'all'}});
  assert.equal(ui.nodes(ui.render()).some(n=>n.type?.name==='CalendarActionForm'),false);
  await ui.click('Kalendervorschau erstellen');
  const next=ui.nodes(ui.render()).find(n=>n.type?.name==='CalendarActionForm');
  assert.equal(next.props.preparedDraft.id,'draft-2');
  assert.equal(next.props.preparedDraft.source_id,'g2');
  assert.equal(next.props.preparedDraft.preview.send_updates,'all');
  assert.equal(next.key,`draft-2:${'d'.repeat(64)}`);
});
