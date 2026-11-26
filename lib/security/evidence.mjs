import crypto from 'node:crypto';
import {isIP} from 'node:net';
import {SaxesParser} from 'saxes';

export class SecurityInputError extends Error {
  constructor(code) {super(code);this.code=code;this.name='SecurityInputError';}
}
export const evidenceHash=value=>crypto.createHash('sha256').update(value).digest('hex');
export function canonicalTarget(value) {
  if(typeof value!=='string' || !isIP(value)) throw new SecurityInputError('EXACT_IP_REQUIRED');
  return isIP(value)===4 ? value : new URL(`http://[${value}]/`).hostname.slice(1,-1);
}
export function assessmentScope(input,now=Date.now()) {
  if(!input || typeof input!=='object') throw new SecurityInputError('INVALID_SCOPE');
  const name=String(input.name || '').trim();
  const authorization=String(input.authorization || '').trim();
  if(name.length<3 || name.length>160 || authorization.length<15 || authorization.length>2000) throw new SecurityInputError('INVALID_SCOPE');
  if(!Array.isArray(input.targets) || input.targets.length<1 || input.targets.length>32) throw new SecurityInputError('INVALID_SCOPE');
  const targets=[...new Set(input.targets.map(canonicalTarget))].sort();
  const expires=new Date(input.expiresAt).getTime();
  if(!Number.isFinite(expires) || expires<=now || expires>now+7*86400000) throw new SecurityInputError('INVALID_EXPIRY');
  return {name,authorization,targets,expiresAt:new Date(expires).toISOString(),method:'imported-nmap-xml-v1'};
}
export const scopeDigest=scope=>evidenceHash(JSON.stringify(scope));
const clean=value=>String(value || '').replace(/[\u0000-\u001f\u007f]/g,' ').slice(0,300);
export function parseNmapEvidence(xml,scope) {
  if(typeof xml!=='string' || Buffer.byteLength(xml,'utf8')>2*1024*1024) throw new SecurityInputError('EVIDENCE_LIMIT');
  if(/<!ENTITY/i.test(xml) || /<!DOCTYPE(?!\s+nmaprun\s*>)/i.test(xml)) throw new SecurityInputError('UNSAFE_XML');
  const allowed=new Set(scope.targets);
  const hosts=[];const stack=[];
  let host,port,root=false,finished=false,finishCount=0,runstatsCount=0,nodes=0,version='';
  const parser=new SaxesParser({xmlns:false});
  parser.on('opentag',tag=>{
    if(++nodes>50000 || stack.length>64) throw new SecurityInputError('EVIDENCE_LIMIT');
    const parent=stack.at(-1);stack.push(tag.name);
    if(stack.length===1) {
      if(tag.name!=='nmaprun' || tag.attributes.scanner!=='nmap' || root) throw new SecurityInputError('INVALID_NMAP_XML');
      root=true;version=clean(tag.attributes.version);
    }
    if(tag.name==='host' && parent==='nmaprun') host={addresses:[],state:'unknown',ports:[]};
    if(host && tag.name==='status' && parent==='host') host.state=clean(tag.attributes.state);
    if(host && tag.name==='address' && parent==='host' && ['ipv4','ipv6'].includes(tag.attributes.addrtype)) {
      const ip=canonicalTarget(tag.attributes.addr);
      if(!allowed.has(ip)) throw new SecurityInputError('OUT_OF_SCOPE_EVIDENCE');
      host.addresses.push(ip);
    }
    if(host && tag.name==='port' && parent==='ports') {
      const number=Number(tag.attributes.portid);
      if(!Number.isInteger(number)||number<1||number>65535||!['tcp','udp','sctp'].includes(tag.attributes.protocol)) throw new SecurityInputError('INVALID_PORT');
      port={port:number,protocol:tag.attributes.protocol,state:'unknown',service:'',product:'',version:''};
    }
    if(port && tag.name==='state' && parent==='port') port.state=clean(tag.attributes.state);
    if(port && tag.name==='service' && parent==='port') {
      for(const field of ['product','version'])port[field]=clean(tag.attributes[field]);
      port.service=clean(tag.attributes.name);
    }
    if(tag.name==='runstats' && (stack.join('/')!=='nmaprun/runstats' || ++runstatsCount!==1))throw new SecurityInputError('INCOMPLETE_NMAP_RUN');
    if(tag.name==='finished') {
      if(stack.join('/')!=='nmaprun/runstats/finished' || ++finishCount!==1 || tag.attributes.exit!=='success')throw new SecurityInputError('INCOMPLETE_NMAP_RUN');
      finished=true;
    }
  });
  parser.on('closetag',tag=>{
    if(tag.name==='port' && port && host) {if(host.ports.some(p=>p.port===port.port&&p.protocol===port.protocol))throw new SecurityInputError('DUPLICATE_PORT');host.ports.push(port);if(hosts.reduce((n,h)=>n+h.ports.length,0)+host.ports.length>2048)throw new SecurityInputError('EVIDENCE_LIMIT');port=null;}
    if(tag.name==='host' && host) {
      if(!host.addresses.length)throw new SecurityInputError('MISSING_HOST_ADDRESS');
      if(hosts.some(row=>row.addresses.some(ip=>host.addresses.includes(ip))))throw new SecurityInputError('DUPLICATE_HOST');
      host.addresses=[...new Set(host.addresses)].sort();hosts.push(host);host=null;
    }
    stack.pop();
  });
  try {parser.write(xml).close();} catch(error) {
    if(error instanceof SecurityInputError)throw error;
    throw new SecurityInputError('INVALID_NMAP_XML');
  }
  if(!root || !finished || stack.length)throw new SecurityInputError('INCOMPLETE_NMAP_RUN');
  const seen=new Set(hosts.flatMap(row=>row.addresses));
  const missing=scope.targets.filter(ip=>!seen.has(ip));
  const observations=hosts.flatMap(row=>row.addresses.flatMap(target=>row.ports.filter(p=>p.state==='open').map(p=>({target,...p,severity:'informational'}))));
  if(observations.length>4096)throw new SecurityInputError('EVIDENCE_LIMIT');
  return {schemaVersion:1,tool:'nmap',toolVersion:version,evidenceSha256:evidenceHash(xml),
    importedAt:new Date().toISOString(),provenance:'user-supplied-tool-output',
    coverage:{requested:scope.targets.length,reported:seen.size,missing,complete:missing.length===0},hosts,observations};
}
const escaped=value=>String(value ?? '').replace(/[\\`*_{}[\]<>|#!]/g,'\\$&').replace(/[\r\n]/g,' ');
export function securityReport({scope,result,approvedAt,approvedBy}) {
  const lines=[`# ${escaped(scope.name)}`,'','## Executive summary','',
    `Imported Nmap evidence contains ${result.observations.length} open-port observations across ${result.coverage.reported} reported scope addresses.`,
    'Open ports are informational observations, not confirmed vulnerabilities. This report does not establish exploitability or a clean security posture.','',
    '## Scope and authorization','',`Targets: ${scope.targets.map(escaped).join(', ')}`,
    `Authorization reference: ${escaped(scope.authorization)}`,`Approved by: ${escaped(approvedBy)} at ${escaped(approvedAt)}`,
    `Authorization expires: ${escaped(scope.expiresAt)}`,'','## Evidence and coverage','',
    `Tool: Nmap ${escaped(result.toolVersion)}`,`Imported at: ${escaped(result.importedAt)}`,
    `Evidence SHA-256: ${result.evidenceSha256}`,
    'Provenance: user-supplied XML. Vector parsed this evidence locally; it did not execute or independently attest the scan.',
    `Coverage: ${result.coverage.complete?'all requested addresses have a host record':'INCOMPLETE; no whole-scope conclusion is permitted'}.`,
    `Missing addresses: ${result.coverage.missing.map(escaped).join(', ') || 'None'}`,'','## Observations','',
    '| Target | Port | Service evidence | Classification |','| --- | --- | --- | --- |'];
  for(const row of result.observations) {
    for(const target of row.target.split(', ')) {
      lines.push(`| ${escaped(target)} | ${row.port}/${row.protocol} | ${escaped([row.service,row.product,row.version].filter(Boolean).join(' '))} | Informational |`);
    }
  }
  if(!result.observations.length)lines.push('| No open ports reported | | | No claim that the target is secure |');
  lines.push('','## Recommended review','',
    '1. Confirm each exposed service is intended and owned by the assessed organization.',
    '2. Validate versions and configuration through authorized evidence before assigning a vulnerability or severity.',
    '3. Compare confirmed findings against the agreed scope and remediation priorities.','',
    '## Limitations','',
    'Imported evidence can be incomplete, stale or fabricated. No exploitation, authenticated testing, web application assessment or CVE verification was performed by this report generator. Missing services or findings are not evidence of absence.');
  return lines.join('\n');
}
