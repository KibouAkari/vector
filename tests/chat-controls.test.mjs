import test from 'node:test';
import assert from 'node:assert/strict';
import {requestDestination,localStatisticsIntent,CHAT_MODES} from '../lib/chat-controls.mjs';
import {localServerStatistics} from '../lib/local-server-statistics.mjs';

const prompt='Gib mir die Rekorde und besten Statistiken von ExampleOne vom Minecraft Server';
const options={mode:'auto',text:prompt,allowServer:true,localEnabled:true};
const uuid=n=>'00000000-0000-0000-0000-'+String(n).padStart(12,'0');
function bulk(items){return {complete:true,files_discovered:items.length,files_returned:items.length,items};}
function fixtures({incomplete=false,invalid=false,tie=false,nullValue=false}={}) {
  const calls=[];
  const inspect=async args=>{
    calls.push(args);
    if(args.pattern==='usercache.json')return bulk([{content:JSON.stringify([{uuid:uuid(1),name:'ExampleOne'},{uuid:uuid(2),name:'ExampleTwo'}])}]);
    const data=bulk([1,2].map(n=>({relative_path:uuid(n)+'.json',content:JSON.stringify({stats:{'minecraft:custom':{
      'minecraft:play_time':nullValue?null:72000*n,'minecraft:mob_kills':invalid?-1:(tie?5:n*5)
    }}})})));
    return incomplete?{...data,truncated:true}:data;
  };
  return {calls,inspect};
}
test('Auto uses local statistics only with permission, availability and supported text',()=>{
  assert.deepEqual(CHAT_MODES.map(m=>m.label),['Auto','Low','Normal','High','Search','Lokal']);
  assert.equal(requestDestination(options),'local');
  for(const extra of [{allowServer:false},{localEnabled:false},{hasAttachments:true},{mode:'normal'},
    {mode:'research'},{text:'Schreibe eine kurze Mail'},{text:'Lies das Backupskript auf FEGCraft'},
    {text:'Erstelle ein PDF mit allen FEGCraft Rekorden'}, {text:'FEGCraft Statistiken und das Passwort anzeigen'}])
    assert.equal(requestDestination({...options,...extra}),'cloud');
  assert.equal(requestDestination({...options,mode:'local',localEnabled:false}),'local');
  assert.throws(()=>requestDestination({...options,mode:'unexpected'}));
});
test('unrelated new tasks do not inherit statistics but real player followups do',()=>{
  const recentMessages=[{role:'user',content:prompt}];
  assert.equal(localStatisticsIntent('und für ExampleTwo?',recentMessages),true);
  assert.equal(localStatisticsIntent('Schreibe eine Mail für ExampleTwo',recentMessages),false);
  assert.equal(localStatisticsIntent('Was ist ein Rekord in Minecraft?'),false);
});
test('actual read-only path returns exact player ranks, values, record and provenance',async()=>{
  const data=fixtures();
  const answer=await localServerStatistics({text:prompt,allowServer:true,inspect:data.inspect,now:()=>new Date('2026-10-16T00:00:00Z')});
  assert.match(answer.text,/FEGCraft · ExampleOne/);
  assert.match(answer.text,/Spielzeit \| \*\*1 h\*\* \| 2/);
  assert.match(answer.text,/Mobkills \| \*\*5 Kills\*\* \| 2/);
  assert.match(answer.text,/keinen ersten Platz/);
  assert.match(answer.text,/gespeicherte Serverdateien/);
  assert.match(answer.text,/2 Spieler vollständig geprüft/);
  assert.equal(data.calls.length,2);
  assert.ok(data.calls.every(c=>c.action==='read_many' && c.path.startsWith('/opt/fegcraft-updated/data')));
});
test('leader ties share first rank and zero counters are not positive records',async()=>{
  const {inspect}=fixtures({tie:true});
  const answer=await localServerStatistics({text:prompt,allowServer:true,inspect});
  assert.match(answer.text,/Mobkills \| \*\*5 Kills\*\* \| 1 · Rekord/);
  assert.doesNotMatch(answer.text,/Tode \|.*Rekord/);
});
test('unknown player including a name in the middle never returns unrelated leaders',async()=>{
  for(const text of ['Welche Rekorde hat Unknown auf FEGCraft?', 'Statistiken von Unknown vom Minecraft Server']){
    await assert.rejects(localServerStatistics({text,allowServer:true,inspect:fixtures().inspect}),/Spielernamen/);
  }
});
test('short player followup resolves current target against the previous real task',async()=>{
  const answer=await localServerStatistics({text:'und für ExampleTwo?',recentMessages:[{role:'user',content:prompt}],
    allowServer:true,inspect:fixtures().inspect});
  assert.match(answer.text,/FEGCraft · ExampleTwo/);
  assert.match(answer.text,/Spielzeit \| \*\*2 h\*\* \| 1 · Rekord/);
});
test('missing permission never reads, and incomplete or invalid data cannot establish a record',async()=>{
  const denied=fixtures();
  await assert.rejects(localServerStatistics({text:prompt,inspect:denied.inspect}),/Serverberechtigung/);
  assert.equal(denied.calls.length,0);
  for(const fixture of [{incomplete:true},{invalid:true},{nullValue:true}])
    await assert.rejects(localServerStatistics({text:prompt,allowServer:true,inspect:fixtures(fixture).inspect}));
});

const routerSource=await import('node:fs').then(fs=>fs.readFileSync(new URL('../lib/router.js',import.meta.url),'utf8'));
const router=await import('data:text/javascript;base64,'+Buffer.from(routerSource).toString('base64'));
test('Auto selects suitable existing cloud modes for German research and analysis',()=>{
  assert.equal(router.determineTaskMode({message:'Recherchiere aktuelle Preise'}),'research');
  assert.equal(router.determineTaskMode({message:'Erstelle eine vollständige Sicherheitsanalyse'}),'deep');
  assert.equal(router.determineTaskMode({message:'Lies den Status von meinem Server'}),'normal');
  assert.equal(router.determineTaskMode({message:'Danke'}),'quick');
  assert.equal(router.determineTaskMode({message:'Recherchiere aktuelle Preise',requestedMode:'quick'}),'quick');
});
