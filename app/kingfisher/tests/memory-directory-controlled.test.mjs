import assert from 'node:assert/strict';
import {after,test} from 'node:test';
import {fileURLToPath} from 'node:url';
import {createServer} from 'vite';
import {renderToStaticMarkup} from 'react-dom/server';
import {createElement} from 'react';
import {testCache} from './testcache.mjs';
const server=await createServer({cacheDir:testCache('memory-directory-controlled.test'),root:fileURLToPath(new URL('..',import.meta.url)),server:{middlewareMode:true,watch:null,ws:false,hmr:false},appType:'custom'});
after(()=>server.close());
const {MemoryDirectory}=await server.ssrLoadModule('/src/MemoryDirectory.tsx');
test('restored query displays only matching records, not the unfiltered directory',()=>{
 const nodes=['Lea','Max'].map(label=>({id:label,kind:'person',label,attributes:{}}));
 const result=renderToStaticMarkup(createElement(MemoryDirectory,{nodes,title:'Menschen',query:'Lea',page:1,onOpen:()=>{}}));
 assert.match(result,/Akte öffnen: Lea/); assert.doesNotMatch(result,/Akte öffnen: Max/);
});
test('empty project directory with existing sources asks for assignment rather than reconnection',()=>{
 const result=renderToStaticMarkup(createElement(MemoryDirectory,{nodes:[],title:'Projekte',hasSources:true,onOpen:()=>{}}));
 assert.match(result,/Noch keine Projekte zugeordnet/); assert.doesNotMatch(result,/Quellen verbinden/);
});
