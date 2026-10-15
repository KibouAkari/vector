import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import crypto from 'node:crypto';
import { assertRequestedArtifactFormat, toolsForArtifactFormat } from '../lib/artifact-format-policy.mjs';

// Exercise the real runtime functions with local provider/host/renderer doubles.
// No provider calls, databases, host sockets or file generation are needed.
function loadRuntime(path, bindings, names) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
    .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, '')
    .replace(/^export\s+/gm, '');
  return new Function(...Object.keys(bindings), source + `\nreturn {${names.join(',')}};`)(...Object.values(bindings));
}

function runtimeFixture() {
  const calls = {host: [], render: [], provider: []};
  const tools = loadRuntime('../lib/tool-runtime.js', {
    crypto, assertRequestedArtifactFormat,
    db: {query: async () => { throw new Error('Unexpected database read'); }},
    hostSnapshot: async () => { calls.host.push('snapshot'); return {}; },
    hostInspect: async args => { calls.host.push(args); return {complete: true, text: 'Fixture evidence'}; },
    createChatArtifact: async args => {
      calls.render.push(args);
      return {artifact: {id: 'generated', format: args.format, name: 'report.' + args.format}};
    },
    buildArtifactPlan: args => args,
    summarizeArtifactPlan: args => args,
    readEncryptedFile: async () => { throw new Error('Unexpected file read'); },
    searchProjectChunks: async () => [],
    sandboxList: async () => [], sandboxRead: async () => '',
    sandboxRun: async () => { throw new Error('Unexpected sandbox run'); },
    sandboxWrite: async () => { throw new Error('Unexpected sandbox write'); }
  }, ['getVectorTools', 'createToolContext', 'executeVectorTool']);
  return {calls, tools};
}

test('PDF and DOCX tool lists exclude the XLSX-only exporter without losing source tools', () => {
  const tools = ['server_inspect', 'artifact_create', 'artifact_create_from_server_json'].map(name => ({type: 'function', name}));
  for (const format of ['pdf', 'docx']) {
    assert.deepEqual(toolsForArtifactFormat(tools, format).map(x => x.name), ['server_inspect', 'artifact_create']);
  }
  assert.equal(toolsForArtifactFormat(tools, 'xlsx'), tools);
  assert.equal(toolsForArtifactFormat(tools, null), tools);
  assert.equal(tools.length, 3);
});

test('actual tool executor rejects wrong formats before host reads, rendering or reuse', async () => {
  const {calls, tools} = runtimeFixture();
  for (const wanted of ['pdf', 'docx']) {
    for (const name of ['artifact_create', 'artifact_create_from_server_json']) {
      const context = {userId:'fixture', conversationId:'fixture', jobId:'fixture', requestedArtifactFormat:wanted};
      await assert.rejects(tools.executeVectorTool({name, arguments:{format:'xlsx'}, context}), /user requested/);
      assert.equal(context.artifactCreated, undefined);
    }
  }
  const context = {
    userId:'fixture', conversationId:'fixture', jobId:'fixture',
    requestedArtifactFormat:'pdf', artifactCreated:true,
    lastArtifact:{artifact:{format:'xlsx'}}
  };
  await assert.rejects(tools.executeVectorTool({name:'artifact_create', arguments:{format:'pdf'}, context}), /user requested PDF/);
  assert.equal(calls.host.length, 0);
  assert.equal(calls.render.length, 0);
});

test('matching document tools render once and reuse only the matching artifact', async () => {
  for (const format of ['pdf', 'docx']) {
    const {calls, tools} = runtimeFixture();
    const context = {userId:'fixture', conversationId:'fixture', jobId:'fixture', requestedArtifactFormat:format};
    const input = {name:'artifact_create', arguments:{format, content:'# Fixture\nVerified content'}, context};
    const first = await tools.executeVectorTool(input);
    const second = await tools.executeVectorTool(input);
    assert.equal(first.artifact.format, format);
    assert.equal(second.artifact.format, format);
    assert.equal(second.reused, true);
    assert.equal(calls.render.length, 1);
  }
});

test('grounded document requests finish as documents even if a provider attempts the XLSX tool', async () => {
  for (const format of ['pdf', 'docx']) {
    for (const executionClass of ['artifact', 'deep']) {
      const {calls, tools} = runtimeFixture();
      const {runVectorAgent} = loadRuntime('../lib/agent-runtime.js', {
        ...tools, assertRequestedArtifactFormat, toolsForArtifactFormat,
        sanitizeForExternal: text => ({sanitized:text, mappings:[]}),
        savePrivacyMappings: async () => {},
        requestProviderResponse: async ({payload}) => {
          calls.provider.push(payload);
          const output = calls.provider.length === 1
            ? [{type:'function_call', call_id:'wrong-format', name:'artifact_create_from_server_json', arguments:'{"path":"/srv/fixture"}'}]
            : calls.provider.length === 2
              ? [{type:'function_call', call_id:'read-source', name:'server_inspect', arguments:'{"action":"read","path":"/srv/fixture/report.json"}'}]
              : [{type:'message', content:[{type:'output_text', text:'# Fixture report\n\nVerified fixture results.'}]}];
          return {id:'response-' + calls.provider.length, status:'completed', output, usage:{input_tokens:10,output_tokens:10}};
        }
      }, ['runVectorAgent']);
      const context = tools.createToolContext({userId:'fixture', conversationId:'fixture', jobId:'fixture'});
      const request = `Erstelle ein ${format.toUpperCase()} mit aktuellen Statistiken von meinem Server.`;
      const result = await runVectorAgent({
        model:'fixture-model', mode:'normal', messages:[{role:'user',content:request}],
        originalUserMessage:request, maxOutputTokens:2048,
        conversationId:'fixture', userId:'fixture', jobId:'fixture',
        providedToolContext:context, allowServer:true,
        executionClass, toolDomains:{server:true}, roundLimit:4
      });
      assert.equal(result.artifactCreated, true);
      assert.equal(result.artifact.artifact.format, format);
      assert.equal(calls.render.length, 1);
      assert.equal(calls.host.length, 1);
      assert.equal(calls.host[0].action, 'read');
      assert.equal(calls.provider.length, 3);
      for (const payload of calls.provider) {
        assert.ok(payload.tools.some(tool => tool.name === 'server_inspect'));
        assert.ok(!payload.tools.some(tool => tool.name === 'artifact_create_from_server_json'));
      }
      assert.ok(result.toolTrace.some(item => item.tool === 'artifact_create_from_server_json' && item.success === false));
    }
  }
});

function limitFixture({format='pdf', finalText='# Fixture rankings\n\n| Rank | Player | Score |\n| --- | --- | --- |\n| 1 | Fixture player | 42 |', renderFailure=false, existing=false, finalStatus='completed', continuations=[]}={}) {
  const {calls, tools}=runtimeFixture();
  const execute=tools.executeVectorTool;
  const {runVectorAgent}=loadRuntime('../lib/agent-runtime.js',{
    ...tools, assertRequestedArtifactFormat, toolsForArtifactFormat,
    executeVectorTool:async input=>{
      if(renderFailure && input.name==='artifact_create')throw new Error('Fixture renderer failed');
      return execute(input);
    },
    sanitizeForExternal:text=>({sanitized:text,mappings:[]}),
    savePrivacyMappings:async()=>{},
    requestProviderResponse:async({payload})=>{
      calls.provider.push(payload);
      const output=calls.provider.length===1
        ? [{type:'function_call',call_id:'last-read',name:'server_inspect',arguments:'{"action":"read","path":"/srv/fixture/rankings.json"}'}]
        : [{type:'message',content:finalText?[{type:'output_text',text:finalText}]:[]}];
      if (calls.provider.length > 2) {
        const part = continuations[calls.provider.length - 3] || {text:'', status:'incomplete'};
        return {id:'continued-'+calls.provider.length,status:part.status,
          incomplete_details:part.status==='incomplete'?{reason:'max_output_tokens'}:null,
          output:[{type:'message',content:[{type:'output_text',text:part.text}]}],
          usage:{input_tokens:10,output_tokens:10,input_tokens_details:{cached_tokens:2}}};
      }
      return {id:'response-'+calls.provider.length,status:calls.provider.length===2?finalStatus:'completed',
        incomplete_details:calls.provider.length===2 && finalStatus==='incomplete'?{reason:'max_output_tokens'}:null,
        output,usage:{input_tokens:10,output_tokens:10}};
    }
  },['runVectorAgent']);
  const context=tools.createToolContext({userId:'fixture',conversationId:'fixture',jobId:'fixture'});
  if(existing){context.artifactCreated=true;context.lastArtifact={artifact:{id:'existing',format}};}
  const request=`Kannst du ein weiteres ${format.toUpperCase()} erstellen, mit Top-10-Ranglisten aus den Serverdaten?`;
  return {calls,context,run:()=>runVectorAgent({
    model:'fixture-model',mode:'normal',messages:[{role:'user',content:request}],
    originalUserMessage:request,maxOutputTokens:2048,conversationId:'fixture',
    userId:'fixture',jobId:'fixture',providedToolContext:context,allowServer:true,
    executionClass:'artifact',toolDomains:{server:true},roundLimit:1
  })};
}

test('a document is rendered after the final permitted tool round',async()=>{
  for(const format of ['pdf','docx']){
    const fixture=limitFixture({format});
    const result=await fixture.run();
    assert.equal(result.finalizedAfterLimit,true);
    assert.equal(result.artifactCreated,true);
    assert.equal(result.artifact.artifact.format,format);
    assert.equal(fixture.calls.render.length,1);
    assert.match(fixture.calls.render[0].content,/Fixture player/);
    assert.equal(fixture.calls.provider.length,2);
    assert.deepEqual(fixture.calls.provider[1].tools,[]);
    assert.equal(result.inputTokens,20);
    assert.equal(result.outputTokens,20);
    assert.ok(result.toolTrace.some(item=>item.tool==='artifact_create'&&item.success===true));
  }
});

test('limit finalization rejects empty document content and renderer errors without claiming completion',async()=>{
  const empty=limitFixture({finalText:''});
  await assert.rejects(empty.run(),/no document content/);
  assert.equal(empty.calls.render.length,0);
  assert.equal(empty.context.artifactCreated,undefined);
  const broken=limitFixture({renderFailure:true});
  await assert.rejects(broken.run(),/Fixture renderer failed/);
  assert.equal(broken.context.artifactCreated,undefined);
  assert.equal(broken.calls.provider.length,2);
});

test('limit finalization preserves an existing document without generating a duplicate',async()=>{
  const fixture=limitFixture({existing:true});
  const result=await fixture.run();
  assert.equal(result.artifactCreated,true);
  assert.equal(result.artifact.artifact.id,'existing');
  assert.equal(fixture.calls.render.length,0);
});


test('truncated document continuation finishes the same table before rendering and accounts for usage',async()=>{
  for(const format of ['pdf','docx']){
    const fixture=limitFixture({format,finalText:'# Complete fixture\n\n| Rank | Player | Value |\n| --- | --- | --- |\n| 1 | Player A | 1',
      finalStatus:'incomplete',continuations:[{text:'23 |\n\n## Other category\n\nAll ten results verified.',status:'completed'}]});
    const result=await fixture.run();
    assert.equal(result.artifactCreated,true);
    assert.equal(fixture.calls.render.length,1);
    assert.match(fixture.calls.render[0].content,/Player A \| 123 \|/);
    assert.match(fixture.calls.render[0].content,/Other category/);
    assert.equal(fixture.calls.provider.length,3);
    assert.deepEqual(fixture.calls.provider[2].tools,[]);
    assert.equal(fixture.calls.provider[2].max_output_tokens,2048);
    assert.equal(result.inputTokens,30);
    assert.equal(result.outputTokens,30);
    assert.equal(result.cachedTokens,2);
    assert.deepEqual(result.providerCalls.map(call=>call.phase),
      ['agent-turn','limit-finalization','document-continuation']);
    assert.equal(result.providerCalls[1].stopReason,'max_output_tokens');
    assert.equal(result.providerCalls[2].cachedTokens,2);
  }
});

test('reasoning-only truncated output uses the existing single recovery instead of document continuations',async()=>{
  const {calls,tools}=runtimeFixture();
  const {runVectorAgent}=loadRuntime('../lib/agent-runtime.js',{
    ...tools,assertRequestedArtifactFormat,toolsForArtifactFormat,
    sanitizeForExternal:text=>({sanitized:text,mappings:[]}),savePrivacyMappings:async()=>{},
    requestProviderResponse:async({payload})=>{
      calls.provider.push(payload);
      const empty=calls.provider.length===1;
      return {id:'fixture',status:empty?'incomplete':'completed',
        incomplete_details:empty?{reason:'max_output_tokens'}:null,
        output:empty?[{type:'reasoning'}]:[{type:'message',content:[{type:'output_text',text:'# Fixture\n\nCompleted body.'}]}],
        usage:{input_tokens:10,output_tokens:10,output_tokens_details:{reasoning_tokens:empty?10:0}}};
    }
  },['runVectorAgent']);
  const request='Erstelle ein PDF mit einer kurzen Zusammenfassung.';
  const result=await runVectorAgent({model:'fixture',mode:'normal',messages:[{role:'user',content:request}],
    originalUserMessage:request,maxOutputTokens:1400,conversationId:'fixture',userId:'fixture',jobId:'fixture',
    executionClass:'artifact',roundLimit:2});
  assert.equal(calls.provider.length,2);
  assert.equal(calls.render.length,1);
  assert.deepEqual(result.providerCalls.map(call=>call.phase),['agent-turn','empty-response-recovery']);
  assert.equal(result.providerCalls[0].reasoningTokens,10);
  assert.equal(result.outputTokens,20);
});
test('bounded continuation never persists a document that remains truncated or returns no continuation',async()=>{
  const partial=limitFixture({finalStatus:'incomplete',continuations:[
    {text:'still partial',status:'incomplete'},{text:'still partial',status:'incomplete'}]});
  await assert.rejects(partial.run(),/no partial document was saved/);
  assert.equal(partial.calls.render.length,0);
  assert.equal(partial.calls.provider.length,4);
  const empty=limitFixture({finalStatus:'incomplete'});
  await assert.rejects(empty.run(),/no document continuation/);
  assert.equal(empty.calls.render.length,0);
});
test('normal no-tool and empty-response recovery paths also complete partial documents',async()=>{
  for(const emptyFirst of [false,true]){
    const {calls,tools}=runtimeFixture();
    const {runVectorAgent}=loadRuntime('../lib/agent-runtime.js',{
      ...tools,assertRequestedArtifactFormat,toolsForArtifactFormat,
      sanitizeForExternal:text=>({sanitized:text,mappings:[]}),savePrivacyMappings:async()=>{},
      requestProviderResponse:async({payload})=>{
        calls.provider.push(payload);
        const n=calls.provider.length;
        const empty=emptyFirst && n===1;
        const partial=n===(emptyFirst?2:1);
        return {id:'fixture-'+n,status:partial?'incomplete':'completed',
          incomplete_details:partial?{reason:'max_output_tokens'}:null,
          output:empty?[]:[{type:'message',content:[{type:'output_text',
            text:partial?'# Fixture\n\nBeginning':' and complete ending.'}]}],
          usage:{input_tokens:10,output_tokens:10}};
      }
    },['runVectorAgent']);
    const request='Erstelle ein PDF mit einer kurzen Zusammenfassung.';
    const result=await runVectorAgent({model:'fixture',mode:'normal',
      messages:[{role:'user',content:request}],originalUserMessage:request,
      maxOutputTokens:2048,conversationId:'fixture',userId:'fixture',jobId:'fixture',
      executionClass:'artifact',roundLimit:2});
    assert.equal(result.artifactCreated,true);
    assert.equal(calls.render.length,1);
    assert.match(calls.render[0].content,/Beginning and complete ending/);
    assert.equal(calls.provider.length,emptyFirst?3:2);
  }
});

