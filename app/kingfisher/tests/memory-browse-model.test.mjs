import assert from 'node:assert/strict';
import {test} from 'node:test';
import {browseState, browseHref, browseMatches, documentNodes, sourceReference} from '../src/MemoryBrowseModel.ts';

const node=(id,kind,label,attributes={})=>({id,kind,label,attributes});
test('memory starts with search; legacy links and bounded directory state remain reachable',()=>{
  assert.equal(browseState('').tab,'search');
  assert.equal(browseState('?people=review').tab,'people');
  assert.equal(browseState('?tab=topics').tab,'topic-files');
  assert.deepEqual(browseState('?tab=people&q=Lea&page=2&people=all'),{tab:'people',q:'Lea',page:2,people:'all'});
  assert.equal(browseState('?tab=unknown&page=-2').page,1);
  assert.equal(browseState('?q='+encodeURIComponent('x'.repeat(600))).q.length,200);
});
test('navigation round trips literal names and directory page without interpreting input as a path',()=>{
  const state={tab:'people',q:'Lea & Max? / #',page:3,people:'people'};
  assert.deepEqual(browseState(browseHref(state).split('?')[1]),state);
  assert.ok(browseHref(state).startsWith('/memory?'));
});
test('search spans source titles and entries while withholding unusable claims',()=>{
  const nodes=[node('person:a','person','Lea Example'),node('episode:e','episode','Lea: Vertrag'),
    node('claim:bad','claim','Lea falsche Behauptung',{usable:false}),node('claim:good','claim','Lea bestätigt',{usable:true})];
  assert.deepEqual(browseMatches(nodes,'lea').map(n=>n.id),['person:a','episode:e','claim:good']);
  assert.deepEqual(browseMatches(nodes,'Lea Vertrag').map(n=>n.id),['episode:e']);
});
test('document list retains original source identity, and references never derive from labels',()=>{
  const nodes=[node('episode:a','episode','Document',{episode_kind:'document'}),node('note:b','document','Note'),node('episode:c','episode','Mail',{episode_kind:'message'})];
  assert.deepEqual(documentNodes(nodes).map(n=>n.id),['episode:a','note:b']);
  assert.deepEqual(sourceReference(nodes[0]),{kind:'episode',id:'a'});
  assert.deepEqual(sourceReference(nodes[1]),{kind:'note',id:'b'});
  assert.equal(sourceReference(node('entity:doc','document','episode:secret')),null);
});
test('legacy area links reload into their selected area and retain it in navigation',()=>{
 const state=browseState('?area=personal');
 assert.equal(state.tab,'areas'); assert.equal(state.area,'personal');
 assert.match(browseHref(state),/area=personal/);
});
test('document list withholds superseded and archived versions',()=>{
 const nodes=[node('episode:old','episode','Old',{episode_kind:'document',source_current:false}),
  node('episode:archived','episode','Archived',{episode_kind:'document',state:'archived'}),
  node('episode:current','episode','Current',{episode_kind:'document',source_current:true})];
 assert.deepEqual(documentNodes(nodes).map(n=>n.id),['episode:current']);
});
