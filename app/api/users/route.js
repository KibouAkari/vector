import { getSession } from "../../../lib/auth";
import { createUser, listUsers } from "../../../lib/identity";
export async function GET(){ const s=await getSession(); if(!s||s.role!=="owner") return Response.json({error:"Forbidden"},{status:403}); return Response.json({users:await listUsers()}); }
export async function POST(request){ const s=await getSession(); if(!s||s.role!=="owner") return Response.json({error:"Forbidden"},{status:403}); try{ const body=await request.json(); return Response.json({ok:true,id:await createUser(body)}); } catch(e){ return Response.json({error:e.message},{status:400}); } }
