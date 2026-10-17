import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import pg from 'pg';

test('actual PostgreSQL admission is exclusive across sessions and releases after worker failure',{timeout:15000},async()=>{
  const db = new pg.Pool({connectionString:process.env.DATABASE_URL,max:3,connectionTimeoutMillis:5000});
  const source=readFileSync(new URL('../lib/local-worker-runtime.js',import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'');
  const {withLocalWorkerSlot}=new Function('db',source+'\nreturn {withLocalWorkerSlot};')(db);
  let release;
  let admitted;
  const ready=new Promise(resolve=>{admitted=resolve;});
  const first=withLocalWorkerSlot(async()=>{admitted();return new Promise(resolve=>{release=resolve;});});
  try {
    await Promise.race([ready,first]);
    await assert.rejects(withLocalWorkerSlot(async()=>assert.fail('concurrent work admitted')),/busy/);
    release('finished');assert.equal(await first,'finished');
    await assert.rejects(withLocalWorkerSlot(async()=>{throw Error('worker fixture failed');}),/fixture failed/);
    assert.equal(await withLocalWorkerSlot(async()=>42),42);
  } finally {
    release?.(); await first.catch(()=>{}); await db.end();
  }
});


test('completed native statistics are fresh while in-flight and ordinary duplicates remain reusable',{timeout:15000},async()=>{
  const db=new pg.Pool({connectionString:process.env.DATABASE_URL,max:1,connectionTimeoutMillis:5000});
  const source=readFileSync(new URL('../lib/background-jobs.js',import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'');
  const {findRecentDuplicate}=new Function('db','initializeDatabase',source+'\nreturn {findRecentDuplicate};')(db,async()=>{});
  const id='fresh-stats-'+globalThis.crypto.randomUUID();
  const request={userId:id,conversationId:id,requestHash:id};
  try {
    await findRecentDuplicate(request); // Create/check the actual job schema.
    await db.query(`INSERT INTO agent_jobs(id,user_id,conversation_id,request_hash,status,payload,result)
      VALUES($1,$1,$1,$1,'completed','{}'::jsonb,$2::jsonb)`,[id,JSON.stringify({meta:{model:'vector-local-statistics'}})]);
    assert.equal(await findRecentDuplicate(request),null,'A new read must not replay a completed native result.');
    for(const status of ['queued','running']) {
      await db.query('UPDATE agent_jobs SET status=$2 WHERE id=$1',[id,status]);
      assert.equal((await findRecentDuplicate(request))?.id,id,'In-flight retries must share one job.');
    }
    await db.query("UPDATE agent_jobs SET status='completed',result=$2::jsonb WHERE id=$1",[id,JSON.stringify({meta:{model:'synthetic-text-model'}})]);
    assert.equal((await findRecentDuplicate(request))?.id,id,'Ordinary completion dedup is retained.');
    await db.query("UPDATE agent_jobs SET status='failed' WHERE id=$1",[id]);
    assert.equal(await findRecentDuplicate(request),null);
  } finally {await db.query('DELETE FROM agent_jobs WHERE id=$1',[id]);await db.end();}
});
