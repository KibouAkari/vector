export async function boundedJson(request,{maxBytes=16384,maxMs=5000}={}) {
  if(!request.body || request.headers.get('content-type')?.split(';')[0].trim().toLowerCase()!=='application/json')throw Error('INVALID_REQUEST');
  const reader=request.body.getReader();let timer;
  const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('REQUEST_LIMIT')),maxMs);});
  try {
    let size=0;const parts=[];
    while(true){const chunk=await Promise.race([reader.read(),deadline]);if(chunk.done)break;size+=chunk.value.byteLength;if(size>maxBytes)throw Error('REQUEST_LIMIT');parts.push(Buffer.from(chunk.value));}
    const value=JSON.parse(Buffer.concat(parts).toString('utf8'));
    if(!value||typeof value!=='object'||Array.isArray(value))throw Error('INVALID_REQUEST');return value;
  } finally {clearTimeout(timer);await reader.cancel().catch(()=>{});reader.releaseLock();}
}
