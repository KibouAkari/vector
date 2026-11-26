import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {readFileSync} from 'node:fs';

// Execute the actual indexer with a transaction-aware fixture, without a live DB.
const source = readFileSync(new URL('../lib/project-index.js', import.meta.url), 'utf8')
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, '')
  .replace(/^export\s+/gm, '');

function fixture({failInsert = 0, owned = true} = {}) {
  let visible = ['old searchable knowledge'];
  let pending;
  let inserts = 0;
  let releases = 0;
  const observed = [];
  const client = {
    async query(sql, params) {
      if (sql === 'BEGIN') pending = [...visible];
      else if (/SELECT id FROM project_files/.test(sql)) {
        return {rowCount: owned ? 1 : 0};
      } else if (/DELETE FROM project_file_chunks/.test(sql)) pending = [];
      else if (/INSERT INTO project_file_chunks/.test(sql)) {
        if (++inserts === failInsert) throw new Error('injected write failure');
        pending.push(params[6]);
        // A separate reader sees the committed generation during replacement.
        observed.push([...visible]);
      } else if (sql === 'COMMIT') visible = pending;
      else if (sql === 'ROLLBACK') pending = undefined;
      return {rows: [], rowCount: 0};
    },
    release() { releases++; }
  };
  const db = {query: async () => ({rows: []}), connect: async () => client};
  const api = new Function('crypto', 'db', 'initializeDatabase',
    source + '\nreturn {indexProjectTextFile};')(crypto, db, async () => {});
  return {api, observed, visible: () => visible, releases: () => releases};
}
const text = Array.from({length: 90}, (_, i) => `${i} ${'new evidence '.repeat(10)}`).join('\n');

test('failed replacement retains the complete previous searchable generation', async () => {
  const f = fixture({failInsert: 2});
  await assert.rejects(f.api.indexProjectTextFile({projectId: 'p', fileId: 'f', text}), /injected write failure/);
  assert.deepEqual(f.visible(), ['old searchable knowledge']);
  assert.equal(f.releases(), 1);
});

test('readers see the old generation until every new chunk commits', async () => {
  const f = fixture();
  const count = await f.api.indexProjectTextFile({projectId: 'p', fileId: 'f', text});
  assert.ok(count > 1);
  assert.equal(f.visible().length, count);
  assert.ok(f.observed.every(rows => rows.length === 1 && rows[0] === 'old searchable knowledge'));
  assert.equal(f.releases(), 1);
});

test('a wrong project cannot replace another project file index', async () => {
  const f = fixture({owned: false});
  await assert.rejects(f.api.indexProjectTextFile({projectId: 'wrong', fileId: 'f', text}), /Project file not found/);
  assert.deepEqual(f.visible(), ['old searchable knowledge']);
  assert.equal(f.releases(), 1);
});
