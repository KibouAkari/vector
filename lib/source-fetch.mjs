import http from 'node:http';
import https from 'node:https';
import {lookup} from 'node:dns/promises';
import {BlockList, isIP} from 'node:net';

export class SourceError extends Error {
  constructor(code) { super(code); this.name = 'SourceError'; this.code = code; }
}
const blocked = new BlockList();
for (const [ip, bits] of [['0.0.0.0',8],['10.0.0.0',8],['100.64.0.0',10],
  ['127.0.0.0',8],['169.254.0.0',16],['172.16.0.0',12],['192.0.0.0',24],
  ['192.0.2.0',24],['192.88.99.0',24],['192.168.0.0',16],['198.18.0.0',15],
  ['198.51.100.0',24],['203.0.113.0',24],['224.0.0.0',3]]) blocked.addSubnet(ip,bits,'ipv4');
const globalV6 = new BlockList();
globalV6.addSubnet('2000::',3,'ipv6');
// Conservative exclusions: special assignments, documentation and transition ranges.
for (const [ip,bits] of [['2001::',23],['2001:db8::',32],['2002::',16],['3fff::',20]]) blocked.addSubnet(ip,bits,'ipv6');

export function isPublicAddress(address) {
  const family = isIP(address);
  if (family === 4) return !blocked.check(address,'ipv4');
  return family === 6 && globalV6.check(address,'ipv6') && !blocked.check(address,'ipv6');
}

export function sourceUrl(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\u0000-\u0020\u007f\\]/.test(value)) throw new SourceError('INVALID_URL');
  let url;
  try { url = new URL(value); } catch { throw new SourceError('INVALID_URL'); }
  if (!['http:','https:'].includes(url.protocol) || url.username || url.password || url.port) throw new SourceError('INVALID_URL');
  const host = url.hostname.replace(/^\[|\]$/g,'');
  if (!host || host.endsWith('.') || (!isIP(host) && (!host.includes('.') || /\.(localhost|local|internal|test|invalid|example|onion)$/i.test(host)))) throw new SourceError('BLOCKED_ADDRESS');
  if (isIP(host) && !isPublicAddress(host)) throw new SourceError('BLOCKED_ADDRESS');
  url.hash = '';
  return url;
}

export async function publicDestination(url, resolve = lookup) {
  const host = url.hostname.replace(/^\[|\]$/g,'');
  let addresses;
  try { addresses = isIP(host) ? [{address:host, family:isIP(host)}] : await resolve(host,{all:true,verbatim:true}); }
  catch { throw new SourceError('DNS_FAILED'); }
  // Reject mixed public/private DNS answers as well as direct private addresses.
  if (!addresses.length || addresses.some(row => !isPublicAddress(row.address))) throw new SourceError('BLOCKED_ADDRESS');
  return addresses[0];
}

export function pinnedLookup(destination) {
  return (_hostname, options, callback) => {
    if (options?.all) callback(null,[destination]);
    else callback(null,destination.address,destination.family);
  };
}

const MAX_BYTES = 2 * 1024 * 1024;
export function requestSourcePage(url, destination, signal) {
  return new Promise((resolve,reject) => {
    const request = (url.protocol === 'https:' ? https : http).request(url,{
      method:'GET', agent:false, lookup:pinnedLookup(destination), signal,
      maxHeaderSize:16384,
      headers:{'User-Agent':'VectorSourceImporter/1.0','Accept':'text/html, text/plain, text/markdown','Accept-Encoding':'identity'}
    }, response => {
      if ([301,302,303,307,308].includes(response.statusCode)) {
        const location = response.headers.location;
        response.destroy();
        resolve({location,redirect:true});
        return;
      }
      if (response.statusCode !== 200) {
        response.destroy(); reject(new SourceError('HTTP_FAILED')); return;
      }
      const type = String(response.headers['content-type'] || '').toLowerCase();
      const mimeType = type.split(';')[0].trim();
      if (!['text/html','text/plain','text/markdown'].includes(mimeType)) {
        response.destroy(); reject(new SourceError('UNSUPPORTED_CONTENT')); return;
      }
      // No transparent decompression or archive/parser expansion on this path.
      if ((response.headers['content-encoding'] && response.headers['content-encoding'] !== 'identity') || Number(response.headers['content-length']) > MAX_BYTES) {
        response.destroy(); reject(new SourceError('CONTENT_LIMIT')); return;
      }
      const parts = [];
      let bytes = 0;
      response.on('data', chunk => {
        bytes += chunk.length;
        if (bytes > MAX_BYTES) { const error = new SourceError('CONTENT_LIMIT'); reject(error); response.destroy(error); return; }
        parts.push(chunk);
      });
      response.on('error',reject);
      response.on('aborted',() => reject(new SourceError('INCOMPLETE_RESPONSE')));
      response.on('end',() => resolve({buffer:Buffer.concat(parts),mimeType,contentType:type}));
    });
    request.on('error',reject);
    request.end();
  });
}

export async function fetchPublicSource(value, {resolve = lookup, request = requestSourcePage} = {}) {
  let url = sourceUrl(value);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(),15000);
  const abort = new Promise((_,reject) => controller.signal.addEventListener('abort',() => reject(new SourceError('FETCH_TIMEOUT')),{once:true}));
  try {
    for (let redirects = 0; redirects <= 3; redirects++) {
      const destination = await Promise.race([publicDestination(url,resolve),abort]);
      const page = await Promise.race([request(url,destination,controller.signal),abort]);
      if (!page.redirect) return {...page, finalUrl:url.href, fetchedAt:new Date().toISOString()};
      if (!page.location || redirects === 3) throw new SourceError('REDIRECT_LIMIT');
      let next;
      try { next = sourceUrl(new URL(page.location,url).href); } catch { throw new SourceError('BLOCKED_REDIRECT'); }
      if (url.protocol === 'https:' && next.protocol !== 'https:') throw new SourceError('BLOCKED_REDIRECT');
      url = next;
    }
  } catch (error) {
    if (error instanceof SourceError) throw error;
    throw new SourceError(controller.signal.aborted ? 'FETCH_TIMEOUT' : 'FETCH_FAILED');
  } finally { clearTimeout(timer); }
}
