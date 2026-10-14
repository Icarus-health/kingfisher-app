import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {renderToStaticMarkup} from 'react-dom/server';
import {createElement} from 'react';
const server=await createServer({cacheDir:`/private/tmp/kingfisher-ui-test-cache-${process.pid}-memory-search-view.test`,root:fileURLToPath(new URL('..',import.meta.url)),server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {MemorySearch}=await server.ssrLoadModule('/src/MemorySearch.tsx');
const props={query:'',page:1,onQueryChange:()=>{},onPageChange:()=>{},onOpen:()=>{}};
test('document read failure has retry and never claims an empty collection',()=>{
 const result=renderToStaticMarkup(createElement(MemorySearch,{...props,graph:null,documents:true,graphError:true,onGraphRetry:()=>{}}));
 assert.match(result,/Erneut laden/); assert.doesNotMatch(result,/Noch keine Dokumente gespeichert/);
});
test('unloaded graph is not a zero-count loaded document directory',()=>{
 const result=renderToStaticMarkup(createElement(MemorySearch,{...props,graph:null,documents:true}));
 assert.doesNotMatch(result,/0 Einträge|Noch keine Dokumente gespeichert/);
});
test('document notes offer original reading without unsupported classification controls',()=>{
 const graph={nodes:[{id:'note:synthetic',kind:'document',label:'Meeting note',attributes:{}}],edges:[]};
 const result=renderToStaticMarkup(createElement(MemorySearch,{...props,graph,documents:true}));
 assert.match(result,/Originalquelle öffnen/); assert.doesNotMatch(result,/Zuordnung &amp; Korrektur/);
});
