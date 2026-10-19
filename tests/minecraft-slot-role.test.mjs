import test from 'node:test';
import assert from 'node:assert/strict';
import {destination,verifyPrivateEndpoint,assertGrants,prepareRole,ROLE} from '../scripts/lib/minecraft-slot-role.mjs';

test('role setup accepts only the fixed private database or explicit disposable fixture',()=>{
  assert.equal(destination('postgresql://a:b@vector-postgres/vector').hostname,'vector-postgres');
  assert.equal(destination('postgresql://a:b@127.0.0.1:5433/vector_admission_fixture',true).port,'5433');
  for(const dsn of ['https://a:b@vector-postgres/vector','postgresql://a:b@outside/vector',
    'postgresql://a:b@vector-postgres:5434/vector','postgresql://a:b@vector-postgres/',
    'postgresql://a@vector-postgres/vector','postgresql://a:b@vector-postgres/vector#fragment'])assert.throws(()=>destination(dsn));
  assert.throws(()=>destination('postgresql://a:b@vector-postgres/vector',true));
  assert.throws(()=>destination('postgresql://a:b@127.0.0.1:5433/vector_admission_fixture?host=outside',true));
  assert.throws(()=>destination('postgresql://a:b@127.0.0.1:5433/vector_admission_fixture'));
});

const endpoint=()=>({container:'vector-postgres',container_id:'a'.repeat(64),network:'vector-internal',
  aliases:['vector-postgres','postgres'],addresses:['172.23.0.4']});
const aliasDsn='postgresql://synthetic:synthetic@postgres/vector';

test('inspected Compose alias is accepted only when every DNS address matches the current private container',async()=>{
  const calls=[];
  const result=await verifyPrivateEndpoint(aliasDsn,endpoint(),async(host,options)=>{
    calls.push([host,options]);return [{address:'172.23.0.4',family:4}];
  });
  assert.equal(result.hostname,'postgres');assert.deepEqual(calls,[['postgres',{all:true}]]);
  for(const host of ['vector-postgres','172.23.0.4'])
    await verifyPrivateEndpoint(aliasDsn.replace('@postgres/','@'+host+'/'),endpoint(),async()=>[{address:'172.23.0.4'}]);
});

test('unknown aliases, public addresses, wrong container/network and missing proof stop before DNS',async()=>{
  for(const change of [{container:'other'},{container_id:'short'},{network:'other'},
    {addresses:['203.0.113.4']},{addresses:['172.99.0.4']},{addresses:[]},{aliases:['other']}]){
    let lookedUp=false;
    await assert.rejects(verifyPrivateEndpoint(aliasDsn,{...endpoint(),...change},async()=>{
      lookedUp=true;return [{address:'172.23.0.4'}];
    }),/ROLE_PRIVATE_/);
    assert.equal(lookedUp,false);
  }
  await assert.rejects(verifyPrivateEndpoint(aliasDsn,null,async()=>[]),/PROOF_REQUIRED/);
});

test('DNS errors, empty, mixed and changed addresses are refused before role/database work',async()=>{
  for(const rows of [[],[{address:'172.23.0.9'}],[{address:'172.23.0.4'},{address:'203.0.113.4'}]])
    await assert.rejects(verifyPrivateEndpoint(aliasDsn,endpoint(),async()=>rows),/DNS_MISMATCH/);
  await assert.rejects(verifyPrivateEndpoint(aliasDsn,endpoint(),async()=>{throw Error('synthetic');}),/DNS_UNAVAILABLE/);
  let connections=0;
  await assert.rejects(prepareRole({dsn:aliasDsn,owner:'a'.repeat(32),password:'b'.repeat(64),endpoint:endpoint(),
    lookup:async()=>[{address:'172.23.0.9'}],connect:()=>{connections++;}}),/DNS_MISMATCH/);
  assert.equal(connections,0);
});

test('query overrides and unexpected ports remain blocked for a valid inspected alias',async()=>{
  for(const dsn of [aliasDsn+'?host=outside',aliasDsn+'?port=5434',aliasDsn+'?options=x',
    aliasDsn.replace('@postgres/','@postgres:5434/')]){
    let lookedUp=false;
    await assert.rejects(verifyPrivateEndpoint(dsn,endpoint(),async()=>{lookedUp=true;return [];}),/PRIVATE_DATABASE_REQUIRED/);
    assert.equal(lookedUp,false);
  }
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
  assert.equal(calls,0);assert.equal(ROLE,'vector_minecraft_slot');
});
