import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {createServer} from 'vite';
import {testCache} from './testcache.mjs';

const server = await createServer({cacheDir: testCache('task-status-recall-ui'),
  root: fileURLToPath(new URL('..', import.meta.url)),
  server: {middlewareMode: true, watch: null, ws: false, hmr: false}, appType: 'custom'});
after(() => server.close());

test('a current or dropped task links to its selected receipt; withheld text has no link', async () => {
  const {TaskStatusAnswer} = await server.ssrLoadModule('/src/TaskStatusAnswer.tsx');
  const {taskHistorySequence} = await server.ssrLoadModule('/src/taskWorkflow.ts');
  const {TaskHistory} = await server.ssrLoadModule('/src/TaskHistory.tsx');
  const id = 't-000000000001';
  for (const status of ['done', 'dropped']) {
    const content = '„<b>**Atlas**</b>“';
    const html = renderToStaticMarkup(createElement(TaskStatusAnswer, {
      content, link: {id, status, sequence: '27'}, messageId: 'synthetic'}));
    assert.match(html, /Aufgabe und Verlauf ansehen/);
    assert.match(html, /&lt;b&gt;\*\*Atlas\*\*&lt;\/b&gt;/);
    const href = html.match(/href="([^"]+)"/)[1].replaceAll('&amp;', '&');
    const url = new URL(href, 'https://example.invalid');
    assert.equal(url.pathname, '/vorhaben');
    assert.equal(url.searchParams.get('task'), id);
    assert.equal(url.searchParams.get('view'), status === 'done' ? 'done' : 'mine');
    const sequence = taskHistorySequence(url.searchParams);
    assert.equal(sequence, '27');
    const history = renderToStaticMarkup(createElement(TaskHistory, {taskId: id, sequence, revision: '0'}));
    assert.match(history, /aria-expanded="true"/);
    assert.match(history, /aria-label="Aufgabenverlauf"/);
  }
  assert.equal(taskHistorySequence(new URLSearchParams('history=9223372036854775808')), undefined);
  const hidden = renderToStaticMarkup(createElement(TaskStatusAnswer, {content: 'Nicht verfügbar.', messageId: 'synthetic'}));
  assert.doesNotMatch(hidden, /href|Aufgabe und Verlauf ansehen/);
});
