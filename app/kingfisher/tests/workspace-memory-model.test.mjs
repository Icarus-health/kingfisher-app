import {test} from 'node:test';
import assert from 'node:assert/strict';
import {coordinatePair,folderDescendants,canonicalSourceId,initials,validateImageFile,batchCategorySave} from '../src/WorkspaceMemoryModel.ts';
test('pins reject empty, infinite and out of range coordinates and accept zero',()=>{
 assert.equal(coordinatePair('','0'),null);assert.equal(coordinatePair('Infinity','1'),null);assert.equal(coordinatePair('91','1'),null);assert.equal(coordinatePair('0','181'),null);
 assert.deepEqual(coordinatePair('0','0'),{lat:0,lng:0});assert.deepEqual(coordinatePair('48,5','7,2'),{lat:48.5,lng:7.2});
});
test('folder subtree remains bounded if corrupt metadata contains a cycle',()=>{
 const folders=[{id:'a',data:{parent_id:'b'}},{id:'b',data:{parent_id:'a'}},{id:'c',data:{parent_id:'a'}},{id:'other',data:{parent_id:null}}];
 assert.deepEqual([...folderDescendants(folders,'a')].sort(),['a','b','c']);
});
test('source keys preserve original identity and distinguish notes from episodes',()=>{
 assert.equal(canonicalSourceId('episode:one'),'episode:one');assert.equal(canonicalSourceId('note:one'),'note:one');assert.equal(canonicalSourceId('one'),'episode:one');
 assert.equal(initials('Lea Sommer <lea@example.test>'),'LS');
});
test('image validation allows only local bounded raster images',()=>{
 assert.equal(validateImageFile({type:'image/png',size:1024}),null);assert.match(validateImageFile({type:'image/svg+xml',size:20}),/PNG/);assert.match(validateImageFile({type:'image/jpeg',size:1048577}),/1 MB/);
});
test('batch saves use preview revisions, preserve other areas and report partial conflicts',async()=>{
 const calls=[];const previews=[{episode_id:'one',revision:'r1',categories:[{id:'health'}],status:'complete'},{episode_id:'two',revision:'r2',categories:[],status:'complete'}];
 const results=await batchCategorySave(previews,'work',async(...args)=>{calls.push(args);if(args[0]==='two')throw Object.assign(Error('stale'),{status:409});return {episode_id:args[0]};});
 assert.deepEqual(calls,[['one',['health','work'],'r1'],['two',['work'],'r2']]);assert.equal(results[0].ok,true);assert.equal(results[1].ok,false);assert.match(results[1].message,/geändert/);
});
test('excluded or revisionless previews never write',async()=>{
 let calls=0;const results=await batchCategorySave([{episode_id:'one',revision:null,categories:[],status:'complete'},{episode_id:'two',revision:'r2',categories:[],status:'excluded'}],'work',async()=>{calls++;});
 assert.equal(calls,0);assert.ok(results.every(r=>!r.ok));
});
import {contactDateFromGraph,folderSourcesFromGraph} from '../src/WorkspaceMemoryModel.ts';
test('mentions do not establish contact and missing occurrence date stays unknown',()=>{
 const graph={generated_at:'2026-10-14T15:00:00Z',nodes:[{id:'episode:one',attributes:{occurred_at:'2026-10-14T12:00:00Z'}},{id:'episode:two',attributes:{recorded_at:'2026-10-14T12:00:00Z'}}],edges:[{source:'person:p',target:'episode:one',relation:'participated_in'},{source:'person:p',target:'episode:two',relation:'participated_in',actual_contact:true}]};
 assert.equal(contactDateFromGraph(graph,'person:p'),'unbekannt');graph.edges[0].actual_contact=true;assert.match(contactDateFromGraph(graph,'person:p'),/2026/);
});
test('future events and withdrawn sources do not become last contact',()=>{
 const graph={generated_at:'2026-10-14T15:00:00Z',nodes:[{id:'episode:future',attributes:{episode_kind:'event',occurred_at:'2026-10-15T12:00:00Z'}},{id:'episode:ignored',attributes:{state:'ignored',occurred_at:'2026-10-14T12:00:00Z'}},{id:'episode:old',attributes:{source_current:false,occurred_at:'2026-10-14T12:00:00Z'}}],edges:['future','ignored','old'].map(id=>({source:'person:p',target:`episode:${id}`,relation:'participated_in',actual_contact:true}))};
 assert.equal(contactDateFromGraph(graph,'person:p'),'unbekannt');graph.nodes.push({id:'episode:past',attributes:{episode_kind:'event',occurred_at:'2026-10-13T12:00:00Z'}});graph.edges.push({source:'person:p',target:'episode:past',relation:'participated_in',actual_contact:true});assert.equal(contactDateFromGraph(graph,'person:p'),'13.10.2026');
});
test('document preview retains source keys and excludes ignored, superseded and archived originals',()=>{
 const nodes=[{id:'note:n',kind:'document',label:'Note',attributes:{}},{id:'episode:e',kind:'episode',label:'File',attributes:{episode_kind:'document'}},...['ignored','archived'].map(state=>({id:`episode:${state}`,kind:'episode',label:state,attributes:{episode_kind:'document',state}})),{id:'episode:old',kind:'episode',label:'Old',attributes:{episode_kind:'document',source_current:false}},{id:'project:p',kind:'project',label:'Project',attributes:{area:'Arbeit'}}];
 const result=folderSourcesFromGraph({nodes,edges:[{source:'note:n',target:'project:p',relation:'belongs_to'}]});assert.deepEqual(result.map(r=>r.id),['note:n','episode:e']);assert.equal(result[0].kind,'note');assert.equal(result[0].project,'project:p');assert.equal(result[0].projectName,'Project');assert.deepEqual(result[0].areas,['Arbeit']);
});
