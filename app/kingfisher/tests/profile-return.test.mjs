import assert from 'node:assert/strict';
import {after, test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {existsSync} from 'node:fs';
import {createServer} from 'vite';

import {testCache} from './testcache.mjs';
const server = await createServer({cacheDir:testCache('profile-return.test'),root:fileURLToPath(new URL('..',import.meta.url)), server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(() => server.close());
const modulePath = new URL('../src/profileReturn.ts', import.meta.url);
const loaded = existsSync(modulePath) ? await server.ssrLoadModule('/src/profileReturn.ts') : {};
const returnPath = (...args) => {assert.equal(typeof loaded.memoryReturnPath, 'function', 'safe profile return helper is available'); return loaded.memoryReturnPath(...args);};
const search = target => `?source_node=person%3Aa%3Ax&return_to=${encodeURIComponent(target)}`;

test('profile return preserves the people search and page with safe encoding', () => {
  assert.equal(returnPath(search('/memory?tab=people&q=Anna+%26+Max&page=3')), '/memory?tab=people&q=Anna+%26+Max&page=3');
});
test('profile return restores project searches and discards unrelated parameters', () => {
  assert.equal(returnPath(search('/memory?tab=projects&q=Verein&page=2&return_to=https://evil.test&source_node=secret'), 'project'), '/memory?tab=projects&q=Verein&page=2');
});
test('profile return defaults to the appropriate list when no return target exists', () => {
  assert.equal(returnPath(''), '/memory?tab=people');
  assert.equal(returnPath('?source_node=abc', 'project'), '/memory?tab=projects');
});
test('profile return rejects foreign routes, URL syntax tricks, hashes and control characters', () => {
  for (const target of ['https://evil.test/memory?tab=people', '//evil.test/memory', '/memory/people/Anna', '/memory/../mail', '/memory#people', '/memory\\evil', '/memory\n?tab=people', 'javascript:alert(1)', '%2Fmemory?tab=people']) {
    assert.equal(returnPath(search(target)), '/memory?tab=people', target);
  }
});
test('profile return rejects invalid or duplicated navigation state', () => {
  for (const target of ['/memory?tab=mail', '/memory?tab=people&tab=projects', '/memory?tab=people&page=0', '/memory?tab=people&page=-1', '/memory?tab=people&page=1.5', '/memory?tab=people&page=999999999999999999999', '/memory?tab=people&q=a&q=b']) {
    assert.equal(returnPath(search(target)), '/memory?tab=people', target);
  }
  assert.equal(returnPath('?return_to=%2Fmemory%3Ftab%3Dprojects&return_to=%2Fmemory%3Ftab%3Dpeople', 'project'), '/memory?tab=projects');
});
test('profile return restores central search and known directory filters', () => {
  assert.equal(returnPath(search('/memory?tab=search&q=Termin&page=2')), '/memory?tab=search&q=Termin&page=2');
  assert.equal(returnPath(search('/memory?tab=people&people=review&q=Anna&page=3')), '/memory?tab=people&q=Anna&page=3&people=review');
  for (const tab of ['areas','topics','topic-files','organizations','places','decisions','documents']) assert.equal(returnPath(search(`/memory?tab=${tab}`)), `/memory?tab=${tab}`);
  assert.equal(returnPath(search('/memory?tab=people&view=status')), '/memory?tab=people&view=status');
  assert.equal(returnPath(search('/memory?tab=people&view=support')), '/memory?tab=people&view=support');
});
test('profile return bounds searches and validates known auxiliary filters', () => {
  assert.equal(returnPath(search(`/memory?tab=people&q=${'a'.repeat(501)}`)), '/memory?tab=people');
  for (const suffix of ['people=evil', 'people=review&people=all', 'view=admin', 'view=status&view=support', 'q=%0Aevil']) assert.equal(returnPath(search(`/memory?tab=projects&${suffix}`)), '/memory?tab=people');
});
test('profile return restores the selected area and infers the areas tab for existing links', () => {
  for (const area of ['work','personal','health','finance','other']) assert.equal(returnPath(search(`/memory?area=${area}`)), `/memory?tab=areas&area=${area}`);
  assert.equal(returnPath(search('/memory?tab=areas&area=health&q=Termin&page=2')), '/memory?tab=areas&q=Termin&page=2&area=health');
});
test('profile return refuses unknown, injected or duplicate area navigation', () => {
  for (const area of ['admin','https://evil.test','%2F%2Fevil.test','work%0Aevil','work&area=health']) assert.equal(returnPath(search(`/memory?area=${area}`)), '/memory?tab=people');
});
