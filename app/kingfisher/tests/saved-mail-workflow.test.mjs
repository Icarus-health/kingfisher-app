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
