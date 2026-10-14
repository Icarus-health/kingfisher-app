import assert from 'node:assert/strict';
import {test} from 'node:test';
import * as layout from '../src/calendarLayout.ts';
const date=(h,m=0)=>new Date(2026,9,14,h,m).toISOString();
test('week time layout clips overnight events and separates overlapping events without title deduplication',()=>{
 const events=[{uid:'a',start:date(9),end:date(11),summary:'Same'}, {uid:'b',start:date(10),end:date(12),summary:'Same'}, {uid:'c',start:date(12),end:date(13)}, {uid:'overnight',start:new Date(2026,9,13,22).toISOString(),end:date(2)}, {uid:'all',start:date(0),end:new Date(2026,9,15).toISOString(),all_day:true}];
 const result=layout.calendarDayLayout(events,new Date(2026,9,14));
 assert.equal(result.length,4);assert.equal(result.find(x=>x.event.uid==='overnight').startMinute,0);assert.equal(result.find(x=>x.event.uid==='overnight').endMinute,120);
 assert.equal(result.find(x=>x.event.uid==='a').columns,2);assert.notEqual(result.find(x=>x.event.uid==='a').column,result.find(x=>x.event.uid==='b').column);assert.equal(result.find(x=>x.event.uid==='c').columns,1);
});
test('calendar day and agenda ranges navigate from focus with exclusive local boundaries across DST',()=>{
 const day=new Date(2027,2,28);
 const range=layout.calendarWorkspaceWindow(day,'Tag');assert.equal(range.from.getDate(),28);assert.equal(range.until.getDate(),29);assert.equal((range.until-range.from)/3600000,24+(range.until.getTimezoneOffset()-range.from.getTimezoneOffset())/60);
 const list=layout.calendarWorkspaceWindow(new Date(2030,0,1),'Liste');assert.equal(list.from.getFullYear(),2030);assert.equal(list.until.getDate(),8);
});
test('repeated clock hours remain separate overlap lanes and midnight end is exclusive',()=>{
 const previousZone=process.env.TZ;process.env.TZ='Europe/Berlin';
 try {const day=new Date(2026,9,25);const events=[{uid:'first',start:'2026-10-25T02:30:00+02:00',end:'2026-10-25T02:50:00+02:00'},{uid:'second',start:'2026-10-25T02:30:00+01:00',end:'2026-10-25T02:50:00+01:00'},{uid:'before',start:'2026-10-24T22:00:00+02:00',end:'2026-10-25T00:00:00+02:00'}];
 const result=layout.calendarDayLayout(events,day);assert.equal(result.length,2);assert.equal(result[0].columns,2);assert.notEqual(result[0].column,result[1].column);
 } finally {if(previousZone===undefined)delete process.env.TZ;else process.env.TZ=previousZone;}
});
test('source colors and identity stay stable for same title and proven copies stay selectable',()=>{
 assert.equal(layout.calendarColor('a'),layout.calendarColor('a'));
 const a={uid:'a:1',source_id:'a',summary:'Title',start:date(9)},b={uid:'b:1',source_id:'b',summary:'Title',start:date(9)};
 assert.notEqual(layout.calendarEventKey(a),layout.calendarEventKey(b));
 assert.deepEqual(layout.calendarVisibleEvents([a,b],new Set(['b'])),[b]);
 const copy={...a,source_copies:[{uid:'a:1',source_id:'a',source_label:'A'},{uid:'b:1',source_id:'b',source_label:'B'}]};assert.equal(layout.calendarVisibleEvents([copy],new Set(['b']))[0],copy);
});
test('physical Mac calendar view keys filter independently while mirror action IDs remain canonical',async()=>{
 const {calendarSourceVersions}=await import('../src/calendarRange.ts');
 const privateEvent={uid:'mac-calendar:p',source_id:'mac-calendar',view_source_id:'mac-calendar:private',start:date(9)};
 const work={uid:'google:w',source_id:'google',start:date(10),source_copies:[
  {uid:'google:w',source_id:'google',source_label:'Google',view_source_id:'google'},
  {uid:'mac-calendar:w',source_id:'mac-calendar',source_label:'Arbeit',view_source_id:'mac-calendar:work'}]};
 assert.deepEqual(layout.calendarVisibleEvents([privateEvent,work],new Set(['mac-calendar:work'])),[work]);
 assert.deepEqual(layout.calendarVisibleEvents([privateEvent,work],new Set(['mac-calendar:private'])),[privateEvent]);
 assert.deepEqual(calendarSourceVersions(work).map(copy=>copy.source_id),['google','mac-calendar']);
});
test('autumn clock crossing splits into exact wall intervals and separates the real overlap',()=>{
 const previousZone=process.env.TZ;process.env.TZ='Europe/Berlin';
 try {
  const crossing={uid:'cross-clock',start:'2026-10-25T02:50:00+02:00',end:'2026-10-25T02:10:00+01:00'};
  const overlapping={uid:'real-overlap',start:'2026-10-25T02:00:00+01:00',end:'2026-10-25T02:20:00+01:00'};
  const result=layout.calendarDayLayout([crossing,overlapping],new Date(2026,9,25));
  const parts=result.filter(p=>p.event===crossing);
  assert.deepEqual(parts.map(p=>[p.startMinute,p.endMinute]).sort((a,b)=>a[0]-b[0]),[[120,130],[170,180]]);
  const second=parts.find(p=>p.startMinute===120), other=result.find(p=>p.event===overlapping);
  assert.notEqual(second.column,other.column);assert.equal(second.columns,2);
  assert.equal(parts.reduce((sum,p)=>sum+(Date.parse(p.segmentEnd)-Date.parse(p.segmentStart))/60000,0),20);
  assert.equal(second.continuesBefore,true);assert.equal(parts.find(p=>p.startMinute===170).continuesAfter,true);
  assert.equal(second.timeLabel,'02:00–02:10 UTC+01:00');assert.equal(parts.find(p=>p.startMinute===170).timeLabel,'02:50–03:00 UTC+02:00');
  assert.equal(new Set(parts.map(layout.calendarPlacementKey)).size,2);
 } finally {if(previousZone===undefined)delete process.env.TZ;else process.env.TZ=previousZone;}
});
test('spring clock crossing leaves the skipped wall hour empty',()=>{
 const previousZone=process.env.TZ;process.env.TZ='Europe/Berlin';
 try {
  const event={uid:'spring',start:'2027-03-28T01:50:00+01:00',end:'2027-03-28T03:10:00+02:00'};
  const result=layout.calendarDayLayout([event],new Date(2027,2,28));
  assert.deepEqual(result.map(p=>[p.startMinute,p.endMinute]),[[110,120],[180,190]]);
  assert.equal(result.reduce((sum,p)=>sum+(Date.parse(p.segmentEnd)-Date.parse(p.segmentStart))/60000,0),20);
 } finally {if(previousZone===undefined)delete process.env.TZ;else process.env.TZ=previousZone;}
});
test('DST segments clip a multiday event at exact midnight boundaries',()=>{
 const previousZone=process.env.TZ;process.env.TZ='Europe/Berlin';
 try {
  const event={uid:'overnight-dst',start:'2026-10-24T23:50:00+02:00',end:'2026-10-26T00:10:00+01:00'};
  const day=layout.calendarDayLayout([event],new Date(2026,9,25));
  assert.deepEqual(day.map(p=>[p.startMinute,p.endMinute]).sort((a,b)=>a[0]-b[0]),[[0,180],[120,1440]]);
  assert.equal(day.every(p=>p.continuesBefore&&p.continuesAfter),true);
  assert.equal(day.reduce((sum,p)=>sum+(Date.parse(p.segmentEnd)-Date.parse(p.segmentStart))/3600000,0),25);
  const next=layout.calendarDayLayout([event],new Date(2026,9,26));
  assert.deepEqual(next.map(p=>[p.startMinute,p.endMinute]),[[0,10]]);
  assert.equal(layout.calendarDayLayout([{...event,end:'2026-10-26T00:00:00+01:00'}],new Date(2026,9,26)).length,0);
 } finally {if(previousZone===undefined)delete process.env.TZ;else process.env.TZ=previousZone;}
});
