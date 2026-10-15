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
