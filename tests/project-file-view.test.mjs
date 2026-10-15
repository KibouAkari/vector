import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { filePreviewKind, visibleProjectFiles, projectDownloadDisposition } from '../lib/project-file-view.mjs';

test('only supported inline types enter the image and PDF preview', () => {
  assert.equal(filePreviewKind({mime_type: 'image/png'}), 'image');
  assert.equal(filePreviewKind({mime_type: 'application/pdf'}), 'pdf');
  assert.equal(filePreviewKind({mime_type: 'image/svg+xml'}), 'download');
  assert.equal(filePreviewKind({mime_type: 'text/plain', previewable: true}), 'text');
  assert.equal(filePreviewKind({mime_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}), 'download');
});

test('search and sorting preserve the original files and work with missing dates', () => {
  const files = [
    {id:'a', original_name:'Notes 10.md', size_bytes:2},
    {id:'b', original_name:'Notes 2.md', size_bytes:30, created_at:'2026-10-15T10:00:00Z'},
    {id:'c', original_name:'image.png', size_bytes:100, created_at:'invalid'}
  ];
  assert.deepEqual(visibleProjectFiles(files, ' NOTES ', 'name').map(x=>x.id), ['b','a']);
  assert.deepEqual(visibleProjectFiles(files, '', 'size').map(x=>x.id), ['c','b','a']);
  assert.equal(visibleProjectFiles(files)[0].id, 'b');
  assert.deepEqual(files.map(x=>x.id), ['a','b','c']);
  assert.deepEqual(visibleProjectFiles(files, 'missing'), []);
});

test('download filenames preserve Unicode without allowing header injection', () => {
  const value = projectDownloadDisposition('Grüsse "Plan"\r\nX-Test: injected.xlsx');
  const headers = new Headers({'Content-Disposition':value});
  assert.ok(!/[\r\n]/.test(value));
  assert.match(headers.get('Content-Disposition'), /^attachment; filename="/);
  assert.ok(value.includes('Gr%C3%BCsse'));
  assert.ok(projectDownloadDisposition("O'Brien.xlsx").endsWith("filename*=UTF-8''O%27Brien.xlsx"));
});

function downloadHandler({session, row, allowed = false}) {
  const calls = {queries: [], reads: 0, authorization: []};
  const source = readFileSync(new URL('../app/api/files/[id]/download/route.js', import.meta.url), 'utf8')
    .replace(/^import .*;\n/gm, '')
    .replace(/export const /g, 'const ')
    .replace('export async function GET', 'async function GET');
  const GET = new Function('deps', `
    const {getSession,canAccessProject,db,initializeFileDatabase,readEncryptedFile,projectDownloadDisposition}=deps;
    ${source}
    return GET;
  `)({
    getSession: async()=>session,
    canAccessProject: async(s,id)=>{calls.authorization.push([s,id]);return allowed;},
    db:{query:async(sql,params)=>{calls.queries.push([sql,params]);return {rows:row?[row]:[]};}},
    initializeFileDatabase:async()=>{},
    readEncryptedFile:async()=>{calls.reads++;return Buffer.from([0,255,1,13,10]);},
    projectDownloadDisposition
  });
  return {GET,calls};
}

test('anonymous and unrelated users cannot read or decrypt original files', async () => {
  for (const session of [null,{userId:'outsider'}]) {
    const {GET,calls} = downloadHandler({session,row:{project_id:'private',original_name:'secret.docx'}});
    const response = await GET(new Request('http://vector.test'),{params:Promise.resolve({id:'known-file'})});
    assert.equal(response.status,session?404:401);
    assert.equal(calls.reads,0);
    if (!session) assert.equal(calls.queries.length,0);
  }
});

test('authorized downloads return original binary bytes and safe response headers', async () => {
  const session={userId:'shared-viewer'};
  const {GET,calls} = downloadHandler({session,allowed:true,row:{project_id:'shared',original_name:'Report.xlsx'}});
  const response = await GET(new Request('http://vector.test'),{params:{id:'file-id'}});
  assert.equal(response.status,200);
  assert.deepEqual(new Uint8Array(await response.arrayBuffer()),new Uint8Array([0,255,1,13,10]));
  assert.deepEqual(calls.queries[0][1],['file-id']);
  assert.deepEqual(calls.authorization,[[session,'shared']]);
  assert.equal(response.headers.get('Content-Type'),'application/octet-stream');
  assert.equal(response.headers.get('Content-Length'),'5');
  assert.equal(response.headers.get('X-Content-Type-Options'),'nosniff');
  assert.equal(response.headers.get('Content-Security-Policy'),'sandbox');
});
