import {chromium} from '/Users/sorenkube/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({headless:true}),root=import.meta.dirname;
const report={scope:'Actual React connection and subsequent refresh; intercepted synthetic HTTP only',checks:[]};
const endpoint='http://host.docker.internal:11434/v1';
try{
 for(const mode of ['success','readiness-failed','reload-failed','locality-unverified']){
  const page=await browser.newPage();page.setDefaultTimeout(8000);
  const errors=[],consoleErrors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(['error','warning'].includes(m.type()))consoleErrors.push(m.text());});
  let saved='missing:12b',failRead=false;
  function setup(){return {settings:{provider:'ollama',model:saved,endpoint},status:{provider:'ollama',model:saved,endpoint,lokale_ki:{zustand:saved==='missing:12b'?'fehlt':'bereit',kurz:`Status ${saved}`,satz:`Hinweis ${saved}`,modell:saved,lokal:true,erreichbar:true,endpunkt:endpoint,installiert:['qwen3.5:9b','other:9b'],cloud:[]}}};}
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url()),path=url.pathname;
   if(url.hostname!=='127.0.0.1'){await route.abort();return;}
   if(!path.startsWith('/api/')){await route.continue();return;}
   await new Promise(resolve=>setTimeout(resolve,100));
   let payload;
   if(req.method()!=='GET'){
    writes.push([req.method(),path,req.postDataJSON()]);
    if(path==='/api/v1/models/roles/antwort'){
     assert.deepEqual(req.postDataJSON(),{modell:'qwen3.5:9b',cloud:false,local_only:true});
     payload={rollen:[{rolle:'antwort',wirksam:{modell:'qwen3.5:9b',lokal:mode==='locality-unverified'?null:true}}]};
    }else if(path==='/api/v1/setup'){
     saved=req.postDataJSON().model;payload=setup();
    }else if(path==='/api/v1/setup/test/modell')payload={ok:mode!=='readiness-failed'};
    else throw Error(`Unexpected write ${path}`);
   }else if(path==='/api/v1/setup'){
    if(failRead){await route.fulfill({status:503,json:{detail:'Synthetic read failure'}});return;}
    payload=setup();
   }else if(path==='/api/v1/models/stand')payload=setup().status.lokale_ki;
   else if(path==='/api/v1/models/roles')payload={rollen:[],ollama_cloud:{modelle:[]}};
   else if(path==='/api/v1/memory/automation')payload={state:'paused',requested:false,pending:0};
   else if(path==='/api/v1/system')payload={art:'rechner',name:'Testrechner',geraet:'Rechner',mac_helfer:false};
   else throw Error(`Unexpected read ${path}`);
   await route.fulfill({json:payload});
  });
  await page.goto('http://127.0.0.1:18762');
  await page.getByText('Hinweis missing:12b',{exact:true}).waitFor();
  await page.getByRole('combobox').selectOption('qwen3.5:9b');
  await page.getByRole('textbox').waitFor({state:'hidden'});
  if(mode==='reload-failed'){
   failRead=true;
   await page.getByRole('button',{name:'Erneut suchen',exact:true}).click();
   await page.getByText('Status gerade nicht erreichbar',{exact:true}).waitFor();
   assert.equal(await page.getByRole('combobox').inputValue(),'qwen3.5:9b');
   failRead=false;
  }else{
   await page.getByRole('button',{name:'Speichern und verbinden',exact:true}).click();
   if(mode==='success')await page.getByRole('button',{name:'Zum Gespräch',exact:true}).waitFor();
   else await page.getByText('Antwortverbindung nicht bestätigt',{exact:true}).waitFor();
   if(mode!=='success'){
    assert.equal(await page.getByRole('button',{name:'Zum Gespräch',exact:true}).count(),0);
    assert.equal(await page.getByRole('button',{name:'Sortieren starten',exact:true}).count(),0);
   }
   saved='other:9b';
  }
  const writeCount=writes.length;
  await page.getByRole('button',{name:'Erneut suchen',exact:true}).click();
  await page.getByText('Modelleinrichtung wird geladen …',{exact:true}).waitFor();
  await page.getByText('Modelleinrichtung wird geladen …',{exact:true}).waitFor({state:'hidden'});
  assert.equal(await page.getByRole('combobox').inputValue(),mode==='success'?'other:9b':'qwen3.5:9b');
  assert.equal(writes.length,writeCount);
  assert.deepEqual(writes.map(w=>w.slice(0,2)),mode==='reload-failed'?[]:mode==='locality-unverified'?[['PUT','/api/v1/models/roles/antwort']]:[['PUT','/api/v1/models/roles/antwort'],['PUT','/api/v1/setup'],['POST','/api/v1/setup/test/modell']]);
  assert.deepEqual(errors,[]);
  if(mode==='reload-failed')assert.ok(consoleErrors.every(x=>x.includes('503')));
  else assert.deepEqual(consoleErrors,[]);
  assert.equal(await page.locator('vite-error-overlay').count(),0);
  report.checks.push({mode,passed:true,simulated_writes:writes.map(w=>w.slice(0,2)),console_errors:consoleErrors,actual_backend_calls:false});
  await page.close();
 }
 report.passed=true;
 await writeFile(root+'/connection.json',JSON.stringify(report,null,2)+'\n');
}finally{await browser.close();}
console.log(JSON.stringify(report));
