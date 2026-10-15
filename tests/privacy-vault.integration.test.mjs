import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {readFileSync} from 'node:fs';
import pg from 'pg';
import {literalReplace} from '../lib/privacy-review-core.mjs';

const url=new URL(process.env.DATABASE_URL || 'postgres://unconfigured');
if(process.env.CI!=='true' || !['localhost','127.0.0.1'].includes(url.hostname) || url.pathname!=='/vector_ci') {
  throw new Error('Privacy vault integration requires isolated CI PostgreSQL.');
}

test('actual vault upsert promotes credentials, preserves ciphertext and never downgrades',async()=>{
  const db=new pg.Client({connectionString:process.env.DATABASE_URL});
  await db.connect();
  try {
    // Session-local table shadows the real vault: exercise production SQL and
    // encryption with synthetic data without modifying persistent user records.
    await db.query(`CREATE TEMP TABLE privacy_vault (
      id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL,placeholder TEXT NOT NULL,
      value_type TEXT NOT NULL,encrypted_value TEXT NOT NULL,
      created_at TIMESTAMPTZ DEFAULT NOW(),UNIQUE(conversation_id,placeholder))`);
    const source=readFileSync(new URL('../lib/privacy-vault.js',import.meta.url),'utf8')
      .replace(/^import\s[\s\S]*?from\s+['"][^'"]+['"];\s*/gm,'').replace(/^export\s+/gm,'');
    const api=new Function('crypto','db','initializeDatabase','literalReplace',source+'\nreturn {savePrivacyMappings,getPrivacyMappings};')(
      crypto,db,async()=>{},literalReplace);
    const mapping={placeholder:'<EMAIL_A1B2C3>',value:'synthetic@example.invalid',type:'EMAIL'};
    const save=entry=>api.savePrivacyMappings({conversationId:'ci-private-conversation',mappings:[entry]});
    await save(mapping);
    const original=(await db.query('SELECT encrypted_value FROM privacy_vault')).rows[0].encrypted_value;
    await save({...mapping,type:'PASSWORD',value:'must-not-overwrite-original'});
    let stored=(await api.getPrivacyMappings('ci-private-conversation'))[0];
    assert.equal(stored.type,'PASSWORD');assert.equal(stored.value,mapping.value);
    assert.equal((await db.query('SELECT encrypted_value FROM privacy_vault')).rows[0].encrypted_value,original);
    await save(mapping);
    stored=(await api.getPrivacyMappings('ci-private-conversation'))[0];
    assert.equal(stored.type,'PASSWORD');assert.equal(stored.value,mapping.value);
  } finally {await db.end();}
});
