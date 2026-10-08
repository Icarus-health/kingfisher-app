import {test} from 'node:test';
import assert from 'node:assert/strict';
import {deriveIntakeProgress} from '../src/mailIntakeProgress.ts';
import {einlesenStand} from '../src/Einrichtung/einlesen.ts';
import {lerntZeilen} from '../src/Einrichtung/lernt.ts';

const folder = {folder:'INBOX',inventory_complete:true,total:260,captured:201,duplicates:0,filtered:0,failed:0,pending:59,live_pending:0,analyzed:0,analysis_failed:0,deferred:0,excluded:0,categorized:0,categories_pending:201,categories_failed:0};
const sentence = 'Postfach Probe: Ältere Mails warten auf die Einordnung bereits gespeicherter Quellen. Bereits 201 von 260 Mails gelesen.';
const account = {account_id:'a',label:'Probe',connected:true,started:true,paused:false,error:null,step:'waiting_analysis',scope:'INBOX',history_waiting_for_analysis:true,folders:[folder],stand:{zustand:'wartet',satz:sentence,gelesen:201,gesamt:260,zuletzt:null}};

test('history wait preserves counters and never becomes active capture',()=>{
  const progress=deriveIntakeProgress(account);
  assert.equal(progress.stage,'waiting_analysis');
  assert.equal(progress.processed,201);
  assert.equal(progress.complete,false);
  assert.equal(einlesenStand(account),sentence);
  assert.equal(lerntZeilen({accounts:[account],attachments_supported:false,analysis_active:false},null).find(row=>row.id==='mail')?.text,sentence);
});

test('mailbox pause and inventory retain precedence over history wait',()=>{
  assert.equal(deriveIntakeProgress({...account,paused:true}).stage,'paused');
  assert.equal(deriveIntakeProgress({...account,folders:[{...folder,inventory_complete:false}]}).stage,'inventory');
  assert.match(einlesenStand({...account,paused:true}),/pausiert/);
});

test('new mail pending cannot look current after the entire history is read',()=>{
  const progress=deriveIntakeProgress({...account,history_waiting_for_analysis:false,folders:[{...folder,captured:260,pending:0,analyzed:260,categorized:260,categories_pending:0,live_pending:1}]});
  assert.equal(progress.stage,'capture');
  assert.equal(progress.complete,false);
});

test('new-mail filters and failures remain separate from historical progress',()=>{
  const progress=deriveIntakeProgress({...account,history_waiting_for_analysis:false,folders:[{...folder,live_filtered:4,live_failed:1,live_pending:1}]});
  assert.equal(progress.processed,201);
  assert.equal(progress.liveFiltered,4);
  assert.equal(progress.liveFailed,1);
});


test('setup keeps pending new mail visible after its retry',()=>{
  const sentence='Postfach Probe: Der bisherige Verlauf ist gelesen. Noch eine Mail neu einzulesen.';
  const pending={...account,history_waiting_for_analysis:false,stand:{...account.stand,zustand:'liest',satz:sentence},folders:[{...folder,total:1,captured:1,pending:0,live_pending:1}]};
  assert.equal(einlesenStand(pending),sentence);
});
