import {chromium} from '/Users/sorenkube/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
const root=import.meta.dirname,seed=JSON.parse(await readFile(root+'/task-seed.json','utf8'));
const report={scope:'Actual TodayOverview, TodayTaskActions and ProfileSource against isolated synthetic SQLite backend',browser:'Browser plugin not available; bundled Playwright',errors:[],writes:[],reads:[]};
const browser=await chromium.launch({headless:true});
try {
 const page=await browser.newPage({viewport:{width:1100,height:850},locale:'de-DE'});
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('console',m=>{if(['error','warning'].includes(m.type()))report.errors.push(m.text());});
 await page.route('**/*',async route=>{const req=route.request(),url=new URL(req.url());
   if(url.hostname!=='127.0.0.1'){await route.abort();return;}
   if(url.pathname.startsWith('/api/')&&req.method()!=='GET')report.writes.push({method:req.method(),path:url.pathname});
   if(url.pathname.startsWith('/api/')&&req.method()==='GET')report.reads.push(url.pathname);await route.continue();});
 await page.goto('http://127.0.0.1:18765');
 await page.getByRole('heading',{name:'Braucht dich',exact:true}).waitFor();
 const card=page.locator('.today-attention-item').filter({has:page.getByRole('heading',{name:'Künstlichen Testbericht prüfen',exact:true})});
 await card.waitFor();
 await card.getByText('Seit dem Festhalten der Aufgabe wurde eine weitere Nachricht im Verlauf erfasst. Bitte prüfen, ob die Aufgabe noch so gilt.',{exact:true}).waitFor();
 await card.getByRole('button',{name:'Weitere Nachricht im Verlauf ansehen',exact:true}).click();
 await card.getByText('Absage: Der künstliche Testauftrag entfällt.',{exact:true}).waitFor();
 const source=card.getByRole('region',{name:'Profilquelle'});
 assert.equal(await source.getByRole('button',{name:/ausschließen|verwerfen|zulassen|berichtigen/i}).count(),0);
 assert.equal(await source.locator('select,input,textarea').count(),0);
 await page.screenshot({path:root+'/task-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:root+'/task-mobile.png',fullPage:true});
 report.mobile_horizontal_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 assert.equal(report.mobile_horizontal_overflow,false);
 const taskResponse=await page.request.get('http://127.0.0.1:18765/api/v1/tasks?all=true');
 assert.equal(taskResponse.status(),200);const tasks=await taskResponse.json();
 const list=Array.isArray(tasks)?tasks:tasks.tasks;
 assert.deepEqual(list.find(t=>t.id===seed.task_id),seed.task_before);
 assert.deepEqual(report.writes,[]);assert.deepEqual(report.errors,[]);
 assert.equal(report.reads.some(path=>path.startsWith('/api/v1/akten/quellen/')),false); report.new_message_visible=true;report.read_only_followup=true;report.task_unchanged=true;report.completed=true;
 await writeFile(root+'/task-ui-proof.json',JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
}catch(error){report.completed=false;report.failure=String(error);await writeFile(root+'/task-ui-proof.json',JSON.stringify(report,null,2)+'\n');throw error;}
finally{await browser.close();}
