import assert from 'node:assert/strict';
import { after, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

// Expose the existing private component only in the test transform.
const server = await createServer({
  root: fileURLToPath(new URL('..', import.meta.url)),
  plugins: [{name: 'test-working-progress', enforce: 'pre', transform(code, id) {
    if (id.endsWith('/src/MemoryStatus.tsx')) return code + '\nexport { WorkingMemoryProgress };';
  }}],
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom',
});
after(() => server.close());
const {WorkingMemoryProgress} = await server.ssrLoadModule('/src/MemoryStatus.tsx');
const base={total:10, done:3, remaining:7, retry:1, skipped:0, estimate_seconds:1200};
const render=(props={}, progress={})=>renderToStaticMarkup(createElement(WorkingMemoryProgress,
  {progress:{...base,...progress}, enabled:true, wartet:false,...props}));

test('global or power pause suppresses completion time while retaining real progress',()=>{
  for (const pauseReason of ['Pausiert. Mit Weiter geht es weiter.', 'Die Verarbeitung pausiert im Akkubetrieb.']) {
    const html=render({pauseReason});
    assert.match(html,/3 von 10/);
    assert.ok(html.includes(pauseReason));
    assert.doesNotMatch(html,/Noch etwa|Restzeit wird|sobald das Sprachmodell/);
  }
});

test('stale completed coverage never claims current completion',()=>{
  const html=render({stale:true},{done:10,remaining:0,retry:0});
  assert.match(html,/letzten bekannten Stand|beim letzten Abruf/);
  assert.doesNotMatch(html,/Alle Quellen sind sortiert|Sortieren ist abgeschlossen/);
});

test('stale partial coverage suppresses time and promised retries',()=>{
  const html=render({stale:true});
  assert.match(html,/letzten bekannten Stand|beim letzten Abruf/);
  assert.doesNotMatch(html,/Noch etwa|werden erneut versucht|sobald das Sprachmodell/);
});

test('available running coverage keeps the estimate; complete coverage keeps its scoped completion',()=>{
  assert.match(render(),/Noch etwa/);
  assert.match(render({}, {done:10,remaining:0,retry:0}),/Alle Quellen sind sortiert/);
});

test('switching off classification is not undone by clearing the independent background pause',()=>{
  const html=render({enabled:false,wartet:false,pauseReason:'Pausiert. Mit Weiter geht es weiter.'});
  assert.match(html,/automatische Sortieren ist pausiert/);
  assert.doesNotMatch(html,/Mit Weiter|Akkubetrieb|Noch etwa/);
});
