import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {readFileSync} from 'node:fs';

// Execute the actual indexer with a transaction-aware fixture, without a live DB.
const source = readFileSync(new URL('../lib/project-index.js', import.meta.url), 'utf8')
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, '')
  .replace(/^export\s+/gm, '');

function fixture({
  failInsert = 0,
  owned = true,
  failInitialization = false,
  beforeInsert = async () => {}
} = {}) {
  let visible = ['old searchable knowledge'];
  let pending;
  let inserts = 0;
  let releases = 0;
  let initializationQueries = 0;
  let databaseInitializations = 0;
  let shouldFailInitialization = failInitialization;
  const observed = [];
  const client = {
    async query(sql, params) {
      if (sql === 'BEGIN') pending = [...visible];
      else if (/SELECT id FROM project_files/.test(sql)) {
        return {rowCount: owned ? 1 : 0};
      } else if (/DELETE FROM project_file_chunks/.test(sql)) pending = [];
      else if (/INSERT INTO project_file_chunks/.test(sql)) {
        await beforeInsert();
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
  const db = {
    async query(sql) {
      if (/^\s*(ALTER|CREATE)/i.test(sql)) {
        initializationQueries++;
        if (shouldFailInitialization) {
          shouldFailInitialization = false;
          throw new Error('injected schema initialization failure');
        }
        return {rows: []};
      }
      if (/SELECT\s+c\.file_id/i.test(sql)) {
        return {rows: visible.map(content => ({content}))};
      }
      return {rows: []};
    },
    connect: async () => client
  };
  const api = new Function('crypto', 'db', 'initializeDatabase',
    source + '\nreturn {initializeProjectIndex, indexProjectTextFile, searchProjectChunks};')(
    crypto, db, async () => {databaseInitializations++;});
  return {
    api,
    observed,
    visible: () => visible,
    releases: () => releases,
    initializationQueries: () => initializationQueries,
    databaseInitializations: () => databaseInitializations
  };
}
const text = Array.from({length: 90}, (_, i) => `${i} ${'new evidence '.repeat(10)}`).join('\n');

test('concurrent schema setup shares one promise and retries after failure', async () => {
  const f = fixture({failInitialization: true});
  await assert.rejects(f.api.initializeProjectIndex(), /injected schema initialization failure/);
  const failedAttempts = f.initializationQueries();
  await Promise.all([
    f.api.initializeProjectIndex(),
    f.api.initializeProjectIndex()
  ]);
  const successfulAttempts = f.initializationQueries() - failedAttempts;
  const completedAttempts = f.initializationQueries();
  assert.ok(successfulAttempts > 1);
  assert.equal(f.databaseInitializations(), 2);
  await f.api.initializeProjectIndex();
  assert.equal(f.initializationQueries(), completedAttempts);
  assert.equal(f.databaseInitializations(), 2);
});

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

test('search during a paused replacement does not rerun schema initialization', async () => {
  let signalInsert;
  let resumeInsert;
  const insertStarted = new Promise(resolve => { signalInsert = resolve; });
  const insertGate = new Promise(resolve => { resumeInsert = resolve; });
  const f = fixture({beforeInsert: async () => {
    signalInsert();
    await insertGate;
  }});

  const replacement = f.api.indexProjectTextFile({
    projectId: 'p',
    fileId: 'f',
    text
  });
  await insertStarted;
  const initializedQueries = f.initializationQueries();
  try {
    const results = await f.api.searchProjectChunks({
      projectId: 'p',
      query: 'searchable knowledge'
    });
    assert.deepEqual(results.map(result => result.content), ['old searchable knowledge']);
    assert.equal(f.initializationQueries(), initializedQueries);
  } finally {
    resumeInsert();
    await replacement;
  }
});

test('a wrong project cannot replace another project file index', async () => {
  const f = fixture({owned: false});
  await assert.rejects(f.api.indexProjectTextFile({projectId: 'wrong', fileId: 'f', text}), /Project file not found/);
  assert.deepEqual(f.visible(), ['old searchable knowledge']);
  assert.equal(f.releases(), 1);
});
