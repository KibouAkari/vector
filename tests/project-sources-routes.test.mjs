import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {SourceError} from '../lib/source-fetch.mjs';
import {readSourceRequest} from '../lib/source-request.mjs';
const source=readFileSync(new URL('../app/api/projects/[id]/sources/route.js',import.meta.url),'utf8')
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'');
function api({session={userId:'u'},read=true,edit=true,code}={}) {
  const calls=[];
  const deps={getSession:async()=>session,canAccessProject:async()=>read,canEditProject:async()=>edit,
    listProjectSources:async id=>{calls.push(['read',id]);return [];},
    importProjectSource:async input=>{calls.push(['import',input]);if(code)throw new SourceError(code);return {id:'source',status:'indexed'};},
    readSourceRequest,SourceError};
  return {...new Function(...Object.keys(deps),source+'\nreturn {GET,POST};')(...Object.values(deps)),calls};
}
const context={params:Promise.resolve({id:'project'})};
const request=()=>new Request('https://vector.test',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({url:'https://docs.example.org',requestId:'123e4567-e89b-42d3-a456-426614174000'})});
test('anonymous, unrelated and read-only users cannot start network imports',async()=>{
  for(const config of [{session:null},{read:false,edit:false},{edit:false}]) {
    const f=api(config);
    assert.equal((await f.POST(request(),context)).status,config.session===null?401:404);
    assert.equal(f.calls.length,0);
  }
  const f=api({read:false,edit:false});assert.equal((await f.GET(null,context)).status,404);assert.equal(f.calls.length,0);
});
test('readers can inspect source metadata; editors import only into the authorized project',async()=>{
  const f=api({edit:false});assert.equal((await f.GET(null,context)).status,200);
  const g=api();const response=await g.POST(request(),context);assert.equal(response.status,200);
  assert.equal(g.calls[0][1].projectId,'project');assert.equal(g.calls[0][1].session.userId,'u');
  assert.match(response.headers.get('cache-control'),/no-store/);
});
test('local-only policy, capacity and blocked network targets return bounded public errors',async()=>{
  for(const [code,status] of [['LOCAL_ONLY_PROJECT',403],['IMPORT_BUSY',429],['BLOCKED_ADDRESS',400],['CONTENT_LIMIT',422]]) {
    const response=await api({code}).POST(request(),context);
    assert.equal(response.status,status);assert.equal((await response.json()).code,code);
  }
});

test('original snapshots require project membership and are served only as downloads',async()=>{
  const raw=readFileSync(new URL('../app/api/projects/[id]/sources/[sourceId]/snapshot/route.js',import.meta.url),'utf8')
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'').replace(/^export\s+/gm,'');
  let queries=0,allowed=false;
  const deps={getSession:async()=>({userId:'reader'}),canAccessProject:async()=>allowed,
    initializeProjectSources:async()=>{},db:{query:async(sql,params)=>{queries++;assert.deepEqual(params,['source','project']);return {rowCount:1,rows:[{raw_snapshot:Buffer.from('<script>never inline</script>')}]};}},
    decryptFileBuffer:value=>value};
  const {GET}=new Function(...Object.keys(deps),raw+'\nreturn {GET};')(...Object.values(deps));
  const ctx={params:Promise.resolve({id:'project',sourceId:'source'})};
  assert.equal((await GET(null,ctx)).status,404);assert.equal(queries,0);
  allowed=true;const response=await GET(null,ctx);
  assert.equal(response.status,200);assert.match(response.headers.get('content-disposition'),/^attachment/);
  assert.equal(response.headers.get('content-type'),'application/octet-stream');
  assert.equal(response.headers.get('x-content-type-options'),'nosniff');
  assert.match(response.headers.get('content-security-policy'),/sandbox/);
});
