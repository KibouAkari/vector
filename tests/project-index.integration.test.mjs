import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {readFileSync} from 'node:fs';
import pg from 'pg';

const url = new URL(process.env.DATABASE_URL || 'postgres://missing');
if (process.env.CI !== 'true' || !['127.0.0.1', 'localhost'].includes(url.hostname)
    || url.pathname !== '/vector_ci') {
  throw new Error('Refusing project index integration tests outside isolated CI.');
}
const source = readFileSync(new URL('../lib/project-index.js', import.meta.url), 'utf8')
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, '')
  .replace(/^export\s+/gm, '');

test('project index replacements on real PostgreSQL', async t => {
  const schema = 'index_fixture_' + crypto.randomBytes(8).toString('hex');
  const admin = new pg.Pool({connectionString: url.toString(), max: 1});
  const pool = new pg.Pool({connectionString: url.toString(), max: 3,
    options: `-c search_path=${schema}`});
  try {
    await admin.query(`CREATE SCHEMA ${schema}`);
    await pool.query(`
      CREATE TABLE projects (id TEXT PRIMARY KEY);
      CREATE TABLE conversations (id TEXT PRIMARY KEY);
      CREATE TABLE tasks (id TEXT PRIMARY KEY);
      CREATE TABLE project_files (id TEXT PRIMARY KEY, project_id TEXT REFERENCES projects(id));
      INSERT INTO projects VALUES ('p'), ('other');
      INSERT INTO project_files VALUES ('f', 'p');
    `);
    let fail = false;
    let observe = false;
    const read = async () => (await pool.query(
      'SELECT content FROM project_file_chunks ORDER BY chunk_index')).rows.map(r => r.content);
    const db = {
      query: (...args) => pool.query(...args),
      async connect() {
        const client = await pool.connect();
        let inserted = 0;
        return {
          release: () => client.release(),
          async query(sql, params) {
            if (/INSERT INTO project_file_chunks/.test(sql)) {
              inserted++;
              if (observe) assert.deepEqual(await read(), ['old knowledge']);
              if (fail && inserted === 2) throw new Error('injected index write failure');
            }
            return client.query(sql, params);
          }
        };
      }
    };
    const api = new Function('crypto', 'db', 'initializeDatabase', source +
      '\nreturn {indexProjectTextFile};')(crypto, db, async () => {});
    const index = (text, projectId = 'p') => api.indexProjectTextFile({projectId, fileId: 'f', text});
    const text = Array.from({length: 90}, (_, i) => `${i} ${'evidence '.repeat(15)}`).join('\n');
    await index('old knowledge');
    await t.test('rollback preserves all old chunks after an interrupted replacement', async () => {
      fail = true;
      observe = true;
      await assert.rejects(index(text), /injected index write failure/);
      assert.deepEqual(await read(), ['old knowledge']);
    });
    await t.test('cross-project replacement is rejected without losing the old index', async () => {
      await assert.rejects(index(text, 'other'), /Project file not found/);
      assert.deepEqual(await read(), ['old knowledge']);
    });
    await t.test('independent readers see no partial replacement', async () => {
      fail = false;
      const count = await index(text);
      assert.ok(count > 1);
      const rows = await read();
      assert.equal(rows.length, count);
      assert.ok(rows.every(row => row.includes('evidence')));
    });
  } finally {
    await pool.end();
    await admin.query(`DROP SCHEMA IF EXISTS ${schema} CASCADE`);
    await admin.end();
  }
});
