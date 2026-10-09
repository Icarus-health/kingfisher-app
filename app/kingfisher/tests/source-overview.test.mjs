import assert from 'node:assert/strict';
import {test} from 'node:test';
import {buildSourceOverview} from '../src/sourceOverviewRows.ts';
const at=Date.parse('2026-10-09T12:00:00Z');
const slot=(data,failed=false)=>({data,failed,checkedAt:at});
const folder=(extra={})=>({folder:'INBOX',inventory_complete:true,total:100,captured:10,duplicates:2,filtered:3,
  pending:84,failed:1,live_pending:4,live_failed:1,analyzed:5,analysis_failed:1,deferred:0,excluded:0,
  categorized:4,categories_pending:8,categories_failed:0,...extra});
const account=(extra={})=>({account_id:'mail-1',label:'Privat',connected:true,started:true,paused:false,
  folders:[folder()],error:null,scope:'INBOX',attachments_supported:false,...extra});
const state=(extra={})=>({intake:slot({accounts:[account()],background_paused:true}),
  integrations:slot({mail_accounts:[],calendar_sources:[]}),
  schedule:slot({mail_status:{'mail-1':{last_success:'2026-10-08T10:00:00Z',last_failure:'unavailable'}}}),...extra});
const text=row=>[row.status,row.warning,...row.details].join(' ');

test('mail inventory, captured mail and classification stay distinct and scoped',()=>{
  const row=buildSourceOverview(state(),at).find(r=>r.id==='mail:mail-1');
  assert.ok(row);assert.match(text(row),/12.*aufgenommen oder wiedererkannt/);
  assert.match(text(row),/100.*gezählt/);assert.match(text(row),/5.*Einordnung/);
  assert.match(text(row),/3.*ausgelassen/);assert.match(text(row),/4.*neue Mails/);
  assert.match(text(row),/pausiert/);assert.doesNotMatch(text(row),/vollständig|aktuell|Alle.*gelesen/);
  assert.equal(row.lastSuccess,'2026-10-08T10:00:00Z');assert.match(text(row),/letzte.*fehlgeschlagen/i);
});
test('partial inventory never promotes counted subset to total mailbox size',()=>{
  const row=buildSourceOverview(state({intake:slot({accounts:[account({folders:[folder({inventory_complete:false})]})]})}),at)[0];
  assert.match(text(row),/Gesamtumfang.*noch nicht bekannt/);assert.doesNotMatch(text(row),/100.*gezählt/);
});
test('failed intake read retains previous accounts and counters as last-known, not absent',()=>{
  const row=buildSourceOverview(state({intake:slot({accounts:[account()]},true)}),at)[0];
  assert.ok(row.stale);assert.match(text(row),/letzten bekannten Stand|Letzter bekannter Stand/);
  assert.match(text(row),/12.*aufgenommen/);assert.doesNotMatch(text(row),/gelöscht|Alle.*gelesen|Stand ist aktuell/);
});
test('external calendars are configuration, never proof of successful synchronization',()=>{
  const rows=buildSourceOverview(state({intake:slot({accounts:[]}),integrations:slot({mail_accounts:[],calendar_sources:[
    {id:'cal-1',label:'Arbeit',kind:'google',enabled:true,configured:true,secret_present:true},
    {id:'cal-2',label:'Alt',kind:'ical',enabled:false,configured:true,secret_present:false}]})}),at);
  const row=rows.find(r=>r.id==='calendar:cal-1');assert.ok(row);assert.equal(row.lastSuccess,null);
  assert.match(text(row),/kein bestätigter Abgleich/i);assert.doesNotMatch(text(row),/keine Termine|Zugang synchronisiert|Abgleich bestätigt/);
  assert.match(text(rows.find(r=>r.id==='calendar:cal-2')),/ausgeschaltet/);
});
test('Mac calendar permission, worker availability, range and snapshot age all constrain coverage',()=>{
  const mac={enabled:true,selected:['a','b','c'],calendars:[{id:'a',name:'Privat'},{id:'b',name:'Arbeit'},{id:'c',name:'Praxis'}],
    status:'granted',online:true,error:'',event_count:0,snapshot_complete:true,
    synced_at:'2026-10-09T11:59:00Z',range_from:'2026-10-01T00:00:00Z',range_to:'2026-11-01T00:00:00Z'};
  for(const patch of [{status:'denied'},{online:false},{snapshot_complete:false},{snapshot_complete:undefined},
      {synced_at:'2026-10-09T11:50:00Z'},{synced_at:'2026-10-09T13:00:00Z'},{range_from:null}]){
    const row=buildSourceOverview(state({mac:slot({...mac,...patch})}),at).find(r=>r.id==='mac');
    assert.ok(row);assert.doesNotMatch(text(row),/Abgleich bestätigt|keine Termine|Alle Termine/);
  }
  const row=buildSourceOverview(state({mac:slot(mac)}),at).find(r=>r.id==='mac');
  assert.match(text(row),/Abgleich bestätigt/);assert.match(text(row),/Privat.*Arbeit.*Praxis/);
  assert.match(text(row),/0.*Termine.*Zeitfenster/);assert.doesNotMatch(text(row),/keine Termine|gesamte.*Kalender/);
});
test('folder partial failure preserves last successful run and existing file states',()=>{
  const data={enabled:true,root_id:'root',folder:'/synthetic/inbox',seen_at:'2026-10-09T11:59:00Z',running:true,
    synced_at:'2026-10-08T12:00:00Z',last_run:{recorded:1,duplicates:0,changed:0,removed:0,errors:['private raw error']},
    files:[{id:'x',filename:'Private file name',state:'raw'},{id:'y',filename:'Other private',state:'ignored'}]};
  const row=buildSourceOverview(state({documents:slot(data)}),at).find(r=>r.id==='documents');
  assert.equal(row.lastSuccess,data.synced_at);assert.match(text(row),/letzte.*nicht vollständig/i);
  assert.match(text(row),/1.*aufgenommen.*1.*ausgenommen/);
  assert.doesNotMatch(text(row),/private raw error|Private file name|gelöscht/);
  const stale=buildSourceOverview(state({documents:slot(data,true)}),at).find(r=>r.id==='documents');
  assert.ok(stale.stale);assert.match(text(stale),/letzten bekannten Stand|Letzter bekannter Stand/);
});
test('unknown dates or no previous success remain unknown rather than substituted by read time',()=>{
  const rows=buildSourceOverview(state({schedule:slot({mail_status:{'mail-1':{last_success:'bad-date'}}}),
    mac:slot({enabled:false,selected:[],calendars:[],synced_at:null})}),at);
  assert.equal(rows.find(r=>r.id==='mail:mail-1').lastSuccess,null);
  assert.equal(rows.find(r=>r.id==='mac').lastSuccess,null);
});

test('pausing mail intake does not hide a known intake problem or leak its raw error',()=>{
  const row=buildSourceOverview(state({intake:slot({background_paused:true,accounts:[account({error:'inventory_unavailable: private server detail'})]})}),at)[0];
  assert.match(row.status,/pausiert/);assert.match(row.warning || '',/Bei der Aufnahme ist ein Problem aufgetreten/);
  assert.doesNotMatch(text(row),/private server detail|inventory_unavailable/);
});
