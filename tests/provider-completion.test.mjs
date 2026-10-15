
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../lib/provider-runtime.js',import.meta.url),'utf8')
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'')
  .replace(/^export\s+/gm,'');
function load(response){
  return new Function('normalizedOpenAiUsage','normalizedAnthropicUsage','fetch',source+'\nreturn {normalizeChatResponse,anthropicRequest};')(
    usage=>usage,usage=>usage,async()=>({ok:true,text:async()=>JSON.stringify(response)}));
}
test('chat-compatible provider preserves token-limit completion metadata',()=>{
  const {normalizeChatResponse}=load({});
  for(const reason of ['length','stop','tool_calls']){
    const result=normalizeChatResponse({id:'fixture',choices:[{finish_reason:reason,message:{content:'partial'}}]}, {provider:'fixture',model:'fixture'});
    assert.equal(result.status,reason==='length'?'incomplete':'completed');
    assert.equal(result.incomplete_details?.reason,reason==='length'?'max_output_tokens':undefined);
  }
});
test('Anthropic provider preserves token-limit completion metadata',async()=>{
  for(const reason of ['max_tokens','end_turn','tool_use']){
    const {anthropicRequest}=load({id:'fixture',stop_reason:reason,content:[{type:'text',text:'partial'}]});
    const result=await anthropicRequest({apiKey:'fixture-test-only',apiBase:'https://fixture.invalid',provider:'fixture',model:'fixture'}, {input:[],tools:[],max_output_tokens:2048});
    assert.equal(result.status,reason==='max_tokens'?'incomplete':'completed');
    assert.equal(result.incomplete_details?.reason,reason==='max_tokens'?'max_output_tokens':undefined);
  }
});
