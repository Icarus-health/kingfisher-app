import test from 'node:test';
import assert from 'node:assert/strict';
import {cloudIssueText} from '../src/cloud-issues.ts';

test('category failure distinguishes the completed basic classification',()=>{
  const text=cloudIssueText({stage:'categories',code:'unsupported_source'});
  assert.match(text,/Themen und Personen/);
  assert.match(text,/Grundeinordnung bleibt erhalten/);
});

test('missing or repeated entity evidence has specific readable explanation',()=>{
  assert.match(cloudIssueText({stage:'categories',code:'invalid_entity_evidence',reason:'entity_missing'}),/Originalstelle fehlt/);
  assert.match(cloudIssueText({stage:'categories',code:'invalid_entity_evidence',reason:'entity_ambiguous'}),/mehrfach/);
});

test('unknown codes and reasons never echo arbitrary provider content',()=>{
  const text=cloudIssueText({stage:'categories',code:'private key',reason:'private model reply'});
  assert.doesNotMatch(text,/private/);
  assert.match(text,/Originalmail/);
});

test('source limit does not claim all rejected sources are too long',()=>{
  assert.match(cloudIssueText({stage:'source',code:'unsupported_source'}),/unvollständig/);
});
