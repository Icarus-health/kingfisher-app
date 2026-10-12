import {chromium} from '/Users/sorenkube/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const root=import.meta.dirname;
const phase=process.argv[2]??'check';
const browser=await chromium.launch({headless:true});
const report={scope:'Actual LocalModelSettings React component; synthetic HTTP responses, no personal app/model/cloud requests',browser:'Browser plugin not available; bundled Playwright',phase,cases:[],errors:[]};
const endpoint='http://host.docker.internal:11434/v1';
const cases=[['fehlt',true],['nicht_erreichbar',true],['keins',true],['bereit',false],['cloud',false]];
try {
 for(const [state,expected] of cases){
  const page=await browser.newPage({viewport:{width:1100,height:850}});
  page.on('pageerror',e=>report.errors.push(e.message));
  page.on('console',msg=>{if(['error','warning'].includes(msg.type()))report.errors.push(msg.text());});
  page.setDefaultTimeout(6000);
  const writes=[];
  const local=state!=='cloud';
  const model=state==='keins'?null:state==='bereit'?'qwen3.5:9b':state==='cloud'?'cloud-answer':'missing:12b';
  const installed=state==='nicht_erreichbar'?[]:['qwen3.5:9b'];
  const lage={zustand:state,kurz:`Status ${state}`,satz:`Hinweis ${state}`,modell:model,lokal:local,erreichbar:state!=='nicht_erreichbar',endpunkt:endpoint,installiert:installed,cloud:[]};
  await page.route('**/*',async route=>{
   const req=route.request(),url=new URL(req.url());
   if(url.hostname!=='127.0.0.1'){await route.abort();return;}
   if(!url.pathname.startsWith('/api/')){await route.continue();return;}
   if(req.method()!=='GET')writes.push([req.method(),url.pathname]);
   const payloads={
    '/api/v1/setup':{settings:{provider:local?'ollama':'openrouter',model:model??'',endpoint},status:{provider:local?'ollama':'openrouter',model,endpoint,lokale_ki:lage}},
    '/api/v1/models/stand':lage,
    '/api/v1/models/roles':{rollen:[],ollama_cloud:{modelle:[]}},
    '/api/v1/system':{art:'rechner',name:'Testrechner',geraet:'Rechner',mac_helfer:false},
   };
   assert.ok(url.pathname in payloads,`Unexpected route ${url.pathname}`);
   await route.fulfill({json:payloads[url.pathname]});
  });
  await page.goto('http://127.0.0.1:18762');
  assert.equal(await page.title(),'Kingfisher lokale KI – künstlicher Bediencheck');
  await page.getByText(`Status ${state}`,{exact:true}).waitFor();
  const actual=await page.getByRole('form',{name:'Lokales Modell einrichten'}).isVisible();
  const row={state,expected_expanded:expected,actual_expanded:actual,passed:actual===expected};
  if(actual){
   await page.getByText(state==='keins'?'Installiertes Modell gefunden. Ein Klick verbindet es mit Kingfisher.':`Hinweis ${state}`,{exact:true}).waitFor();
   await page.getByRole('button',{name:'Schließen',exact:true}).click();
   assert.equal(await page.getByRole('form',{name:'Lokales Modell einrichten'}).isVisible(),false);
   await page.getByRole('button',{name:'Modell verwalten',exact:true}).click();
   await page.getByText(state==='keins'?'Installiertes Modell gefunden. Ein Klick verbindet es mit Kingfisher.':`Hinweis ${state}`,{exact:true}).waitFor();
   row.manual_close_open=true;
   if(state==='fehlt'){
    await page.getByRole('combobox').selectOption('qwen3.5:9b');
    await page.getByRole('textbox').waitFor({state:'hidden'});
    assert.equal(await page.getByRole('combobox').inputValue(),'qwen3.5:9b');
    await page.getByText('Auswahl geändert. Bitte verbinden.',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'Speichern und verbinden',exact:true}).isEnabled(),true);
    row.installed_alternative_selectable=true;
   }
  }
  assert.deepEqual(writes,[]);
  assert.equal(await page.locator('vite-error-overlay').count(),0);
  row.writes=writes;
  await page.screenshot({path:`${root}/${phase}-${state}.png`,fullPage:true});
  if(state==='fehlt'){
   await page.setViewportSize({width:390,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await page.screenshot({path:`${root}/${phase}-mobile.png`,fullPage:true});
   row.mobile_no_horizontal_overflow=true;
  }
  report.cases.push(row);
  await page.close();
 }
 assert.deepEqual(report.errors,[]);
 report.passed=report.cases.every(c=>c.passed);
 await writeFile(`${root}/${phase}.json`,JSON.stringify(report,null,2)+'\n');
 assert.equal(report.passed,true,JSON.stringify(report.cases.filter(c=>!c.passed)));
}finally{await browser.close();}
console.log(JSON.stringify(report));
