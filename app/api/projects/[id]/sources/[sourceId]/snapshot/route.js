import {getSession} from '../../../../../../../lib/auth';
import {canAccessProject} from '../../../../../../../lib/identity';
import {db} from '../../../../../../../lib/db';
import {initializeProjectSources} from '../../../../../../../lib/project-sources';
import {decryptFileBuffer} from '../../../../../../../lib/project-files';
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export async function GET(request,context) {
  const session = await getSession();
  if (!session) return new Response('Unauthorized',{status:401});
  const {id,sourceId} = await context.params;
  if (!await canAccessProject(session,id)) return new Response('Not found',{status:404});
  await initializeProjectSources();
  const result = await db.query(`SELECT raw_snapshot FROM project_sources
    WHERE id=$1 AND project_id=$2 AND status IN ('indexed','partial')`,[sourceId,id]);
  if (!result.rowCount || !result.rows[0].raw_snapshot) return new Response('Not found',{status:404});
  return new Response(decryptFileBuffer(result.rows[0].raw_snapshot),{headers:{
    'Content-Type':'application/octet-stream',
    'Content-Disposition':'attachment; filename="source-snapshot.bin"',
    'X-Content-Type-Options':'nosniff',
    'Content-Security-Policy':"default-src 'none'; sandbox",
    'Cache-Control':'private, no-store'
  }});
}
