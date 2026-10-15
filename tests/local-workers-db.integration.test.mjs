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
