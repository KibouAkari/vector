import {getSession} from '../../../../lib/auth';
import {db,initializeDatabase} from '../../../../lib/db';
import {listUsageCalls} from '../../../../lib/usage-ledger.mjs';
export const runtime='nodejs';export const dynamic='force-dynamic';
const reply=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'private, no-store'}});
export async function GET(request){
 const session=await getSession();if(!session)return reply({error:'Unauthorized'},401);
 try{await initializeDatabase();return reply(await listUsageCalls(db,session.userId,{after:new URL(request.url).searchParams.get('after')}));}
 catch(error){return reply({error:error.message==='INVALID_CURSOR'?'INVALID_CURSOR':'USAGE_UNAVAILABLE'},error.message==='INVALID_CURSOR'?400:503);}
}
