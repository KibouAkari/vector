import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
test('quick mode avoids paid planner/reviewer stages for routine project and coding wording',async()=>{
 const source=readFileSync(new URL('../lib/workflow-runtime.js',import.meta.url),'utf8').replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'');
 let worker=0,extra=0;
 const deps={runVectorAgent:async()=>{worker++;return {text:'Fixture answer',toolTrace:[{tool:'project_search',success:true}]};},extractAuthorizedTargets:()=>[],createToolContext:()=>({}),requestSimpleProviderText:async()=>{extra++;throw Error('No extra provider stage should run');}};
 const api=new Function(...Object.keys(deps),source+'\nreturn {runAutonomousWorkflow};')(...Object.values(deps));
 for(const message of ['Fix this app','Summarize the project','I am happy today'])await api.runAutonomousWorkflow({mode:'quick',originalUserMessage:message,messages:[{role:'user',content:message}]});
 assert.equal(worker,3);assert.equal(extra,0);
});
