import test from 'node:test';
import assert from 'node:assert/strict';
import {initialSavedTask, savedTaskPayload} from '../src/savedMailWorkflowState.ts';
const view={source_digest:'sha256:'+'b'.repeat(64),fingerprint:'a'.repeat(64),projects:[{id:'p1',name:'Belege'}]};
const item={id:'v1',statement:'Belege prüfen',review_required:true,project_suggestion:{project_id:'p1',name:'Belege'}};
test('historical suggestion stays a review and has no inferred deadline or owner',()=>{
 const draft=initialSavedTask(item,view.projects);
 assert.equal(draft.title,'Aktualität der Bitte prüfen: Belege prüfen');
 const payload=savedTaskPayload(view,draft);
 assert.equal(payload.due,null);assert.equal(payload.waiting_for,null);
 assert.equal(payload.source_digest,view.source_digest);assert.equal(payload.fingerprint,view.fingerprint);
 assert.equal(payload.project_id,'p1');
});
test('closed hinted projects are not preselected and new project is accepted in same payload',()=>{
 const draft=initialSavedTask(item,[]);assert.equal(draft.project,'');
 const payload=savedTaskPayload(view,{...draft,title:'Belege prüfen',project:'new',newProject:' Belegprüfung '});
 assert.equal(payload.new_project_name,'Belegprüfung');assert.equal(payload.project_id,null);
});
test('confirmed source deadline keeps its exact time through visible draft and submission',()=>{
 const source={...item,review_required:false,frist_vorschlag:'2026-11-30T14:30:00+01:00'};
 const draft=initialSavedTask(source,view.projects);
 assert.equal(draft.due,'2026-11-30');
 assert.equal(savedTaskPayload(view,draft).due,'2026-11-30T14:30:00+01:00');
 assert.equal(savedTaskPayload(view,{...draft,due:''}).due,null);
 const changed=new Date(savedTaskPayload(view,{...draft,due:'2026-12-01'}).due);
 assert.equal(changed.getDate(),1);assert.equal(changed.getHours(),23);assert.equal(changed.getMinutes(),59);
});
test('historic and unreviewed deadlines stay empty; a model date cannot override a rejected source date',()=>{
 for(const source of [
  {...item,frist_vorschlag:'2020-01-02T14:30:00+01:00'},
  {...item,review_required:false,frist_vorschlag:null,valid_until:'2026-11-30T23:59:00+01:00'},
 ]){
  const draft=initialSavedTask(source,view.projects);
  assert.equal(draft.due,'');assert.equal(savedTaskPayload(view,draft).due,null);
 }
});
test('explicit waiting person is submitted separately from the source counterparty',()=>{
 const draft=initialSavedTask({...item,person_vorschlag:{name:'Anna Berg',adresse:'anna@example.org'}},[]);
 assert.equal(draft.waiting,'');
 assert.equal(savedTaskPayload(view,{...draft,waiting:' Jonas Keller '}).waiting_for,'Jonas Keller');
});
test('invalid date never silently becomes an undated task',()=>{
 assert.throws(()=>savedTaskPayload(view,{...initialSavedTask(item,[]),due:'2026-02-30'}));
});
