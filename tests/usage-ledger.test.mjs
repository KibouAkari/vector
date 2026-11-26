import test from 'node:test';
import assert from 'node:assert/strict';
import {publicUsageCall,listUsageCalls} from '../lib/usage-ledger.mjs';
test('public ledger distinguishes reported, estimated and unknown and excludes private metadata',()=>{
 const row={id:'call_fixture',input_tokens:'12',output_tokens:'3',cached_tokens:'0',metadata:{kind:'provider-call',usageKnown:true,costStatus:'reported',costUsd:0.002,reportedCostUsd:0.002,usdToChfRate:0.8,prompt:'must stay private',apiKey:'fixture credential'}};
 const result=publicUsageCall(row);assert.equal(result.reportedCostUsd,0.002);assert.equal(result.estimatedCostUsd,null);assert.equal(result.inputTokens,12);assert.equal(result.convertedCostChf,0.0016);assert.ok(!JSON.stringify(result).includes('must stay private'));assert.ok(!JSON.stringify(result).includes('apiKey'));
 const unknown=publicUsageCall({...row,metadata:{costStatus:'incomplete'}});assert.equal(unknown.inputTokens,null);assert.equal(unknown.convertedCostChf,null);
 assert.equal(publicUsageCall({...row,metadata:{...row.metadata,usdToChfRate:null}}).convertedCostChf,null);
});
test('ledger pagination is bounded and scopes both rows and cursor ownership to the user',async()=>{
 const queries=[];const db={query:async(sql,args)=>{queries.push({sql,args});return {rows:Array.from({length:51},(_,i)=>({id:'call_'+i,metadata:{}})),rowCount:0};}};
 const page=await listUsageCalls(db,'alice');assert.equal(page.calls.length,50);assert.equal(page.nextCursor,'call_49');assert.match(queries[0].sql,/user_id=\$1/);assert.match(queries[0].sql,/LIMIT 51/);assert.deepEqual(queries[0].args,['alice',null]);
 await assert.rejects(listUsageCalls(db,'bob',{after:'call_1'}),/INVALID_CURSOR/);assert.deepEqual(queries[1].args,['call_1','bob']);
});
