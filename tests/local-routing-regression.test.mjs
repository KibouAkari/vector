import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../lib/execution-router.js',import.meta.url),'utf8');
const {classifyExecution}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const recentMessages=[{role:'user',content:'Welche Rekorde hat ExampleOne auf Minecraft?'}];
const classify=taskText=>classifyExecution({taskText,allowServer:true,recentMessages});

test('self-contained reset email does not inherit a Minecraft tool requirement',()=>{
  for(const prompt of [
    'Hilf mir eine Mail zu schreiben. Es geht um einen password reset für demo.example.invalid. Der username ist benno beispiel und das password Demo-456. Bitte gib benno bescheid.',
    'Schreibe eine Mail für <VEC_PERSON_0123456789abcdef0123456789abcdef>.',
    'Write an email for ExampleOne about a password reset.'
  ]) {
    const route=classify(prompt);
    assert.equal(route.class,'fast');
    assert.equal(route.requirements.server,false);
    assert.equal(route.requirements.functionTools,false);
  }
});

test('short player follow-ups still require real data, including masked names',()=>{
  for(const prompt of ['und für ExampleTwo?','and for ExampleTwo','für <VEC_PERSON_0123456789abcdef0123456789abcdef>?']) {
    assert.equal(classify(prompt).requirements.serverMinecraft,true);
  }
  assert.equal(classify('Welche Rekorde hat ExampleOne auf Minecraft?').requirements.server,true);
});

test('actual local executor blocks unsupported live lookups before any inference',async()=>{
  const original=readFileSync(new URL('../lib/local-private-chat.js',import.meta.url),'utf8');
  const stripped=original.replace(/^import .*;\n/gm,'');
  // Use the complete router so all internal predicates execute unchanged.
  const moduleSource=source.replace('export function classifyExecution','function classifyExecution')+`
    const getAgentJob=async()=>({status:'running'});
    const heartbeatAgentJob=async()=>{};
    const hostInspect=async()=>{throw Error('unexpected read')};
    const localServerStatistics=async()=>null;
    const failAgentJob=async()=>{failures++};
    const restorePrivateValues=async({text})=>text;
    const requestLocalChat=async()=>{requests++;throw Error('unexpected inference')};
    const withLocalWorkerSlot=async f=>f();
    let requests=0,failures=0;
    export const counters=()=>({requests,failures});
  `+stripped;
  const mod=await import('data:text/javascript;base64,'+Buffer.from(moduleSource).toString('base64'));
  const prior=[process.env.VECTOR_PRIVACY_REVIEW,process.env.VECTOR_LOCAL_WORKERS];
  process.env.VECTOR_PRIVACY_REVIEW='1';process.env.VECTOR_LOCAL_WORKERS='1';
  try {
    await assert.rejects(()=>mod.executeLocalPrivateJob({id:'synthetic',payload:{messages:[{role:'user',content:'Lies die Docker Logs von meinem Server'}]}},{}),/weitere Datenwerkzeuge/);
    assert.deepEqual(mod.counters(),{requests:0,failures:1});
  } finally {
    for(const [i,key] of ['VECTOR_PRIVACY_REVIEW','VECTOR_LOCAL_WORKERS'].entries()){
      if(prior[i]===undefined)delete process.env[key];else process.env[key]=prior[i];
    }
  }
});


test('Minecraft statistics without a named server still require real tools',()=>{
  for(const prompt of ['Gib mir die Rekorde und besten Statistiken von ExampleOne vom Minecraft Server',
    'Welche Rekorte hat ExampleOne auf Minecraft?', 'Welche Statistik hat ExampleOne auf Minecraft?']) {
    assert.equal(classify(prompt).requirements.server,true);
  }
});

test('German own-server read requests require the existing server tool path',()=>{
  for(const taskText of ['Kannst du meinen Server vollständig auslesen?', 'Zeige die Konfiguration meines Servers', 'Lies die Dateien auf meinem Server']) {
    const result=classifyExecution({taskText,allowServer:true});
    assert.equal(result.requirements.server,true);
    assert.equal(result.requirements.functionTools,true);
    assert.equal(classifyExecution({taskText,allowServer:false}).requirements.server,false);
  }
});

test('generic Minecraft explanations stay text-only and topic switches end old player context',()=>{
  for(const taskText of ['Was ist ein Rekord in Minecraft?', 'Erkläre mir Statistiken in Minecraft'])
    assert.equal(classifyExecution({taskText,allowServer:true}).requirements.server,false);
  const recentMessages=[{role:'user',content:'Welche Rekorde hat ExampleOne auf Minecraft?'},
    {role:'user',content:'Schreibe eine Mail für ExampleOne'}];
  assert.equal(classifyExecution({taskText:'und für ExampleTwo?',allowServer:true,recentMessages}).requirements.server,false);
});
