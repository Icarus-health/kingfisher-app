import {chromium} from '/Users/sorenkube/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const phase=process.argv[2]??'check', root=import.meta.dirname;
const browser=await chromium.launch({headless:true});
const report={phase,scope:'Actual LocalModelSettings with controlled synthetic HTTP; no real model/private data/cloud',browser:'Browser plugin not available; bundled Playwright',cases:[],errors:[]};
const endpoint='http://host.docker.internal:11434/v1';
async function choice(page){
 const mode=await page.getByRole('combobox').inputValue();
 return {model:mode==='__manual__'?await page.getByRole('textbox').inputValue():mode,manual:mode==='__manual__'};
}
try{
 for(const name of ['installed-alternative','typed-name','empty-manual','untouched-config','removed-alternative']){
  const page=await browser.newPage({viewport:{width:1100,height:850}});page.setDefaultTimeout(8000);
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('console',m=>{if(['error','warning'].includes(m.type()))report.errors.push(m.text());});
  let refreshed=false;
  const writes=[];
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(url.hostname!=='127.0.0.1'){await route.abort();return;}
   if(!url.pathname.startsWith('/api/')){await route.continue();return;}
   if(req.method()!=='GET')writes.push([req.method(),url.pathname]);
   const installed=refreshed&&name==='removed-alternative'?[]:['qwen3.5:9b'];
   const saved=refreshed&&name==='untouched-config'?'qwen3.5:9b':'missing:12b';
   const state=saved==='qwen3.5:9b'?'bereit':'fehlt';
   const lage={zustand:state,kurz:`Status ${state}`,satz:`Hinweis ${state}`,modell:saved,lokal:true,erreichbar:true,endpunkt:endpoint,installiert:installed,cloud:[]};
   const payloads={
    '/api/v1/setup':{settings:{provider:'ollama',model:saved,endpoint},status:{provider:'ollama',model:saved,endpoint,lokale_ki:lage}},
    '/api/v1/models/stand':lage,
    '/api/v1/models/roles':{rollen:[],ollama_cloud:{modelle:[]}},
    '/api/v1/system':{art:'rechner',name:'Testrechner',geraet:'Rechner',mac_helfer:false},
   };
   assert.ok(url.pathname in payloads,`Unexpected ${url.pathname}`);
   // Controlled response latency makes the loading transition observable.
   await new Promise(resolve=>setTimeout(resolve,100));
   await route.fulfill({json:payloads[url.pathname]});
  });
  await page.goto('http://127.0.0.1:18762');
  assert.equal(await page.title(),'Kingfisher lokale KI – künstlicher Bediencheck');
  await page.getByText('Hinweis fehlt',{exact:true}).waitFor();
  if(name.includes('alternative')){
   await page.getByRole('combobox').selectOption('qwen3.5:9b');
   await page.getByRole('textbox').waitFor({state:'hidden'});
  }else if(name==='typed-name'||name==='empty-manual'){
   await page.getByRole('textbox').fill(name==='typed-name'?'typed:7b':'');
  }
  const before=await choice(page);
  refreshed=true;
  await page.getByRole('button',{name:'Erneut suchen',exact:true}).click();
  await page.getByText('Modelleinrichtung wird geladen …',{exact:true}).waitFor();
  await page.getByText('Modelleinrichtung wird geladen …',{exact:true}).waitFor({state:'hidden'});
  const actual=await choice(page);
  const expected=name==='untouched-config'?{model:'qwen3.5:9b',manual:false}:name==='removed-alternative'?{model:'qwen3.5:9b',manual:true}:before;
  const row={name,before,expected,actual,passed:JSON.stringify(actual)===JSON.stringify(expected),writes};
  assert.deepEqual(writes,[]);
  assert.equal(await page.locator('vite-error-overlay').count(),0);
  await page.screenshot({path:`${root}/${phase}-${name}.png`,fullPage:true});
  if(name==='installed-alternative'){
   assert.equal(await page.getByRole('button',{name:'Speichern und verbinden',exact:true}).isEnabled(),true);
   await page.setViewportSize({width:390,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await page.screenshot({path:`${root}/${phase}-mobile.png`,fullPage:true});
   row.mobile_no_horizontal_overflow=true;
  }
  if(name==='empty-manual'&&row.passed)assert.equal(await page.getByRole('button',{name:'Speichern und verbinden',exact:true}).isEnabled(),false);
  report.cases.push(row);await page.close();
 }
 assert.deepEqual(report.errors,[]);
 report.passed=report.cases.every(c=>c.passed);
 await writeFile(`${root}/${phase}.json`,JSON.stringify(report,null,2)+'\n');
 assert.equal(report.passed,true,JSON.stringify(report.cases.filter(c=>!c.passed)));
}finally{await browser.close();}
console.log(JSON.stringify(report));
