import {SourceError} from './source-fetch.mjs';
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[1-8][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/i;
export async function readSourceRequest(request) {
  if (!request.headers.get('content-type')?.toLowerCase().startsWith('application/json') || !request.body) throw new SourceError('INVALID_REQUEST');
  const reader = request.body.getReader();
  let timer;
  const timeout = new Promise((_,reject) => { timer=setTimeout(() => reject(new SourceError('INVALID_REQUEST')),5000); });
  try {
    let bytes=0;
    const parts=[];
    while (true) {
      const {value,done} = await Promise.race([reader.read(),timeout]);
      if (done) break;
      bytes+=value.byteLength;
      if (bytes>4096) throw new SourceError('INVALID_REQUEST');
      parts.push(Buffer.from(value));
    }
    let data;
    try { data=JSON.parse(Buffer.concat(parts).toString('utf8')); } catch { throw new SourceError('INVALID_REQUEST'); }
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new SourceError('INVALID_REQUEST');
    if (data.sourceId) {
      if (typeof data.sourceId !== 'string' || !UUID.test(data.sourceId) || data.url || data.requestId) throw new SourceError('INVALID_REQUEST');
      return {sourceId:data.sourceId};
    }
    if (typeof data.url !== 'string' || typeof data.requestId !== 'string' || !UUID.test(data.requestId)) throw new SourceError('INVALID_REQUEST');
    return {url:data.url,requestId:data.requestId};
  } finally { clearTimeout(timer); await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
