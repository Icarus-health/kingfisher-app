import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {build} from 'vite';

const compiled = await build({configFile:false, logLevel:'silent', build:{write:false, minify:false,
  lib:{entry:fileURLToPath(new URL('../src/MailTaskForm.tsx', import.meta.url)),formats:['cjs']},
  rollupOptions:{external:['react','react/jsx-runtime','./api','./taskWorkflow','./ui']}}});
const code = [compiled].flat().flatMap(result => result.output).find(item => item.type === 'chunk').code;

// Die echten TSX-Handler laufen mit isoliertem Hookzustand und API-Aufzeichnung.
// Kein nachgebauter Submit-Code; diese Fälle betreffen manuelle Eingaben.
const require = createRequire(import.meta.url);
function form(initial) {
  const slots = [], calls = [];
  let index = 0, props = initial;
  const hooks = {
    useState(value) {
      const slot = index++;
      if (!(slot in slots)) slots[slot] = typeof value === 'function' ? value() : value;
      return [slots[slot], next => {slots[slot] = typeof next === 'function' ? next(slots[slot]) : next;}];
    },
    useRef(value) {const slot = index++; return slots[slot] ??= {current:value};},
    useEffect() {},
  };
  const module = {exports:{}};
  new Function('require', 'module', 'exports', code)(name => {
    if (name === 'react') return hooks;
    if (name === './api') return {api:{addMailTask:async (...args) => {calls.push(args); return {id:'task-synthetic'};}}};
    if (name === './taskWorkflow') return {endOfTaskDay: value => value ? `${value}T23:59:00` : null, explicitDeadline:()=>null, taskHref:()=>'/tasks/synthetic'};
    if (name === './ui') return {navigate() {}};
    return require(name);
  }, module, module.exports);
  function render(next) {if (next) props = next; index = 0; return module.exports.MailTaskForm(props);}
  function nodes(node) {return !node || typeof node !== 'object' ? [] : [node, ...[node.props?.children].flat(Infinity).flatMap(nodes)];}
  function find(predicate) {return nodes(render()).find(predicate);}
  function edit(id, value) {find(n => n.props?.id === id).props.onChange({target:{value}});}
  function open() {find(n => n.type === 'button').props.onClick();}
  async function submit() {await find(n => n.type === 'form').props.onSubmit({preventDefault() {}});}
  return {render,find,edit,open,submit,calls};
}
const digest = 'a'.repeat(64), changed = 'b'.repeat(64);
const initial = {uid:'work:1', subject:'Angebot prüfen', expectedSourceDigest:digest};

test('manual task sends opening source digest without requiring a model suggestion', async () => {
  const ui = form(initial); ui.open(); ui.edit('mail-task-title','Eigenen Termin nachhalten'); ui.edit('mail-task-due','2026-10-12');
  await ui.submit();
  assert.equal(ui.calls.length,1);
  assert.equal(ui.calls[0][1].source_digest,digest);
  assert.equal(ui.calls[0][1].title,'Eigenen Termin nachhalten');
  assert.equal(ui.calls[0][1].due,'2026-10-12T23:59:00');
  assert.equal(ui.calls[0][1].source_quote,undefined);
});

test('refresh to a different source version cannot silently rebind edited task fields', async () => {
  const ui = form(initial); ui.open(); ui.edit('mail-task-title','Mein bearbeiteter Titel');
  ui.render({...initial, expectedSourceDigest:changed}); await ui.submit();
  assert.equal(ui.calls.length,0);
  assert.equal(ui.find(n => n.props?.id === 'mail-task-title').props.value,'Mein bearbeiteter Titel');
  assert.ok(ui.find(n => n.props?.role === 'alert'));
});

test('missing opening source version prevents manual task save', async () => {
  const ui = form({...initial,expectedSourceDigest:null}); ui.open(); await ui.submit();
  assert.equal(ui.calls.length,0);
  assert.ok(ui.find(n => n.props?.role === 'alert'));
});
