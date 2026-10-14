import assert from 'node:assert/strict';
import {test} from 'node:test';
import {displayLabel} from '../src/displayIdentity.ts';
test('matching enclosing name quotes are display-only and preserve mail identity',()=>{
  assert.deepEqual(displayLabel("'Lea Example' <lea@example.invalid>"),{name:'Lea Example',detail:'lea@example.invalid'});
  assert.equal(displayLabel("O'Connor <lea@example.invalid>").name,"O'Connor");
  assert.equal(displayLabel("'Unmatched <lea@example.invalid>").name,"'Unmatched");
});
