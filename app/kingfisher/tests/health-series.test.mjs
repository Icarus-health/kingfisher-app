import assert from 'node:assert/strict';
import {test} from 'node:test';
const load=()=>import('../src/healthSeries.ts');
const item=(id,value,observed_at='2023-01-01T12:00:00Z',changes={})=>({id,value,observed_at,metric:'Gewicht',unit:'kg',status:'current',...changes});

test('different units or metrics never become a single curve',async()=>{
  const {healthSeries}=await load();
  assert.equal(healthSeries([item('a','70'),item('b','155',undefined,{unit:'lb'})]),null);
  assert.equal(healthSeries([item('a','70'),item('b','80',undefined,{metric:'Puls'})]),null);
});
test('points use measurement instants and retain original values and offsets',async()=>{
  const {healthSeries}=await load();const series=healthSeries([item('late','072,50','2023-01-02T09:00:00+02:00'),item('early','71','2023-01-01T12:00:00Z')]);
  assert.deepEqual(series.points.map(p=>p.id),['early','late']);
  assert.equal(series.points[1].value,'072,50');assert.equal(series.points[1].observed_at,'2023-01-02T09:00:00+02:00');
  assert.equal(series.points[0].x,0);assert.equal(series.points[1].x,1);
});
test('very large close decimals and negative comma values keep distinct positions',async()=>{
  const {healthSeries}=await load();
  const large=healthSeries([item('a','99999999999999999999999999.01'),item('b','99999999999999999999999999.02')]);
  assert.notEqual(large.points[0].y,large.points[1].y);
  const negative=healthSeries([item('a','-0,5'),item('b','+0.50')]);
  assert.equal(negative.minimum,'-0,5');assert.equal(negative.maximum,'+0.50');
});
test('constant values or equal instants remain finite without inventing a time span',async()=>{
  const {healthSeries}=await load();const series=healthSeries([item('a','70'),item('b','70.00')]);
  assert.ok(series.points.every(p=>p.x===0.5&&p.y===0.5));
});
test('one point, withdrawn status, invalid numbers and invalid dates have no curve',async()=>{
  const {healthSeries}=await load();assert.equal(healthSeries([item('a','70')]),null);
  for(const changes of [{status:'excluded'},{value:'NaN'},{observed_at:'unknown'}])
    assert.equal(healthSeries([item('a','70'),{...item('b','71'),...changes}]),null);
});

test('sub-millisecond measurement instants remain ordered and horizontally distinct',async()=>{
  const {healthSeries}=await load();const series=healthSeries([
    item('newer','71','2023-01-01T12:00:00.000002Z'),
    item('older','70','2023-01-01T13:00:00.000001+01:00')]);
  assert.deepEqual(series.points.map(p=>p.id),['older','newer']);
  assert.equal(series.points[0].x,0);assert.equal(series.points[1].x,1);
});
