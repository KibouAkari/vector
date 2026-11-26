// Retry the exact same mutation after a lost acknowledgement or refresh failure.
export function assessmentDraft(previous,fields,{now=Date.now,requestId=()=>crypto.randomUUID()}={}){
 const fingerprint=JSON.stringify(fields);
 return previous?.fingerprint===fingerprint?previous:{fingerprint,payload:{...fields,expiresAt:new Date(now()+24*3600000).toISOString(),requestId:requestId()}};
}
