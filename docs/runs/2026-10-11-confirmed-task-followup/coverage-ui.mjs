import {chromium} from '/Users/sorenkube/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const root=import.meta.dirname, browser=await chromium.launch({headless:true});
const report={scope:'Actual Today components; explicit synthetic partial_failures fixture on real backend response',errors:[]};
try{
 const page=await browser.newPage({viewport:{width:1100,height:850},locale:'de-DE'});
 page.on('pageerror',e=>report.errors.push(e.message));
 const message='Bei einigen verknüpften Quellen ließ sich nicht sicher einordnen, ob sie zu einem Mailverlauf gehören.';
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());if(url.hostname!=='127.0.0.1'){await route.abort();return;}
  if(url.pathname==='/api/v1/morning-briefing'){
   const response=await route.fetch(),body=await response.json();body.partial_failures=[{section:'source_review',message}];body.post_ausstehend=false;
   await route.fulfill({response,json:body});return;
  }await route.continue();
 });
 await page.goto('http://127.0.0.1:18765');
 await page.getByRole('heading',{name:'Braucht dich',exact:true}).waitFor();
 const notice=page.locator('.today-attention').getByRole('status');
 await notice.getByText(message,{exact:false}).waitFor();
 assert.equal(await notice.getByRole('link',{name:'Aufgaben prüfen →',exact:true}).getAttribute('href'),'/vorhaben?view=mine');
 const status=page.getByRole('region',{name:'Stand deines Überblicks'});
 assert.equal(await status.getByRole('link',{name:'Aufgaben prüfen →',exact:true}).getAttribute('href'),'/vorhaben?view=mine');
 assert.equal(await status.getByRole('link',{name:'Quellen prüfen →',exact:true}).count(),0);
 assert.deepEqual(report.errors,[]);report.visible=true;report.correct_task_action=true;
 await page.screenshot({path:root+'/task-coverage.png',fullPage:true});
 await writeFile(root+'/task-coverage-ui-proof.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}finally{await browser.close();}
