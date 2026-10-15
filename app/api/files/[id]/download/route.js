import { getSession } from '../../../../../lib/auth';
import { canAccessProject } from '../../../../../lib/identity';
import { db } from '../../../../../lib/db';
import { initializeFileDatabase, readEncryptedFile } from '../../../../../lib/project-files';
import { projectDownloadDisposition } from '../../../../../lib/project-file-view.mjs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request, context) {
  const session = await getSession();
  if (!session) return new Response('Unauthorized', {status: 401});
  const { id } = await context.params;
  await initializeFileDatabase();
  const result = await db.query('SELECT * FROM project_files WHERE id = $1', [id]);
  const file = result.rows[0];
  if (!file || !await canAccessProject(session, file.project_id)) {
    return new Response('Not found', {status: 404});
  }
  const buffer = await readEncryptedFile(file);
  return new Response(buffer, {
    headers: {
      'Content-Type': 'application/octet-stream',
      'Content-Length': String(buffer.length),
      'Content-Disposition': projectDownloadDisposition(file.original_name),
      'Cache-Control': 'private, no-store',
      'X-Content-Type-Options': 'nosniff',
      'Content-Security-Policy': 'sandbox'
    }
  });
}
