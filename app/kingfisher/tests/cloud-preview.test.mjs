import test from 'node:test';
import assert from 'node:assert/strict';
import {prepareCloudPreview} from '../src/cloud-preview.ts';

test('Remaining candidates keep their page even when older pages exist',async()=>{
  const calls=[];
  const result=await prepareCloudPreview(async(purpose,cursor)=>{
    calls.push(cursor);return {count:1000,next_cursor:2000};
  },'bulk',4000);
  assert.deepEqual(calls,[4000]);
  assert.equal(result.cursor,4000);
});

test('Only exhausted bulk pages advance, with at most four metadata requests',async()=>{
  const calls=[];
  const result=await prepareCloudPreview(async(purpose,cursor)=>{
    calls.push(cursor);return {count:0,next_cursor:(cursor??10000)-2000};
  },'bulk');
  assert.deepEqual(calls,[undefined,8000,6000,4000]);
  assert.equal(result.cursor,4000);
  assert.equal(result.preview.next_cursor,2000);
});

test('Stop at first eligible page and never skip a manual quality sample',async()=>{
  const calls=[];
  const request=async(purpose,cursor)=>{
    calls.push(cursor);return {count:cursor?25:0,next_cursor:cursor?null:2000};
  };
  const result=await prepareCloudPreview(request,'bulk');
  assert.deepEqual(calls,[undefined,2000]);
  assert.equal(result.preview.count,25);
  calls.length=0;
  await prepareCloudPreview(request,'pilot');
  assert.deepEqual(calls,[undefined]);
});
