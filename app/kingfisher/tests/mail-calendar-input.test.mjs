import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {build} from 'vite';

const compiled = await build({configFile:false, logLevel:'silent', build:{write:false, minify:false,
  lib:{entry:fileURLToPath(new URL('../src/mailCalendarInput.ts', import.meta.url)),formats:['cjs']}}});
const code = [compiled].flat().flatMap(result => result.output).find(item => item.type === 'chunk').code;
const module = {exports:{}};
new Function('require','module','exports',code)(createRequire(import.meta.url),module,module.exports);
const {splitIsoOffset, buildIsoOffset, offsetOptions} = module.exports;

test('split and rebuild unchanged ISO keeps original seconds, milliseconds and offset', () => {
  const original = '2026-10-09T13:24:37.456+02:00';
  const parts = splitIsoOffset(original);
  assert.deepEqual(parts, {local:'2026-10-09T13:24', offset:'+02:00'});
  assert.equal(buildIsoOffset(parts.local, parts.offset, original), original);
});

test('edited local time uses explicit chosen offset and never device-local conversion', () => {
  assert.equal(buildIsoOffset('2026-10-09T14:24', '+01:00', '2026-10-09T13:24:37+02:00'),
    '2026-10-09T14:24:00+01:00');
});

test('missing, malformed, or invalid local/offset values fail closed', () => {
  assert.throws(() => buildIsoOffset('2026-10-09T13:24', '', null), /Zeitzone|Offset/i);
  assert.throws(() => buildIsoOffset('2026-10-09T13:24', 'local', null), /Zeitzone|Offset/i);
  assert.throws(() => buildIsoOffset('2026-02-30T13:24', '+01:00', null), /Zeit|Datum/i);
  assert.throws(() => splitIsoOffset('2026-10-09T13:24:00'), /Offset|Zeitzone/i);
});

test('offset choices include UTC, MEZ, MESZ and preserve a source-specific offset', () => {
  assert.deepEqual(offsetOptions('+05:45'), [
    {value:'Z',label:'UTC'}, {value:'+01:00',label:'MEZ (UTC+01:00)'},
    {value:'+02:00',label:'MESZ (UTC+02:00)'}, {value:'+05:45',label:'Vorhandener Offset (+05:45)'},
  ]);
  assert.deepEqual(splitIsoOffset('2026-10-09T13:24:37+17:00'), {local:'2026-10-09T13:24',offset:'+17:00'});
});
