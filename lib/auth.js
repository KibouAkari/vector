import crypto from "node:crypto";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { authenticateUser, getUserById, getUserByUsername, hasFeature, initializeIdentity, publicUser } from "./identity";

const COOKIE_NAME="vector_session";
function secret(){ const x=process.env.VECTOR_SECRET; if(!x) throw new Error("VECTOR_SECRET missing"); return x; }
function sign(v){ return crypto.createHmac("sha256",secret()).update(v).digest("base64url"); }
function decode(token){
  try {
    if(!token) return null;
    const [encoded,sig,...rest]=token.split(".");
    if(rest.length) return null;
    const expected=sign(encoded);
    const a=Buffer.from(expected), b=Buffer.from(sig||"");
    if(a.length!==b.length || !crypto.timingSafeEqual(a,b)) return null;
    const payload=JSON.parse(Buffer.from(encoded,"base64url").toString("utf8"));
    if(!payload.expiresAt || Date.now()>payload.expiresAt) return null;
    return payload;
  } catch { return null; }
}

export function createSession(user){
  const accountExpiry=user.expiresAt ? new Date(user.expiresAt).getTime() : Infinity;
  const payload={userId:user.userId,username:user.username,role:user.role,expiresAt:Math.min(Date.now()+604800000,accountExpiry)};
  const encoded=Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${encoded}.${sign(encoded)}`;
}

export async function getSession(){
  await initializeIdentity();
  const store=await cookies();
  const payload=decode(store.get(COOKIE_NAME)?.value);
  if(!payload) return null;
  const user=payload.userId ? await getUserById(payload.userId) : await getUserByUsername(payload.username);
  if(!user || !user.enabled) return null;
  if(user.expires_at && new Date(user.expires_at).getTime()<=Date.now()) return null;
  return publicUser(user);
}

export async function requireSession(){ const s=await getSession(); if(!s) redirect("/login"); return s; }
export async function requireOwner(){ const s=await requireSession(); if(s.role!=="owner") redirect("/"); return s; }
export async function requireFeature(feature){ const s=await requireSession(); if(!hasFeature(s,feature)) redirect("/"); return s; }
export { authenticateUser, hasFeature };

export async function setSessionCookie(token){ const s=await cookies(); s.set(COOKIE_NAME,token,{httpOnly:true,secure:process.env.COOKIE_SECURE==="true",sameSite:"strict",path:"/",maxAge:604800}); }
export async function clearSessionCookie(){ const s=await cookies(); s.set(COOKIE_NAME,"",{httpOnly:true,secure:process.env.COOKIE_SECURE==="true",sameSite:"strict",path:"/",maxAge:0}); }
