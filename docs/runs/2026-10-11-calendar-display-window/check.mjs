import {chromium} from '/Users/sorenkube/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
const root=import.meta.dirname;
const browser=await chromium.launch({headless:true});
const report={scope:'Actual CalendarPage; synthetic responses only; no personal app access',browser:'Browser plugin not available; bundled Playwright',errors:[],writes:[],cases:[]};
try {
 const page=await browser.newPage({viewport:{width:1100,height:850}});
 page.on('pageerror',e=>report.errors.push(e.message));
 page.on('console',m=>{if(['error','warning'].includes(m.type()))report.errors.push(m.text());});
 let showWarning=true;
 const warning='2 Kalendereinträge ohne eindeutige Zeitangabe werden in diesem Zeitraum nicht angezeigt.';
 await page.route('**/*',async route=>{
  const request=route.request(), url=new URL(request.url());
  if(url.hostname!=='127.0.0.1'){await route.abort();return;}
  if(!url.pathname.startsWith('/api/')){await route.continue();return;}
  if(request.method()!=='GET')report.writes.push([request.method(),url.pathname]);
  if(url.pathname==='/api/v1/calendar')await route.fulfill({json:{items:[],errors:[],warnings:showWarning?[warning]:[],configured:true}});
  else if(url.pathname==='/api/v1/calendar-actions/sources')await route.fulfill({json:{sources:[]}});
  else throw new Error(`Unexpected API ${url.pathname}`);
 });
 await page.goto('http://127.0.0.1:18763');
 await page.getByRole('heading',{name:'Kalender',exact:true}).waitFor();
 assert.equal(await page.title(),'Kingfisher Kalender - künstliche Prüfung');
 await page.getByText(warning,{exact:true}).waitFor();
 assert.equal(await page.getByRole('alert').count(),0);
 await page.getByRole('button',{name:'Liste',exact:true}).click();
 await page.getByText('Nächste sieben Tage',{exact:true}).waitFor();
 await page.getByText(warning,{exact:true}).waitFor();
 await page.screenshot({path:root+'/desktop.png',fullPage:true});
 report.cases.push({name:'warning-visible-as-status-without-provider-error',passed:true});
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.getByText(warning,{exact:true}).isVisible(),true);
 await page.screenshot({path:root+'/mobile.png',fullPage:true});
 report.mobile_horizontal_overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 showWarning=false;
 await page.getByRole('button',{name:'Ansicht aktualisieren',exact:true}).click();
 await page.getByText(warning,{exact:true}).waitFor({state:'hidden'});
 await page.getByText('Keine Termine in diesem Zeitraum.',{exact:true}).waitFor();
 report.cases.push({name:'refresh-clears-old-warning',passed:true});
 assert.equal(await page.locator('vite-error-overlay').count(),0);
 assert.deepEqual(report.errors,[]);assert.deepEqual(report.writes,[]);
 await writeFile(root+'/verification.json',JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify(report));
}finally{await browser.close();}
