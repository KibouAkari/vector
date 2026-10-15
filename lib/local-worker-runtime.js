import {db} from './db';
import {runLocalWorker} from './local-worker-core.mjs';

// Session-level lock shared by all Vector web/worker processes. Never queue while
// holding a pool connection. Ollama also enforces one loaded model/request.
const LOCK = '6194261933202610';
export async function withLocalWorkerSlot(execute) {
  const client = await db.connect();
  let locked = false;
  let discard = false;
  try {
    const result = await client.query('SELECT pg_try_advisory_lock($1::bigint) AS locked', [LOCK]);
    locked = result.rows[0]?.locked === true;
    if (!locked) throw new Error('Local worker busy; continue with existing evidence instead of recursively retrying.');
    return await execute();
  } finally {
    if (locked) {
      try {
        const result = await client.query('SELECT pg_advisory_unlock($1::bigint) AS unlocked', [LOCK]);
        discard = result.rows[0]?.unlocked !== true;
      } catch { discard = true; }
    }
    client.release(discard);
  }
}

export function executeLocalWorker(args, context) {
  return runLocalWorker(args, context, {exclusive: withLocalWorkerSlot});
}
