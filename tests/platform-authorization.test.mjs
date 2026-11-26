import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {boundedJson} from '../lib/bounded-json.mjs';
import {SecurityInputError} from '../lib/security/evidence.mjs';
const load=(path,deps,names)=>new Function(...Object.keys(deps),readFileSync(new URL(path,import.meta.url),'utf8').replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/\bexport\s+/g,'')+`\nreturn {${names.join(',')}};`)(...Object.values(deps));
test('members cannot approve global privileged actions or inspect policy',async()=>{
 for(const path of ['../app/api/approvals/[id]/decision/route.js','../app/api/permissions/check/route.js']){
  let accesses=0;const deps={getSession:async()=>({userId:'member',role:'member'}),db:{query:async()=>{accesses++;}},initializeDatabase:async()=>{accesses++;},writeAudit:async()=>{},getPermissionPolicy:async()=>{accesses++;}};
  const {POST}=load(path,deps,['POST']);const response=await POST({json:async()=>{throw Error('body must not be read');}},{params:{id:'a'}});assert.equal(response.status,403);assert.equal(accesses,0);
 }
});
test('security workspace rejects non-owners before storage or parsing',async()=>{
 let effects=0;for(const session of [null,{userId:'m',role:'member'}]){
 const api=load('../app/api/security/assessments/route.js',{getSession:async()=>session,boundedJson:async()=>{effects++;},listAssessments:async()=>{effects++;},changeAssessment:async()=>{effects++;},SecurityInputError},['GET','POST']);
 assert.equal((await api.GET()).status,session?403:401);assert.equal((await api.POST({})).status,session?403:401);assert.equal(effects,0);
 }
});
test('skill activation needs owner role as well as project edit access',async()=>{
 let writes=0;const api=load('../app/api/projects/[id]/skills/route.js',{getSession:async()=>({userId:'editor',role:'member'}),canEditProject:async()=>true,canAccessProject:async()=>true,boundedJson:async()=>({action:'activate'}),reviewSkill:async()=>{writes++;},createSkill:async()=>{writes++;},listSkills:async()=>[]},['POST']);
 assert.equal((await api.POST({}, {params:{id:'p'}})).status,403);assert.equal(writes,0);
});
test('skill selection is project-scoped, active-only and cannot grant execution privileges',async()=>{
 const id='123e4567-e89b-42d3-a456-426614174000';let queries=0;
 const api=load('../lib/project-skills.js',{crypto:{},initializeDatabase:async()=>{},db:{query:async(sql,params)=>{if(/SELECT id,name/.test(sql)){queries++;assert.match(sql,/project_id=\$1/);assert.match(sql,/status='active'/);assert.equal(params[0],'p');return {rows:[{id,name:'Reporting',instructions:'Summarize the supplied evidence.',content_sha256:'fixture'}]};}return {rows:[]};}}},['selectedSkillContext']);
 assert.equal(await api.selectedSkillContext('p',undefined),'');assert.equal(queries,0);
 assert.match(await api.selectedSkillContext('p',[id]),/not permission grants/);
 await assert.rejects(api.selectedSkillContext('p',['bad']),/INVALID_SKILL_SELECTION/);
 await assert.rejects(api.selectedSkillContext('p',[id,id,id,id]),/INVALID_SKILL_SELECTION/);
});
test('bounded JSON blocks oversized inputs and non-JSON bodies',async()=>{
 await assert.rejects(boundedJson(new Request('https://vector.test',{method:'POST',body:'plain'})),/INVALID_REQUEST/);
 await assert.rejects(boundedJson(new Request('https://vector.test',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({text:'x'.repeat(100)})}),{maxBytes:20}),/REQUEST_LIMIT/);
});

test('malformed JSON yields an input error while valid large Unicode skills remain accepted',async()=>{
 await assert.rejects(boundedJson(new Request('https://vector.test',{method:'POST',headers:{'content-type':'application/json'},body:'{"broken"'})),/INVALID_REQUEST/);
 const instructions='界'.repeat(6000);let received;
 const api=load('../app/api/projects/[id]/skills/route.js',{getSession:async()=>({userId:'editor',role:'member'}),canEditProject:async()=>true,canAccessProject:async()=>true,boundedJson,createSkill:async(_id,_session,input)=>{received=input;return {id:'fixture'};}},['POST']);
 const response=await api.POST(new Request('https://vector.test',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'create',name:'Unicode',instructions})}),{params:{id:'p'}});
 assert.equal(response.status,200);assert.equal(received.instructions,instructions);
});
test('skill context exposes original quoted bytes to the privacy scanner before serialization',async()=>{
 const id='123e4567-e89b-42d3-a456-426614174000';const instructions='Password: "R7! synthetic phrase"';
 const api=load('../lib/project-skills.js',{crypto:{},initializeDatabase:async()=>{},db:{query:async sql=>({rows:/SELECT id,name/.test(sql)?[{id,name:'Synthetic',instructions,content_sha256:'fixture'}]:[]})}},['selectedSkillContext']);
 assert.ok((await api.selectedSkillContext('p',[id])).includes(instructions));
});
