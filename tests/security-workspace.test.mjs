import test from 'node:test';
import assert from 'node:assert/strict';
import {PDFDocument} from 'pdf-lib';
import {assessmentScope,scopeDigest,parseNmapEvidence,securityReport} from '../lib/security/evidence.mjs';
import {renderSecurityPdf} from '../lib/security/report-pdf.mjs';
const scope=()=>assessmentScope({name:'Synthetic assessment',authorization:'Owned isolated test fixture',targets:['192.0.2.1','2001:db8::1'],expiresAt:new Date(Date.now()+3600000).toISOString()});
const xml=(ip='192.0.2.1')=>`<?xml version="1.0"?><!DOCTYPE nmaprun><nmaprun scanner="nmap" version="7.95"><host><status state="up"/><address addr="${ip}" addrtype="ipv4"/><ports><port protocol="tcp" portid="443"><state state="open"/><service name="https" product="Synthetic server" version="1.0"/></port></ports></host><runstats><finished exit="success"/></runstats></nmaprun>`;
test('scope is exact, bounded, canonical and expires; broad shell or DNS targets cannot enter it',()=>{
 const s=scope();assert.equal(s.targets.length,2);assert.equal(scopeDigest(s).length,64);
 for(const target of ['example.org','192.0.2.0/24','*','192.0.2.1; id','-iL /tmp/x'])assert.throws(()=>assessmentScope({...s,targets:[target]}),{code:'EXACT_IP_REQUIRED'});
 assert.throws(()=>assessmentScope({...s,expiresAt:'2000-01-01'}),{code:'INVALID_EXPIRY'});
 assert.throws(()=>assessmentScope({...s,targets:Array(33).fill('192.0.2.1')}),{code:'INVALID_SCOPE'});
});
test('XML yields informational evidence with missing-host coverage, never a fabricated vulnerability',()=>{
 const s=scope(),r=parseNmapEvidence(xml(),s);assert.equal(r.observations.length,1);assert.equal(r.observations[0].severity,'informational');assert.equal(r.coverage.complete,false);assert.deepEqual(r.coverage.missing,['2001:db8::1']);
 const md=securityReport({scope:s,result:r,approvedAt:'fixture date',approvedBy:'fixture reviewer'});assert.match(md,/INCOMPLETE/);assert.match(md,/not confirmed vulnerabilities/);assert.match(md,/user-supplied XML/);assert.ok(!md.includes('CVE-'));
});
test('out-of-scope, malformed, failed and entity-bearing results fail closed',()=>{
 assert.throws(()=>parseNmapEvidence(xml('192.0.2.2'),scope()),{code:'OUT_OF_SCOPE_EVIDENCE'});
 assert.throws(()=>parseNmapEvidence(xml().replace('exit="success"','exit="error"'),scope()),{code:'INCOMPLETE_NMAP_RUN'});
 assert.throws(()=>parseNmapEvidence(xml().replace('</host>',''),scope()),{code:'INVALID_NMAP_XML'});
 assert.throws(()=>parseNmapEvidence('<!DOCTYPE nmaprun SYSTEM "file:///etc/passwd">'+xml(),scope()),{code:'UNSAFE_XML'});
 assert.throws(()=>parseNmapEvidence('<!ENTITY xxe SYSTEM "https://private">'+xml(),scope()),{code:'UNSAFE_XML'});
 assert.throws(()=>parseNmapEvidence(xml().replace('portid="443"','portid="70000"'),scope()),{code:'INVALID_PORT'});
});
test('professional report produces a readable multi-page PDF without a provider call',async()=>{
 const s=scope(),r=parseNmapEvidence(xml(),s);r.observations=Array.from({length:90},(_,i)=>({...r.observations[0],port:i+1}));
 const bytes=await renderSecurityPdf(securityReport({scope:s,result:r,approvedAt:'2026-11-26',approvedBy:'Fixture reviewer'}));
 assert.match(bytes.toString('ascii',0,8),/%PDF/);const pdf=await PDFDocument.load(bytes);assert.ok(pdf.getPageCount()>1);assert.equal(pdf.getAuthor(),'Vector Security Workspace');
});
