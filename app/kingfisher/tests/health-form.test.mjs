import assert from 'node:assert/strict';
import {existsSync} from 'node:fs';
import {test} from 'node:test';

async function helpers() {
  assert.ok(existsSync(new URL('../src/healthObservationForm.ts', import.meta.url)), 'Dated own-health form is missing');
  return import('../src/healthObservationForm.ts');
}
const input = changes => ({own:true,metric:'Gewicht',value:'072,50',unit:'kg',localTime:'2023-07-02T09:30',offset:'+02:00',note:'Eigene Waage',...changes});

test('explicit own confirmation, literal value and visible offset survive preview', async()=>{
  const {healthPayload} = await helpers();
  assert.deepEqual(healthPayload(input()), {subject:'self',metric:'Gewicht',value:'072,50',unit:'kg',observed_at:'2023-07-02T09:30:00+02:00',note:'Eigene Waage'});
  assert.throws(()=>healthPayload(input({own:false})), /eigene/);
});

test('invalid or ambiguous dates/values do not silently normalize', async()=>{
  const {healthPayload} = await helpers();
  for(const change of [{localTime:'2023-02-30T09:30'}, {offset:''}, {offset:'+26:00'}, {value:'1e6'}, {unit:' '}, {metric:' '}, {note:'\u0000'}])
    assert.throws(()=>healthPayload(input(change)));
});

test('retries use one nonce until confirmed success; changed data gets a new nonce', async()=>{
  const {HealthSaveRequest, healthPayload} = await helpers();
  let n=0;
  const request = new HealthSaveRequest(()=>`request-${++n}`);
  const first = request.for(healthPayload(input()));
  assert.equal(request.for(healthPayload(input())).request_id, first.request_id);
  assert.notEqual(request.for(healthPayload(input({value:'73'}))).request_id,first.request_id);
  request.done();
  assert.equal(request.for(healthPayload(input())).request_id,'request-3');
});

test('a correction preserves original clock and offset instead of changing it to device time', async()=>{
  const {healthFormFromObservation,healthPayload} = await helpers();
  const original={subject:'self',metric:'Wert',value:'7.20',unit:'mg/l',observed_at:'2021-01-02T23:59:42-04:00',note:'Original'};
  const form=healthFormFromObservation(original);
  assert.equal(form.own,false);
  assert.deepEqual(healthPayload({...form,own:true}),original);
});

test('device-time suggestion leaves repeated DST hour undecided and rejects a nonexistent hour',async()=>{
  const {deviceOffsets}=await helpers();const before=process.env.TZ;
  try {
    process.env.TZ='Europe/Berlin';
    assert.deepEqual(deviceOffsets('2026-07-01T09:30'),['+02:00']);
    assert.deepEqual(new Set(deviceOffsets('2026-10-25T02:30')),new Set(['+02:00','+01:00']));
    assert.deepEqual(deviceOffsets('2026-03-29T02:30'),[]);
  } finally {if(before===undefined)delete process.env.TZ;else process.env.TZ=before;}
});

test('original UTC suffix and six fractional digits survive a value-only correction',async()=>{
  const {healthFormFromObservation,healthPayload}=await helpers();
  const original={subject:'self',metric:'Wert',value:'7.20',unit:'mg/l',observed_at:'2021-01-02T23:59:42.000100Z',note:'Original'};
  assert.deepEqual(healthPayload({...healthFormFromObservation(original),own:true}),original);
});
