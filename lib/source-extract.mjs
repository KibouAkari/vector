import {Parser} from 'htmlparser2';
import crypto from 'node:crypto';
import {SourceError} from './source-fetch.mjs';

export const SOURCE_TEXT_LIMIT = 180000;
export const sourceDigest = buffer => crypto.createHash('sha256').update(buffer).digest('hex');

export function extractSourceText({buffer,mimeType,contentType}) {
  if (!Buffer.isBuffer(buffer) || buffer.length > 2 * 1024 * 1024) throw new SourceError('CONTENT_LIMIT');
  const charset = contentType?.match(/charset\s*=\s*["']?([^\s;"']+)/i)?.[1] || 'utf-8';
  let input;
  try { input = new TextDecoder(charset,{fatal:true}).decode(buffer); }
  catch { throw new SourceError('UNSUPPORTED_ENCODING'); }
  let title = '';
  let text = '';
  const append = value => { text += value; };
  if (mimeType === 'text/html') {
    let ignored = 0;
    let elements = 0;
    let inTitle = false;
    const stack = [];
    const skip = new Set(['script','style','noscript','template','iframe','svg','nav','footer','form']);
    const breaks = new Set(['p','div','section','article','main','li','tr','h1','h2','h3','h4','pre','br']);
    const parser = new Parser({
      onopentag(name) {
        if (++elements > 50000 || stack.length > 128) throw new SourceError('EXTRACTION_LIMIT');
        stack.push({name,skip:skip.has(name)});
        if (skip.has(name)) ignored++;
        if (name === 'title') inTitle = true;
        if (!ignored && breaks.has(name)) append('\n');
      },
      ontext(value) {
        if (inTitle && !ignored) title += value;
        else if (!ignored) append(value);
      },
      onclosetag(name) {
        const current = stack.pop();
        if (current?.skip) ignored--;
        if (name === 'title') inTitle = false;
        if (!ignored && breaks.has(name)) append('\n');
      }
    },{decodeEntities:true});
    parser.write(input); parser.end();
  } else if (['text/plain','text/markdown'].includes(mimeType)) text = input;
  else throw new SourceError('UNSUPPORTED_CONTENT');
  text = text.replace(/\r\n?|[\u2028\u2029]/g,'\n').replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g,'');
  if (mimeType === 'text/html') text = text.replace(/[ \t]+/g,' ').replace(/ *\n */g,'\n').replace(/\n{3,}/g,'\n\n').trim();
  if (!text.trim()) throw new SourceError('NO_EXTRACTABLE_TEXT');
  const partial = text.length > SOURCE_TEXT_LIMIT;
  text = text.slice(0,SOURCE_TEXT_LIMIT);
  // Bounded physical lines keep the existing line-based project index bounded.
  text = text.split('\n').map(line => line.match(/.{1,2000}/gu)?.join('\n') || '').join('\n');
  return {text,title:title.replace(/\s+/g,' ').trim().slice(0,200),partial,
    method:mimeType === 'text/html' ? 'static-html-text-v1' : 'decoded-text-v1',
    rawSha256:sourceDigest(buffer),textSha256:sourceDigest(Buffer.from(text,'utf8'))};
}
