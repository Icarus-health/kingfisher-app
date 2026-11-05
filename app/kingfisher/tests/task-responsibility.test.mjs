import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';
import {taskHref, taskUserActionable} from '../src/taskWorkflow.ts';
import {projectColumns} from '../src/taskWorkspaceModel.ts';

const root = fileURLToPath(new URL('..', import.meta.url));
const stateModule = 'virtual:task-responsibility-hooks';

function find(tree, predicate) {
  if (Array.isArray(tree)) return tree.flatMap(child => find(child, predicate));
  if (typeof tree !== 'object' || tree === null) return [];
  return [...(predicate(tree) ? [tree] : []), ...find(tree.props?.children, predicate)];
}
function text(tree) {
  if (Array.isArray(tree)) return tree.map(text).join('');
  return typeof tree === 'object' ? text(tree?.props?.children) : typeof tree === 'string' ? tree : '';
}

async function withEditor(run) {
  const server = await createServer({
    root, cacheDir: testCache('task-responsibility'), configFile: false,
    plugins: [{
      name: 'responsibility-hook-driver',
      enforce: 'pre',
      resolveId(id) {if (id === stateModule) return '\0' + id;},
      load(id) {
        if (id === '\0' + stateModule) return `
          export const useState = (...args) => globalThis.__responsibilityDriver.state(...args);
          export const useRef = (...args) => globalThis.__responsibilityDriver.ref(...args);
          export const useEffect = (...args) => globalThis.__responsibilityDriver.effect(...args);
          export const useMemo = factory => factory();
          export const useId = () => 'synthetic-responsibility-address';
        `;
      },
      transform(code, id) {
        if (['TaskResponsibility', 'TaskDetail', 'MailQuickTask'].some(name => id.endsWith(`/src/${name}.tsx`))) {
          return code.replace(/from (["'])react\1/, `from '${stateModule}'`);
        }
      },
    }],
    server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom',
  });
  const oldDriver = globalThis.__responsibilityDriver;
  const oldFetch = globalThis.fetch;
  globalThis.fetch = () => {throw new Error('Unexpected fetch in synthetic editor test');};
  try {
    const {TaskResponsibility} = await server.ssrLoadModule('/src/TaskResponsibility.tsx');
    const {TaskDetail} = await server.ssrLoadModule('/src/TaskDetail.tsx');
    const {MailQuickTask} = await server.ssrLoadModule('/src/MailQuickTask.tsx');
    const {api, ApiError} = await server.ssrLoadModule('/src/api.ts');
    function makeDriver(props, Component = TaskResponsibility) {
      const values = [], refs = [], dependencies = [], effects = [], cleanups = [];
      let stateIndex = 0, refIndex = 0, effectIndex = 0;
      return {
        state(initial) {
          const index = stateIndex++;
          if (!(index in values)) values[index] = typeof initial === 'function' ? initial() : initial;
          return [values[index], value => {values[index] = typeof value === 'function' ? value(values[index]) : value;}];
        },
        ref(initial) {return refs[refIndex++] ??= {current: initial};},
        effect(effect, next) {
          const index = effectIndex++;
          if (dependencies[index] && next.every((value, j) => Object.is(value, dependencies[index][j]))) return;
          dependencies[index] = next;
          effects.push(() => {cleanups[index]?.(); cleanups[index] = effect();});
        },
        render() {
          stateIndex = refIndex = effectIndex = 0;
          globalThis.__responsibilityDriver = this;
          return Component(props);
        },
        async flush() {
          while (effects.length) effects.shift()();
          await new Promise(resolve => setImmediate(resolve));
          return this.render();
        },
      };
    }
    await run(api, ApiError, makeDriver, {TaskDetail, MailQuickTask});
  } finally {
    globalThis.fetch = oldFetch;
    globalThis.__responsibilityDriver = oldDriver;
    await server.close();
  }
}

const allowMutation = () => () => {};
const base = {id: 'synthetic-task', status: 'open', wartet_auf: null, responsibility: null};
const person = {version: 1, decision: 'person', address: 'alex.two@example.invalid', label: 'Alex'};
const unknown = {version: 1, decision: 'unknown', address: null, label: null};
const self = {version: 1, decision: 'self', address: null, label: null};
const snapshot = (revision, responsibility, sequence = null, overlap = false) => ({
  task: {...base, responsibility}, revision, responsibility_event_sequence: sequence, own_address_overlap: overlap,
});
const element = (tree, tag, label) => find(tree, node => node.type === tag && (!label || text(node).includes(label)))[0];
const input = (tree, length) => find(tree, node => node.type === 'input' && node.props.maxLength === length)[0];
const submit = tree => element(tree, 'form').props.onSubmit({preventDefault() {}});
const change = (node, value) => node.props.onChange({target: {value}});

test('detail editor keeps a single request on response loss and requires review after a conflict', () => withEditor(async (api, ApiError, driver) => {
  let current = snapshot(10, null);
  let contactLoads = 0;
  const requests = [], parent = [];
  api.taskResponsibility = async () => current;
  api.responsibilityContacts = async () => {
    contactLoads++;
    return [{name: 'Alex', adressen: ['alex.one@example.invalid', 'alex.two@example.invalid']}, {name: 'Keine Adresse'}];
  };
  api.changeTaskResponsibility = async (_id, command) => {
    requests.push(command);
    if (requests.length === 1) throw new Error('Synthetic response loss');
    if (requests.length === 2) throw new ApiError(409);
    current = snapshot(12, person, 12, true);
    return {...current, applied_event_sequence: 12, replayed: false};
  };
  const d = driver({task: base, refreshKey: 0, disabled: false, beginMutation: allowMutation, onSnapshot: (...args) => parent.push(args)});
  let tree = d.render();
  assert.match(renderToStaticMarkup(tree), /Zuständigkeit · Nicht bestätigt/);
  tree = await d.flush();
  element(tree, 'button', 'Zuständigkeit ·').props.onClick();
  tree = d.render();
  assert.equal(element(tree, 'button', 'Zuständigkeit bestätigen').props.disabled, true);
  assert.equal(contactLoads, 0);
  change(element(tree, 'select'), 'person');
  tree = d.render();
  assert.equal(element(tree, 'button', 'Zuständigkeit bestätigen').props.disabled, true);
  tree = await d.flush();
  assert.equal(contactLoads, 1);
  assert.deepEqual(find(tree, node => node.type === 'datalist')[0].props.children.map(option => option.props.value),
    ['alex.one@example.invalid', 'alex.two@example.invalid']);
  change(input(tree, 254), person.address);
  tree = d.render();
  change(input(tree, 120), person.label);
  tree = d.render();
  await submit(tree);
  tree = d.render();
  assert.match(text(tree), /Speicherung ist unklar/);
  assert.equal(input(tree, 254).props.disabled, true);
  assert.equal(requests[0].owner.address, person.address);
  await submit(tree);
  assert.strictEqual(requests[1], requests[0]);
  tree = d.render();
  assert.equal(input(tree, 254).props.value, person.address);
  assert.equal(element(tree, 'button', 'Zuständigkeit bestätigen').props.disabled, true);
  current = snapshot(11, self, 11);
  element(tree, 'button', 'Aktuellen Stand laden').props.onClick();
  tree = d.render();
  tree = await d.flush();
  assert.match(text(tree), /Zuständigkeit · Ich/);
  assert.equal(input(tree, 120).props.value, person.label);
  assert.equal(requests.length, 2);
  await submit(tree);
  tree = d.render();
  assert.equal(requests[2].expected_revision, 11);
  assert.notEqual(requests[2].request_id, requests[0].request_id);
  assert.equal(requests[2].confirmed, true);
  assert.match(text(tree), /Personenadresse gehört inzwischen zu deinen Konten/);
  assert.equal(parent.at(-1)[0].revision, 12);
  assert.equal(parent.at(-1)[1], true);
  assert.equal(element(tree, 'button', 'Zuständigkeit bestätigen').props.disabled, true);
}));

for (const status of ['done', 'dropped']) test(`${status} decisions can reset explicitly and undo the latest revision`, () => withEditor(async (api, _ApiError, driver) => {
  const task = {...base, status, responsibility: person};
  let current = {...snapshot(41, person, 39), task};
  const requests = [];
  api.taskResponsibility = async () => current;
  api.responsibilityContacts = async () => [];
  api.changeTaskResponsibility = async (_id, command) => {
    requests.push(command);
    const next = command.operation === 'reset' ? unknown : person;
    current = {...snapshot(current.revision + 1, next, current.revision + 1), task: {...task, responsibility: next}};
    return {...current, applied_event_sequence: current.revision, replayed: false};
  };
  const d = driver({task, refreshKey: 0, disabled: false, beginMutation: allowMutation, onSnapshot() {}});
  d.render();
  let tree = await d.flush();
  element(tree, 'button', 'Zuständigkeit ·').props.onClick();
  tree = d.render();
  change(element(tree, 'select'), 'unknown');
  tree = d.render();
  assert.match(text(tree), /ausdrücklich auf Ungeklärt/);
  await submit(tree);
  tree = d.render();
  assert.equal(requests[0].operation, 'reset');
  assert.equal(requests[0].expected_revision, 41);
  element(tree, 'button', 'Letzte Änderung rückgängig machen').props.onClick();
  tree = d.render();
  await submit(tree);
  tree = d.render();
  assert.equal(requests[1].operation, 'undo');
  assert.equal(requests[1].target_event_sequence, 42);
  assert.match(renderToStaticMarkup(tree), /Alex &lt;alex.two@example.invalid&gt;/);
}));

test('list links, filters and width-safe markup keep assignment and waiting distinct', () => {
  const otherWaiting = {...base, responsibility: person, wartet_auf: 'Sam'};
  const unclear = {...base, id: 'synthetic-unclear', responsibility: unknown};
  assert.match(taskHref(otherWaiting), /view=others&task=synthetic-task/);
  assert.match(taskHref(unclear), /view=unassigned/);
  assert.equal(taskUserActionable(otherWaiting), false);
  assert.equal(taskUserActionable(unclear), false);
  const columns = Object.fromEntries(projectColumns([otherWaiting, unclear]).map(col => [col.view, col.items]));
  assert.deepEqual(columns.mine, []);
  assert.deepEqual(columns.waiting, [otherWaiting]);
  assert.deepEqual(columns.others, [otherWaiting]);
  assert.deepEqual(columns.unassigned, [unclear]);
  const source = name => readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8');
  assert.match(source('TaskDetail.tsx'), /\{task && <TaskResponsibility/);
  assert.match(source('TaskDetail.tsx'), /historyRevision=\{historyRevision\}/);
  assert.match(source('TaskHistory.tsx'), /Bestätigende Person: nicht erfasst/);
  const css = source('WorkspaceTasks.css');
  assert.match(css, /task-responsibility-person.*minmax\(min\(100%, 12rem\), 1fr\)/);
  assert.match(css, /task-responsibility-actions.*flex-wrap: wrap/);
});
for (const changeType of ['completion', 'ordinary edit']) test(`a delayed responsibility POST cannot undo a newer ${changeType} snapshot`, () => withEditor(async (api, _ApiError, driver) => {
  let current = snapshot(10, null);
  let resolveWrite;
  const updates = [];
  api.taskResponsibility = async () => current;
  api.responsibilityContacts = async () => [];
  api.changeTaskResponsibility = async () => new Promise(resolve => {resolveWrite = resolve;});
  const props = {task: base, refreshKey: 0, disabled: false, beginMutation: allowMutation, onSnapshot: value => updates.push(value)};
  const d = driver(props);
  d.render();
  let tree = await d.flush();
  element(tree, 'button', 'Zuständigkeit ·').props.onClick();
  tree = d.render();
  change(element(tree, 'select'), 'unknown');
  tree = d.render();
  const writing = submit(tree);
  // Responsibility committed as 11, but its response was delayed. A newer
  // snapshot can come from a sibling action or a different window.
  const latest = changeType === 'completion' ? {status: 'done'} : {title: 'Bearbeiteter Titel'};
  current = {...snapshot(12, unknown, 11), task: {...base, ...latest, responsibility: unknown}};
  props.task = current.task;
  props.refreshKey = 1;
  d.render();
  tree = await d.flush();
  assert.equal(updates.at(-1).revision, 12);
  assert.deepEqual(updates.at(-1).task, current.task);
  resolveWrite({...snapshot(11, unknown, 11), applied_event_sequence: 11, replayed: false});
  await writing;
  d.render();
  assert.equal(updates.at(-1).revision, 12, 'delayed responsibility response must not restore older task state');
  assert.deepEqual(updates.at(-1).task, current.task);
}));

test('the task detail shares one write lock across responsibility, completion and ordinary edits', () => withEditor(async (api, _ApiError, driver, {TaskDetail}) => {
  const oldWindow = globalThis.window;
  globalThis.window = {location: {search: ''}};
  try {
    const task = {...base, title: 'Offene Probe', tags: [], project_id: null};
    api.task = async () => task;
    api.projects = async () => [];
    let completed = 0;
    let edited = 0;
    api.completeTask = async () => {completed++; throw new Error('Synthetic completion failure');};
    api.editTask = async () => {edited++; return {...task, title: 'Bearbeitete Probe'};};
    const d = driver({taskId: base.id, onChanged() {}}, TaskDetail);
    d.render();
    let tree = await d.flush();
    const row = find(tree, node => node.type?.name === 'TaskRow')[0];
    const editor = find(tree, node => node.type?.name === 'TaskResponsibility')[0];
    const release = editor.props.beginMutation();
    assert.equal(typeof release, 'function');
    row.props.onComplete();
    assert.equal(await row.props.onEdit({title: 'Bearbeitete Probe'}), false);
    assert.deepEqual([completed, edited], [0, 0]);
    tree = d.render();
    assert.equal(find(tree, node => node.type?.name === 'TaskRow')[0].props.completing, true);
    release();
    row.props.onComplete();
    tree = await d.flush();
    assert.equal(completed, 1);
    assert.equal(await find(tree, node => node.type?.name === 'TaskRow')[0].props.onEdit({title: 'Bearbeitete Probe'}), true);
    assert.equal(edited, 1);
  } finally {
    globalThis.window = oldWindow;
  }
}));

test('quick mail conflict displays the review instruction and retains the suggestion', () => withEditor(async (api, ApiError, driver, {MailQuickTask}) => {
  const requests = [];
  const review = 'Bitte die vorhandene Aufgabe und den neuen Vorschlag prüfen.';
  let saved = 0;
  api.addMailTask = async (...args) => {requests.push(args); throw new ApiError(409, review);};
  const d = driver({uid: 'synthetic:1', title: 'Angebot prüfen', quote: 'Quellenstelle', sourceDigest: 'digest',
                    disabled: false, onSaved: () => saved++}, MailQuickTask);
  let tree = d.render();
  element(tree, 'button', 'Als Aufgabe übernehmen').props.onClick();
  tree = await d.flush();
  assert.match(text(tree), /vorhandene Aufgabe und den neuen Vorschlag prüfen/);
  const retry = element(tree, 'button', 'Als Aufgabe übernehmen');
  assert.equal(retry.props.disabled, false);
  retry.props.onClick();
  await d.flush();
  assert.deepEqual(requests[1], requests[0]);
  assert.equal(saved, 0);
}));

test('a stale refresh never rolls back the history revision and offers to reload', () => withEditor(async (api, _ApiError, driver) => {
  let current = snapshot(12, self, 12);
  const updates = [];
  api.taskResponsibility = async () => current;
  const props = {task: current.task, refreshKey: 0, disabled: false, beginMutation: allowMutation,
                 onSnapshot: value => updates.push(value)};
  const d = driver(props);
  d.render();
  let tree = await d.flush();
  element(tree, 'button', 'Zuständigkeit ·').props.onClick();
  current = snapshot(11, person, 11);
  props.refreshKey = 1;
  d.render();
  tree = await d.flush();
  assert.equal(updates.at(-1).revision, 12);
  assert.match(text(tree), /Zuständigkeit · Ich/);
  assert.ok(element(tree, 'button', 'Aktuellen Stand laden'));
  current = snapshot(13, unknown, 13);
  element(tree, 'button', 'Aktuellen Stand laden').props.onClick();
  d.render();
  await d.flush();
  assert.equal(updates.at(-1).revision, 13);

  let resolveOlderRead;
  api.taskResponsibility = () => new Promise(resolve => {resolveOlderRead = resolve;});
  props.refreshKey = 2;
  d.render();
  await d.flush();
  api.taskResponsibility = async () => snapshot(14, person, 14);
  props.refreshKey = 3;
  d.render();
  await d.flush();
  resolveOlderRead(snapshot(13, unknown, 13));
  tree = await d.flush();
  assert.equal(updates.at(-1).revision, 14);
  assert.match(text(tree), /Zuständigkeit · Alex/);
}));
