import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {normalizeContainerResources, resourceBytes, resourcePercent, sortedContainers, topContainers} from '../lib/server-resources.mjs';

const fixture = {
  sample:'one-shot', running_count:3,
  containers:[
    {id:'a',name:'game-a',cpu_percent:2,memory_usage_bytes:8*1024**3,memory_percent:12.5},
    {id:'b',name:'worker-b',cpu_percent:230.5,memory_usage_bytes:96*1024**2,memory_percent:75},
    {id:'c',name:'idle-c',cpu_percent:0,memory_usage_bytes:0,pids:0}
  ]
};

test('rankings use absolute memory bytes and retain multicore CPU values and real zeroes', () => {
  const data=normalizeContainerResources(fixture,'2026-01-01T12:00:00Z');
  assert.equal(data.available,true);
  assert.equal(data.runningCount,3);
  assert.equal(topContainers(data.containers,'memory')[0].name,'game-a');
  assert.equal(topContainers(data.containers,'cpu')[0].name,'worker-b');
  assert.equal(resourcePercent(230.5),'230.5%');
  assert.equal(resourcePercent(0),'0%');
  assert.equal(resourceBytes(0),'0 B');
  assert.equal(resourceBytes(8*1024**3),'8 GiB');
  assert.equal(data.containers[2].pids,0);
  assert.deepEqual(data.containers.map(x=>x.name),['game-a','worker-b','idle-c']);
});

test('missing measurements remain unknown instead of becoming healthy zeroes', () => {
  const data=normalizeContainerResources({containers:[
    {name:'missing',cpu_percent:null,memory_usage_bytes:'unknown'},
    {name:'invalid',cpu_percent:NaN,memory_usage_bytes:-2},
    {name:'empty',cpu_percent:'',memory_usage_bytes:Infinity},
    {name:'zero',cpu_percent:0,memory_usage_bytes:0}
  ]},'sample-time');
  assert.equal(data.containers[0].cpuPercent,null);
  assert.equal(data.containers[0].memoryBytes,null);
  assert.deepEqual(topContainers(data.containers,'cpu').map(x=>x.name),['zero']);
  assert.deepEqual(topContainers(data.containers,'memory').map(x=>x.name),['zero']);
  assert.equal(resourceBytes(null),'Unavailable');
  assert.equal(resourcePercent(null),'Unavailable');
  assert.equal(normalizeContainerResources(null,null).available,false);
  assert.equal(normalizeContainerResources({},null).runningCount,null);
  assert.equal(normalizeContainerResources({containers:[],running_count:0},'now').runningCount,0);
});

test('search and sorting preserve the source array and cap rankings at five', () => {
  const rows=normalizeContainerResources(fixture,'now').containers;
  const before=structuredClone(rows);
  assert.deepEqual(sortedContainers(rows,'cpu','WORKER').map(x=>x.name),['worker-b']);
  assert.deepEqual(rows,before);
  const many=Array.from({length:9},(_,i)=>({id:String(i),name:'fixture-'+i,cpuPercent:i,memoryBytes:i}));
  assert.deepEqual(topContainers(many,'cpu').map(x=>x.cpuPercent),[8,7,6,5,4]);
});

function snapshotRoute({session, snapshotFailure=false, resourceFailure=false}) {
  const calls=[];
  const source=readFileSync(new URL('../app/api/server/snapshot/route.js',import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'')
    .replace(/^export\s+/gm,'');
  const GET=new Function('deps',`
    const {getSession,hasFeature,hostSnapshot,hostInspect,normalizeContainerResources}=deps;
    ${source}
    return GET;
  `)({
    getSession:async()=>session,
    hasFeature:(s,f)=>s.role==='owner'||s.features?.[f]===true,
    hostSnapshot:async()=>{
      calls.push('snapshot');
      if(snapshotFailure)throw new Error('private internal host detail');
      return {uptime:'up 5 days',ports:'fixture listener',services:'fixture service'};
    },
    hostInspect:async args=>{
      calls.push(args);
      if(resourceFailure)throw new Error('private internal host detail');
      return fixture;
    },
    normalizeContainerResources
  });
  return {GET,calls};
}

test('anonymous and unauthorized accounts cannot trigger host reads', async () => {
  for(const [session,status] of [[null,401],[{role:'member',features:{}},403]]){
    const {GET,calls}=snapshotRoute({session});
    assert.equal((await GET()).status,status);
    assert.deepEqual(calls,[]);
  }
});

test('authorized snapshots include one-shot resources, preserve host fields and normalize the ports key', async () => {
  for(const session of [{role:'owner'},{role:'member',features:{server:true}}]){
    const {GET,calls}=snapshotRoute({session});
    const response=await GET();
    assert.equal(response.status,200);
    assert.equal(response.headers.get('cache-control'),'no-store');
    const body=await response.json();
    assert.equal(body.ports,'fixture listener');
    assert.equal(body.listeningPorts,'fixture listener');
    assert.equal(body.containerResources.containers.length,3);
    assert.equal(body.containerResources.sample,'one-shot');
    assert.ok(Number.isFinite(Date.parse(body.containerResources.sampledAt)));
    assert.deepEqual(calls,['snapshot',{action:'docker_stats'}]);
  }
});

test('resource failure preserves host information while host failure is reported without internal details', async () => {
  const resources=snapshotRoute({session:{role:'owner'},resourceFailure:true});
  const response=await resources.GET();
  assert.equal(response.status,200);
  const body=await response.json();
  assert.equal(body.uptime,'up 5 days');
  assert.equal(body.containerResources.available,false);
  assert.equal(body.containerResources.runningCount,null);
  assert.ok(!JSON.stringify(body).includes('private internal'));
  const primary=snapshotRoute({session:{role:'owner'},snapshotFailure:true});
  const failed=await primary.GET();
  assert.equal(failed.status,503);
  assert.ok(!(await failed.text()).includes('private internal'));
});
