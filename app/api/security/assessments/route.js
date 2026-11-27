import {getSession} from '../../../../lib/auth';
import {boundedJson} from '../../../../lib/bounded-json.mjs';
import {listAssessments,changeAssessment} from '../../../../lib/security/store';
import {SecurityInputError} from '../../../../lib/security/evidence.mjs';
export const runtime='nodejs';export const dynamic='force-dynamic';
const reply=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'private, no-store'}});
export async function GET(request){
 const session=await getSession();if(!session)return reply({error:'Unauthorized'},401);if(session.role!=='owner')return reply({error:'Owner access required'},403);
 try{return reply(await listAssessments({after:new URL(request.url).searchParams.get('after')}));}
 catch(error){return reply({error:error instanceof SecurityInputError?error.code:'ASSESSMENT_FAILED'},error instanceof SecurityInputError?400:500);}
}
export async function POST(request){
  const session=await getSession();
  if(session?.role==='readonly')return Response.json({error:'READ_ONLY_ACCOUNT'},{status:403});
if(!session)return reply({error:'Unauthorized'},401);if(session.role!=='owner')return reply({error:'Owner access required'},403);
  try {const input=await boundedJson(request,{maxBytes:3*1024*1024});return reply({assessment:await changeAssessment(session,input)});}
  catch(error){const code=error instanceof SecurityInputError?error.code:['INVALID_REQUEST','REQUEST_LIMIT'].includes(error.message)?error.message:'ASSESSMENT_FAILED';return reply({error:code},code==='NOT_FOUND'?404:code==='ASSESSMENT_FAILED'?500:400);}
}
