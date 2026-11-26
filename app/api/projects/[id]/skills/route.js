import {getSession} from '../../../../../lib/auth';
import {canAccessProject,canEditProject} from '../../../../../lib/identity';
import {boundedJson} from '../../../../../lib/bounded-json.mjs';
import {listSkills,createSkill,reviewSkill} from '../../../../../lib/project-skills';
export const runtime='nodejs';export const dynamic='force-dynamic';
const reply=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'private, no-store'}});
export async function GET(request,context){const session=await getSession();if(!session)return reply({error:'Unauthorized'},401);const {id}=await context.params;if(!await canAccessProject(session,id))return reply({error:'Not found'},404);return reply({skills:await listSkills(id,await canEditProject(session,id)),canReview:session.role==='owner'});}
export async function POST(request,context){
  const session=await getSession();if(!session)return reply({error:'Unauthorized'},401);const {id}=await context.params;if(!await canEditProject(session,id))return reply({error:'Not found'},404);
  try {const input=await boundedJson(request,{maxBytes:65536});if(input.action==='create')return reply({skill:await createSkill(id,session,input)});if(session.role!=='owner')return reply({error:'Owner access required'},403);return reply({skill:await reviewSkill(id,session,input)});}
  catch(error){const code=['INVALID_SKILL','SKILL_LIMIT','SKILL_CONFLICT','REQUEST_LIMIT','INVALID_REQUEST'].includes(error.message)?error.message:'SKILL_UPDATE_FAILED';return reply({error:code},code==='SKILL_UPDATE_FAILED'?500:400);}
}
