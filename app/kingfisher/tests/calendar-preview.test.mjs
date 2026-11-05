import assert from 'node:assert/strict';
import {test} from 'node:test';
import {calendarPreview} from '../src/calendarPreview.ts';

const a={uid:'a:one',source_id:'a',source_label:'Erster Kalender',summary:'Erster Termin',start:'2026-11-05T10:00:00Z',end:'2026-11-05T11:00:00Z',all_day:false,location:''};
const b={...a,uid:'b:two',source_id:'b',source_label:'Zweiter Kalender',summary:'Zweiter Termin'};
const view=(items,failed=[])=>({items,configured:true,errors:failed.length?['Offline']:[],failed_sources:failed,read_context:'context-a',read_at:'2026-11-04T10:00:00Z'});

test('only the failed source retains its original timestamp across repeated failures',()=>{
 const previous=view([a,b]);const next={...view([{...b,summary:'Aktuell'}],['a']),read_at:'2026-11-04T11:00:00Z'};
 const merged=calendarPreview(previous,next,true);assert.equal(merged.items.length,2);
 const old=merged.items.find(x=>x.uid===a.uid);assert.equal(old.stale_since,previous.read_at);assert.equal(merged.items.find(x=>x.uid===b.uid).stale_since,undefined);
 const again=calendarPreview(merged,{...next,read_at:'2026-11-04T12:00:00Z'},true);assert.equal(again.items.find(x=>x.uid===a.uid).stale_since,previous.read_at);
 assert.equal(previous.items[0].stale_since,undefined,'no mutation');
});
test('successful empty source, changed authority, missing authority and changed range clear old rows',()=>{
 const previous=view([a,b]);
 for(const [next,sameRange] of [[view([]),true],[{...view([],['a']),read_context:'other'},true],[{...view([],['a']),read_context:undefined},true],[view([],['a']),false]])assert.deepEqual(calendarPreview(previous,next,sameRange).items,[]);
});
test('a cached mirror keeps only failed-source references and cannot inherit a fresh action destination',()=>{
 const mirror={...a,source_copies:[{uid:a.uid,source_id:'a',source_label:'Erster'},{uid:'b:mirror',source_id:'b',source_label:'Zweiter'}]};
 const merged=calendarPreview(view([mirror]),view([],['b']),true);
 assert.equal(merged.items.length,1);assert.equal(merged.items[0].uid,'b:mirror');assert.equal(merged.items[0].source_id,'b');assert.equal(merged.items[0].stale_since,'2026-11-04T10:00:00Z');
 assert.ok(!merged.items[0].source_copies?.some(c=>c.source_id==='a'));
});
test('a freshly read proven mirror is not duplicated by its old failed copy',()=>{
 const mirror={...a,source_copies:[{uid:a.uid,source_id:'a',source_label:'Erster'},{uid:'b:mirror',source_id:'b',source_label:'Zweiter'}]};
 const current={...a,uid:'b:mirror',source_id:'b'};
 assert.deepEqual(calendarPreview(view([mirror]),view([current],['a']),true).items,[current]);
});
test('different recurring occurrences survive and stale data is replaced on recovery',()=>{
 const later={...a,start:'2026-11-06T10:00:00Z',end:'2026-11-06T11:00:00Z'};
 const cached=calendarPreview(view([a,later]),view([],['a']),true);assert.equal(cached.items.length,2);
 assert.deepEqual(calendarPreview(cached,view([later]),true).items,[later]);
});
