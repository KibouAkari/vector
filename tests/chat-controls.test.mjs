import test from 'node:test';
import assert from 'node:assert/strict';
import {requestDestination,localStatisticsIntent,statisticsRequest,CHAT_MODES} from '../lib/chat-controls.mjs';
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

test('native statistics only accepts complete supported requests without secondary tasks',()=>{
  for(const text of ['Schreibe eine Mail über die Statistiken auf FEGCraft',
    'Zeige FEGCraft Statistiken und suche zusätzlich im Web',
    'FEGCraft Rekorde und erkläre Redstone', 'Wie funktioniert die Statistik auf dem Minecraft Server?'])
    assert.equal(requestDestination({...options,text}),'cloud',text);
  assert.equal(localStatisticsIntent('Zeige die Statistik von Spieler ExampleOne auf FEGCraft'),true);
});
test('player followups cannot jump past the latest standalone task',()=>{
  const recentMessages=[{role:'user',content:prompt},{role:'user',content:'Schreibe eine Mail für ExampleOne'}];
  assert.equal(localStatisticsIntent('und für ExampleTwo?',recentMessages),false);
  assert.equal(localStatisticsIntent('und für ExampleTwo?',[{role:'user',content:prompt},{role:'user',content:'für ExampleThree?'}]),true);
});
test('cached identity without a stats file is not a server overview',async()=>{
  const original=fixtures();
  const inspect=async args=>{
    const result=await original.inspect(args);
    if(args.pattern==='usercache.json') {
      const cache=JSON.parse(result.items[0].content);cache.push({uuid:uuid(3),name:'ExampleThree'});
      result.items[0].content=JSON.stringify(cache);
    }
    return result;
  };
  await assert.rejects(localServerStatistics({text:'Welche Rekorde hat ExampleThree auf FEGCraft?',allowServer:true,inspect}),/keine Statistikdatei/);
  for(const text of ['Wie viel Spielzeit hat Unknown auf FEGCraft?', 'Welche Tode hat Unknown auf FEGCraft?'])
    await assert.rejects(localServerStatistics({text,allowServer:true,inspect}),/Spielernamen/);
});

const {chatMenuPosition}=await import('../lib/chat-menu-position.mjs');
test('menu escapes panel clipping and stays within header, composer and narrow viewport bounds',()=>{
  const viewport={width:360,height:800};
  const header=chatMenuPosition({top:40,bottom:70,right:345},viewport,210);
  const composer=chatMenuPosition({top:740,bottom:770,right:345},viewport,210);
  assert.equal(header.position,'fixed');assert.ok(header.top>=78);
  assert.ok(composer.top+composer.maxHeight<=732);
  for(const rect of [{top:40,bottom:70,right:345},{top:740,bottom:770,right:345},{top:-100,bottom:-70,right:500}]) {
    const style=chatMenuPosition(rect,{width:200,height:180},210);
    assert.ok(style.left>=8);assert.ok(style.left+style.width<=192);
    assert.ok(style.top>=8);assert.ok(style.top+style.maxHeight<=172);
  }
});

test('record holders and explicit refresh stay local across the native conversation',async()=>{
  const recentMessages=[{role:'user',content:prompt},{role:'assistant',content:'Historical answer is not a data source.'}];
  for(const text of ['kannst du mir einfach nur alle rekordhalter geben?', 'wer hat die meisten mobkills?',
    'bitte checke es auf meinem server', 'bitte erneut prüfen']) {
    assert.equal(requestDestination({...options,text,recentMessages}),'local',text);
    recentMessages.push({role:'user',content:text});
  }
  const answer=await localServerStatistics({text:'kannst du mir einfach nur alle rekordhalter geben?',recentMessages,
    allowServer:true,inspect:fixtures().inspect});
  for(const metric of ['Spielzeit','Strecke','Mobkills','Spielerkills','Tode'])assert.match(answer.text,new RegExp('\\| '+metric+' \\|'));
  assert.match(answer.text,/Mobkills \| \*\*10 Kills\*\* \| ExampleTwo/);
  assert.match(answer.text,/frisch gelesen/);
  assert.doesNotMatch(answer.text,/Unbekannt/);
});

test('refresh and holder followups never cross a topic switch or include unsupported work',()=>{
  for(const text of ['alle Rekordhalter bitte','bitte checke es auf meinem server']) {
    assert.equal(localStatisticsIntent(text),false);
    assert.equal(localStatisticsIntent(text,[{role:'user',content:prompt},{role:'user',content:'Schreibe eine Mail'}]),false);
  }
  for(const text of ['Alle Rekordhalter und das Passwort', 'Bitte checke es und lösche Dateien',
    'Statistiken und erkläre Redstone','Alle Rekordhalter als PDF'])
    assert.equal(localStatisticsIntent(text,[{role:'user',content:prompt}]),false,text);
});

test('each completed statistics query rereads changed source files and returns new provenance',async()=>{
  let kills=10;let reads=0;
  const original=fixtures();
  const inspect=async args=>{
    reads++;const data=await original.inspect(args);
    if(args.pattern==='*.json') {
      const document=JSON.parse(data.items[1].content);document.stats['minecraft:custom']['minecraft:mob_kills']=kills;
      data.items[1].content=JSON.stringify(document);
    }
    return data;
  };
  const request={text:'Zeige alle Rekordhalter auf FEGCraft',allowServer:true,inspect};
  const first=await localServerStatistics({...request,now:()=>new Date('2026-10-17T00:00:00Z')});
  kills=25;
  const next=await localServerStatistics({...request,now:()=>new Date('2026-10-17T00:01:00Z')});
  assert.equal(reads,4);assert.match(first.text,/10 Kills/);assert.match(next.text,/25 Kills/);
  assert.equal(first.readAt,'2026-10-17T00:00:00.000Z');assert.equal(next.readAt,'2026-10-17T00:01:00.000Z');
  assert.match(next.text,/erst nach dem Speichern durch Minecraft/);
});


test('an own-server correction retains only an uninterrupted statistics task',()=>{
  const history=[{role:'user',content:'Welche Rekorde hat ExampleOne auf meinem Minecraft Server?'}];
  assert.deepEqual(statisticsRequest('ich meine von meinem server',history),{targets:['exampleone']});
  assert.equal(statisticsRequest('ich meine von meinem server',[...history,{role:'user',content:'Schreibe eine Mail'}]),null);
});
