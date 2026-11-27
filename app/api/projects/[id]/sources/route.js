import {getSession} from '../../../../../lib/auth';
import {canAccessProject,canEditProject} from '../../../../../lib/identity';
import {listProjectSources,importProjectSource} from '../../../../../lib/project-sources';
import {readSourceRequest} from '../../../../../lib/source-request.mjs';
import {SourceError} from '../../../../../lib/source-fetch.mjs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
export const maxDuration = 30;
const reply = (body,status=200) => Response.json(body,{status,headers:{'Cache-Control':'private, no-store'}});
export async function GET(request,context) {
  const session = await getSession();
  if (!session) return reply({error:'Unauthorized'},401);
  const {id} = await context.params;
  if (!await canAccessProject(session,id)) return reply({error:'Not found'},404);
  return reply({sources:await listProjectSources(id)});
}
export async function POST(request,context) {
  const session = await getSession();
  if(session?.role==='readonly')return Response.json({error:'READ_ONLY_ACCOUNT'},{status:403});

  if (!session) return reply({error:'Unauthorized'},401);
  const {id} = await context.params;
  if (!await canEditProject(session,id)) return reply({error:'Not found'},404);
  try {
    const input = await readSourceRequest(request);
    const source = await importProjectSource({projectId:id,session,...input});
    return reply({source},source.status === 'fetching' ? 202 : 200);
  } catch (error) {
    const code = error instanceof SourceError ? error.code : 'IMPORT_FAILED';
    const status = code === 'REQUEST_CONFLICT' ? 409 : ['IMPORT_BUSY','SOURCE_LIMIT','RETRY_UNAVAILABLE'].includes(code) ? 429 :
      ['LOCAL_ONLY_PROJECT','ACCESS_REVOKED'].includes(code) ? 403 : code === 'NOT_FOUND' ? 404 :
      ['INVALID_URL','INVALID_REQUEST','BLOCKED_ADDRESS','BLOCKED_REDIRECT'].includes(code) ? 400 : 422;
    return reply({error:'Source import could not be completed.',code},status);
  }
}
