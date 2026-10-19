import test from 'node:test';
import assert from 'node:assert/strict';
import {boundedLocalContext} from '../lib/local-context.mjs';

test('long local chats retain the exact current prompt and only complete recent turns',()=>{
  const history=[{role:'user',content:'old'.repeat(3000)},{role:'assistant',content:'old reply'},
    {role:'user',content:'recent question'},{role:'assistant',content:'recent reply'},
    {role:'user',content:'Write a short reset email with these exact details: synthetic-password.'}];
  const result=boundedLocalContext(history);
  assert.deepEqual(result.messages,history.slice(2));
  assert.equal(result.omittedMessages,2);
  assert.equal(history.length,5);
  assert.deepEqual(boundedLocalContext(history,150).messages,history.slice(-1));
  assert.throws(()=>boundedLocalContext([{role:'user',content:'x'.repeat(6001)}]),/aktuelle Nachricht/);
});

test('local context has a real UTF-8 byte budget and ignores stale trailing assistants',()=>{
  const current={role:'user',content:'ü'.repeat(100)};
  assert.throws(()=>boundedLocalContext([current],150),/aktuelle Nachricht/);
  assert.deepEqual(boundedLocalContext([current,{role:'assistant',content:'stale'}]).messages,[current]);
  assert.throws(()=>boundedLocalContext([{role:'assistant',content:'orphan'}]),/aktuelle Nachricht/);
});
