import test from 'node:test';
import assert from 'node:assert/strict';
import {parseBudgetUsd,formatBudgetUsd,sourceProviderLabel,sourceImportModel,mistralBindingCurrent,budgetNotice} from '../src/cloud-budget.ts';

test('budget input converts decimal digits exactly to micro-USD without float billing',()=>{
  for(const [text,expected] of [['0',0],['1,00',1000000],[' 2.15 ',2150000],['0.000001',1],['0,999999',999999],['1000',1000000000]]){
    assert.equal(parseBudgetUsd(text),expected,text);
  }
});

test('blank, negative, nonfinite, scientific, grouped or oversized input never grants money',()=>{
  for(const text of ['', ' ', '-1','NaN','Infinity','1e2','1.234,56','1 000','0.0000001','1000.000001','1001','00','1,']){
    assert.equal(parseBudgetUsd(text),null,text);
  }
});

test('money display is explicitly USD and unknown values do not look like free budget',()=>{
  assert.match(formatBudgetUsd(1000000),/1,00.*USD/);
  assert.match(formatBudgetUsd(1,true),/0,000001.*USD/);
  assert.equal(formatBudgetUsd(undefined),'—');
  assert.equal(formatBudgetUsd(NaN),'—');
});

test('fixed source model is independent from unrelated ordinary cloud chat model',()=>{
  const access={providers:[{id:'mistral',model:'ordinary-chat-model',import_model:'mistral-small-2603'},
    {id:'anthropic',model:'claude-source-model'}]};
  assert.equal(sourceImportModel('mistral',access,'local-chat'),'mistral-small-2603');
  assert.equal(sourceImportModel('anthropic',access,'local-chat'),'claude-source-model');
  assert.equal(sourceImportModel('chatgpt',access,'chatgpt-current'),'chatgpt-current');
  assert.equal(sourceImportModel('mistral',{providers:[{id:'mistral',model:'unprepared'}]},'chatgpt-current'),'');
});

test('job labels use the stored provider and never relabel Mistral as a ChatGPT subscription',()=>{
  assert.equal(sourceProviderLabel('mistral'),'Mistral · EU');
  assert.equal(sourceProviderLabel('anthropic'),'Claude API');
  assert.equal(sourceProviderLabel(undefined),'ChatGPT');
});

test('Mistral resume needs same budget/price review; other providers do not inherit that limit',()=>{
  const budget={budget_id:'budget1',revision:2,price_id:'price1'};
  const job={provider:'mistral',budget_id:'budget1',budget_revision:2,price_id:'price1'};
  assert.equal(mistralBindingCurrent(job,budget),true);
  assert.equal(mistralBindingCurrent(job,{...budget,revision:3}),false);
  assert.equal(mistralBindingCurrent({...job,price_id:'old'},budget),false);
  assert.equal(mistralBindingCurrent(job,null),false);
  assert.equal(mistralBindingCurrent({provider:'anthropic'},null),true);
});

test('uncertain or pending charges are visible and not described as a fresh allowance',()=>{
  assert.match(budgetNotice({reconciliation_required:true,blocked_reason:'budget_uncertain'}),/Abrechnung.*offen/);
  assert.match(budgetNotice({blocked_reason:'budget_busy'}),/reserviert/);
  assert.match(budgetNotice({cap_microusd:0,blocked_reason:'budget_exhausted'}),/nicht freigegeben/);
});
