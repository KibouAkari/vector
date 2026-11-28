// Preserve complete reviewed text entries: selective consent is bound to exact
// messages, not a JSON serialization or truncated transformation of them.
export function teamMessages(messages,goal,maxBytes=24000){
 const task=String(goal||'');let used=Buffer.byteLength(task);const chosen=[],seen=new Set([task]);
 for(const message of [...messages].reverse()){
  if(!message||typeof message.content!=='string'||!['user','assistant','system'].includes(message.role)||seen.has(message.content))continue;
  const bytes=Buffer.byteLength(message.content);if(used+bytes>maxBytes)continue;
  chosen.unshift({role:message.role,content:message.content});used+=bytes;seen.add(message.content);
 }
 return [...chosen,{role:'user',content:task}];
}
export function nonReplayable(error){
 if(error?.vectorNonReplayableProviderAttempt)return error;
 const marked=error instanceof Error?error:new Error(String(error));
 try{Object.defineProperty(marked,'vectorNonReplayableProviderAttempt',{value:true});return marked;}
 catch{return Object.assign(new Error(marked.message,{cause:marked}),{code:marked.code,status:marked.status,vectorNonReplayableProviderAttempt:true});}
}
