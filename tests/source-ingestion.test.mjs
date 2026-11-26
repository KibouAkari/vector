import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import {once} from 'node:events';
import {isPublicAddress,sourceUrl,publicDestination,pinnedLookup,fetchPublicSource,requestSourcePage} from '../lib/source-fetch.mjs';
import {extractSourceText,SOURCE_TEXT_LIMIT,sourceDigest} from '../lib/source-extract.mjs';
import {readSourceRequest} from '../lib/source-request.mjs';

const resolve = async () => [{address:'93.184.216.34',family:4}];
const page = () => ({buffer:Buffer.from('source facts'),mimeType:'text/plain'});
test('private, metadata, reserved and transition IP addresses fail closed',() => {
  for(const ip of ['0.0.0.0','10.2.3.4','127.0.0.1','169.254.169.254','172.31.4.1','192.168.1.1','100.100.100.200','198.19.1.1','192.0.2.1','224.0.0.1','255.255.255.255','::','::1','::ffff:127.0.0.1','::ffff:8.8.8.8','fe80::1','fc00::1','2001:db8::1','2002:7f00:1::','2001::1','3fff::1']) assert.equal(isPublicAddress(ip),false,ip);
  for(const ip of ['8.8.8.8','93.184.216.34','2606:4700:4700::1111']) assert.equal(isPublicAddress(ip),true,ip);
});
test('URLs reject credentials, alternate ports, protocols, ambiguous and private literals',()=>{
  for(const value of ['file:///etc/passwd','ftp://public.org/x','https://user:password@public.org','https://public.org:9443','http://127.1','http://2130706433','http://0x7f000001','http://[::ffff:127.0.0.1]','http://intranet','http://local.internal','https://public.org./','https://public.org\\@127.0.0.1',' https://public.org']) assert.throws(()=>sourceUrl(value),undefined,value);
  assert.equal(sourceUrl('https://public.org/article#heading').href,'https://public.org/article');
});
test('mixed DNS responses are blocked and lookup failures do not expose details',async()=>{
  await assert.rejects(publicDestination(sourceUrl('https://public.org'),async()=>[{address:'8.8.8.8',family:4},{address:'10.0.0.2',family:4}]),{code:'BLOCKED_ADDRESS'});
  await assert.rejects(publicDestination(sourceUrl('https://public.org'),async()=>{throw Error('internal resolver secret');}),{code:'DNS_FAILED'});
  const value=await publicDestination(sourceUrl('https://public.org'),resolve);
  pinnedLookup(value)('ignored',{all:true},(error,rows)=>assert.deepEqual(rows,[value]));
});
test('each redirect is checked before a new connection, including DNS changes',async()=>{
  let calls=0;
  await assert.rejects(fetchPublicSource('https://public.org',{resolve,request:async()=>{calls++;return {redirect:true,location:'http://169.254.169.254/latest'};}}),{code:'BLOCKED_REDIRECT'});
  assert.equal(calls,1);
  let resolutions=0;
  await assert.rejects(fetchPublicSource('https://public.org',{resolve:async()=>++resolutions===1?resolve():[{address:'127.0.0.1',family:4}],request:async()=>({redirect:true,location:'/next'})}),{code:'BLOCKED_ADDRESS'});
  assert.equal(resolutions,2);
  await assert.rejects(fetchPublicSource('https://public.org',{resolve,request:async()=>({redirect:true,location:'http://public.org/next'})}),{code:'BLOCKED_REDIRECT'});
  const result=await fetchPublicSource('https://public.org',{resolve,request:async()=>page()});
  assert.equal(result.finalUrl,'https://public.org/');
  assert.ok(result.fetchedAt);
});
test('transport pins the checked IP, sends no credentials and bounds bodies',async()=>{
  let mode='ok';
  const server=http.createServer((request,response)=>{
    assert.equal(request.headers.authorization,undefined);
    assert.equal(request.headers.cookie,undefined);
    assert.equal(request.headers['accept-encoding'],'identity');
    assert.match(request.headers.host,/public\.org/);
    if(mode==='type') response.writeHead(200,{'content-type':'application/zip'}).end('zip');
    else if(mode==='encoding') response.writeHead(200,{'content-type':'text/plain','content-encoding':'gzip'}).end('zip');
    else if(mode==='size') response.writeHead(200,{'content-type':'text/plain'}).end(Buffer.alloc(2*1024*1024+1));
    else response.writeHead(200,{'content-type':'text/plain'}).end('evidence');
  });
  server.listen(0,'127.0.0.1'); await once(server,'listening');
  try {
    const url=new URL(`http://public.org:${server.address().port}/`);
    const request=()=>requestSourcePage(url,{address:'127.0.0.1',family:4},AbortSignal.timeout(2000));
    assert.equal((await request()).buffer.toString(),'evidence');
    mode='type'; await assert.rejects(request(),{code:'UNSUPPORTED_CONTENT'});
    mode='encoding'; await assert.rejects(request(),{code:'CONTENT_LIMIT'});
    mode='size'; await assert.rejects(request(),{code:'CONTENT_LIMIT'});
  } finally {server.closeAllConnections();await new Promise(r=>server.close(r));}
});
test('HTML is decoded as text without scripts, navigation, forms or execution',()=>{
  const buffer=Buffer.from('<title>A &amp; B</title><script>fetch("private")</script><nav>menu</nav><article><h1>Evidence</h1><p>Fact &lt;b&gt;literal&lt;/b&gt;</p><style>bad</style><form>secret</form></article>');
  const result=extractSourceText({buffer,mimeType:'text/html'});
  assert.equal(result.title,'A & B'); assert.match(result.text,/Evidence/); assert.match(result.text,/<b>literal<\/b>/);
  assert.doesNotMatch(result.text,/private|menu|secret|bad/);
  assert.equal(result.rawSha256,sourceDigest(buffer));
  assert.equal(result.textSha256,sourceDigest(Buffer.from(result.text)));
  assert.equal(result.partial,false);
});
test('empty, unsupported and oversized extraction never report indexed content',()=>{
  assert.throws(()=>extractSourceText({buffer:Buffer.from('<script>empty</script>'),mimeType:'text/html'}),{code:'NO_EXTRACTABLE_TEXT'});
  assert.throws(()=>extractSourceText({buffer:Buffer.from([255,255]),mimeType:'text/plain'}),{code:'UNSUPPORTED_ENCODING'});
  assert.throws(()=>extractSourceText({buffer:Buffer.from('x'),mimeType:'application/pdf'}),{code:'UNSUPPORTED_CONTENT'});
  assert.throws(()=>extractSourceText({buffer:Buffer.from('<div>'.repeat(140)),mimeType:'text/html'}),{code:'EXTRACTION_LIMIT'});
  const result=extractSourceText({buffer:Buffer.from('x'.repeat(SOURCE_TEXT_LIMIT+1)),mimeType:'text/plain'});
  assert.equal(result.partial,true);assert.ok(result.text.split('\n').every(line=>line.length<=2000));
});
test('import requests have bounded bodies and exclusive UUID retry/idempotency keys',async()=>{
  const request=value=>new Request('https://vector.test',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(value)});
  const requestId='123e4567-e89b-42d3-a456-426614174000';
  assert.deepEqual(await readSourceRequest(request({url:'https://public.org',requestId})),{url:'https://public.org',requestId});
  assert.deepEqual(await readSourceRequest(request({sourceId:requestId})),{sourceId:requestId});
  for(const value of [{url:'x',requestId:'not-uuid'},{sourceId:requestId,url:'x'},[],{url:'x'.repeat(5000),requestId}]) await assert.rejects(readSourceRequest(request(value)),{code:'INVALID_REQUEST'});
});
