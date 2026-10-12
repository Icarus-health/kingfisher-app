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
function storage() {
  const values = new Map();
  return {getItem:key => values.get(key) ?? null, setItem:(key,value) => values.set(key,value), removeItem:key => values.delete(key)};
}
function form(initial, save = async () => ({id:'task-synthetic'}), pending = storage(), random = globalThis.crypto) {
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
  new Function('require', 'module', 'exports', 'localStorage', 'crypto', code)(name => {
    if (name === 'react') return hooks;
    if (name === './api') return {ApiError:class extends Error {}, api:{addMailTask:async (...args) => {calls.push(args); return save(...args);}}};
    if (name === './taskWorkflow') return {endOfTaskDay: value => value ? `${value}T23:59:00` : null, explicitDeadline:()=>null, taskHref:()=>'/tasks/synthetic'};
    if (name === './ui') return {navigate() {}};
    return require(name);
  }, module, module.exports, pending, random);
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

test('lost response retry keeps a stable request even if fields were edited', async () => {
  let saves = 0;
  const ui = form(initial, async () => {if (++saves === 1) throw new TypeError('Lost response'); return {id:'saved-task'};});
  ui.open(); await ui.submit();
  assert.ok(ui.find(n => n.props?.role === 'alert'));
  ui.edit('mail-task-title','Geänderte Eingabe'); await ui.submit();
  assert.match(ui.calls[0][1].request_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
  assert.equal(ui.calls[1][1].request_id, ui.calls[0][1].request_id);
  assert.equal(ui.calls[1][1].title, 'Geänderte Eingabe');
});

test('two submits before React rerenders only start one save', async () => {
  let release;
  const pending = new Promise(resolve => {release = resolve;});
  const ui = form(initial, () => pending); ui.open();
  const handler = ui.find(n => n.type === 'form').props.onSubmit;
  const first = handler({preventDefault() {}}), second = handler({preventDefault() {}});
  assert.equal(ui.calls.length, 1);
  release({id:'saved-task'}); await Promise.all([first,second]);
});

test('reopening after a lost response reuses the unresolved request, confirmed save releases it', async () => {
  const pending = storage();
  const first = form(initial, async () => {throw new TypeError('Lost response');}, pending);
  first.open(); await first.submit();
  const reopened = form(initial, undefined, pending); reopened.open(); await reopened.submit();
  assert.equal(reopened.calls[0][1].request_id, first.calls[0][1].request_id);
  const next = form(initial, undefined, pending); next.open(); await next.submit();
  assert.notEqual(next.calls[0][1].request_id, first.calls[0][1].request_id);
});

test('unavailable durable retry storage fails closed before sending a task', async () => {
  const pending = {getItem:() => {throw new Error('Storage unavailable');}};
  const ui = form(initial, undefined, pending); ui.open(); await ui.submit();
  assert.equal(ui.calls.length, 0);
  assert.ok(ui.find(n => n.props?.role === 'alert'));
});

test('a deliberately new request needs task review and does not submit automatically', async () => {
  let saves = 0;
  const ui = form(initial, async () => {if (++saves === 1) throw new TypeError('Lost response'); return {id:'new-task'};});
  ui.open(); await ui.submit();
  const reset = () => ui.find(n => n.props?.id === 'mail-task-new-request');
  assert.ok(reset(), 'A reviewed recovery path must exist');
  assert.equal(reset().props.disabled, true);
  ui.edit('mail-task-title','Bewusst neue Aufgabe');
  ui.find(n => n.props?.id === 'mail-task-request-reviewed').props.onChange({target:{checked:true}});
  assert.equal(reset().props.disabled, false);
  reset().props.onClick();
  assert.equal(ui.calls.length, 1);
  await ui.submit();
  assert.notEqual(ui.calls[0][1].request_id, ui.calls[1][1].request_id);
  assert.equal(ui.calls[1][1].title, 'Bewusst neue Aufgabe');
});

test('native WebKit without randomUUID saves with a valid random-byte identity', async () => {
  const ui = form(initial, undefined, undefined, {getRandomValues:array => globalThis.crypto.getRandomValues(array)});
  ui.open(); await ui.submit();
  assert.equal(ui.calls.length, 1);
  assert.match(ui.calls[0][1].request_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
});

test('durable storage write failure prevents a task request', async () => {
  const ui = form(initial, undefined, {getItem:() => null, setItem:() => {throw new Error('Full storage');}});
  ui.open(); await ui.submit();
  assert.equal(ui.calls.length, 0);
  assert.ok(ui.find(n => n.props?.role === 'alert'));
});

test('source failure before loading the request cannot clear another unresolved save', async () => {
  const pending = storage();
  const first = form(initial, async () => {throw new TypeError('Lost response');}, pending);
  first.open(); await first.submit();
  const blocked = form(initial, undefined, pending); blocked.open();
  blocked.render({...initial, expectedSourceDigest:changed}); await blocked.submit();
  assert.equal(blocked.calls.length, 0);
  blocked.find(n => n.props?.id === 'mail-task-request-reviewed').props.onChange({target:{checked:true}});
  blocked.find(n => n.props?.id === 'mail-task-new-request').props.onClick();
  const reopened = form(initial, undefined, pending); reopened.open(); await reopened.submit();
  assert.equal(reopened.calls[0][1].request_id, first.calls[0][1].request_id);
});
