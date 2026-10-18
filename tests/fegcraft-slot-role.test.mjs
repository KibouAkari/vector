import test from 'node:test';
import assert from 'node:assert/strict';
import {destination,assertGrants,prepareRole,ROLE} from '../scripts/lib/fegcraft-slot-role.mjs';

test('role setup accepts only the fixed private database or explicit disposable fixture',()=>{
  assert.equal(destination('postgresql://a:b@vector-postgres/vector').hostname,'vector-postgres');
  assert.equal(destination('postgresql://a:b@127.0.0.1:5433/vector_admission_fixture',true).port,'5433');
  for(const dsn of ['https://a:b@vector-postgres/vector','postgresql://a:b@outside/vector',
    'postgresql://a:b@vector-postgres:5434/vector','postgresql://a:b@vector-postgres/',
    'postgresql://a@vector-postgres/vector','postgresql://a:b@vector-postgres/vector#fragment'])assert.throws(()=>destination(dsn));
  assert.throws(()=>destination('postgresql://a:b@vector-postgres/vector',true));
  assert.throws(()=>destination('postgresql://a:b@127.0.0.1:5433/vector_admission_fixture'));
});

test('effective PUBLIC or direct data/create/admin/foreign grants are refused',()=>{
  assertGrants([{scope:'database',privilege_type:'CONNECT',grant_option:false},
    {scope:'database',privilege_type:'TEMPORARY',grant_option:false},
    {scope:'schema',privilege_type:'USAGE',grant_option:false}]);
  for(const row of [{scope:'database',privilege_type:'CREATE'}, {scope:'schema',privilege_type:'CREATE'},
    {scope:'relation',privilege_type:'SELECT'}, {scope:'column',privilege_type:'SELECT'},
    {scope:'routine',privilege_type:'EXECUTE'},{scope:'security_definer',privilege_type:'EXECUTE'},
    {scope:'foreign_server',privilege_type:'USAGE'}, {scope:'large_object',privilege_type:'SELECT'},
    {scope:'parameter',privilege_type:'SET'},{scope:'future_data',privilege_type:'SELECT'},
    {scope:'database',privilege_type:'CONNECT',grant_option:true}])assert.throws(()=>assertGrants([row]),/UNSAFE/);
});

test('private input format is validated before any database connection',async()=>{
  let calls=0;const connect=()=>{calls++;throw Error('unexpected database access');};
  for(const owner of ['',"';DROP ROLE postgres;--",'a'.repeat(31)])
    await assert.rejects(prepareRole({dsn:'postgresql://a:b@vector-postgres/vector',owner,password:'b'.repeat(64),connect}),/PRIVATE_INPUT/);
  assert.equal(calls,0);assert.equal(ROLE,'vector_fegcraft_slot');
});
