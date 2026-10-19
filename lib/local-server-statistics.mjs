import {statisticsRequest} from './chat-controls.mjs';

function configuredSource() {
  const base=process.env.VECTOR_MINECRAFT_DATA_PATH || '';
  const relative=process.env.VECTOR_MINECRAFT_STATS_PATH || 'world/players/stats';
  if(!base.startsWith('/') || base.includes('\0') || base.split('/').includes('..')
    || !/^[A-Za-z0-9_./-]+$/.test(relative) || relative.startsWith('/') || relative.split('/').some(p=>!p || p==='..'))
    throw new Error('Die lokale Minecraft-Datenquelle ist nicht konfiguriert. Nutze Auto oder die vorhandenen Serverwerkzeuge.');
  return {base:base.replace(/\/$/,''),relative};
}
const METRICS=[
  ['Spielzeit',['play_time'],72000,'h'],
  ['Strecke',['walk_one_cm','sprint_one_cm','swim_one_cm','aviate_one_cm','boat_one_cm','horse_one_cm','minecart_one_cm'],100000,'km'],
  ['Mobkills',['mob_kills'],1,'Kills'],
  ['Spielerkills',['player_kills'],1,'Kills'],
  ['Tode',['deaths'],1,'Tode']
];
function items(value) {
  if(value?.complete!==true || value.truncated || value.scan_truncated || !Array.isArray(value.items)
    || !Number.isInteger(value.files_discovered) || value.files_discovered<1
    || value.files_discovered!==value.files_returned || value.items.length!==value.files_returned
    || value.items.some(item=>item.truncated || typeof item.content!=='string'))
    throw new Error('Die Statistikdateien konnten nicht vollständig gelesen werden. Es werden keine Rekorde behauptet.');
  return value.items;
}
const number=value=>new Intl.NumberFormat('de-CH',{maximumFractionDigits:1}).format(value);

// Fixed read-only data sources; neither a model nor user input chooses a path.
export async function localServerStatistics({text,recentMessages=[],allowServer=false,inspect,now=()=>new Date()}) {
  const request=statisticsRequest(text,recentMessages);
  if(!request) return null;
  if(!allowServer) throw new Error('Für diese Anfrage fehlt die Serverberechtigung.');
  const {base:BASE,relative}=configuredSource();
  const identities=items(await inspect({action:'read_many',path:BASE,pattern:'usercache.json',recursive:false,max_files:1}));
  if(identities.length!==1) throw new Error('Die Spielerzuordnung ist unvollständig.');
  const cache=JSON.parse(identities[0].content);
  if(!Array.isArray(cache)) throw new Error('Ungültige Spielerzuordnung.');
  const names=new Map();const unique=new Set();
  for(const entry of cache) {
    if(typeof entry.uuid!=='string' || !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(entry.uuid)
      || typeof entry.name!=='string' || !/^[A-Za-z0-9_]{1,16}$/.test(entry.name)
      || names.has(entry.uuid.toLowerCase()) || unique.has(entry.name.toLowerCase()))
      throw new Error('Die Spielerzuordnung ist nicht eindeutig.');
    names.set(entry.uuid.toLowerCase(),entry.name);unique.add(entry.name.toLowerCase());
  }
  const files=items(await inspect({action:'read_many',path:BASE+'/'+relative,pattern:'*.json',recursive:false,max_files:120}));
  const players=[];const ids=new Set();
  for(const item of files) {
    const id=String(item.relative_path || item.path || '').split('/').pop().replace(/\.json$/i,'').toLowerCase();
    const name=names.get(id);
    if(!name || ids.has(id)) throw new Error('Nicht alle Statistikdateien sind eindeutig einem Spieler zugeordnet.');
    ids.add(id);
    const document=JSON.parse(item.content);
    const stats=document?.stats?.['minecraft:custom'];
    if(!stats || typeof stats!=='object' || Array.isArray(stats)) throw new Error('Ungültige Statistikdatei.');
    const values=METRICS.map(([,keys,divisor])=>{
      let sum=0;
      for(const key of keys) {
        // Minecraft omits counters that have never been incremented.
        const raw=Object.hasOwn(stats,'minecraft:'+key)?stats['minecraft:'+key]:0;
        if(!Number.isSafeInteger(raw) || raw<0 || !Number.isSafeInteger(sum+raw)) throw new Error('Ungültiger Statistikwert.');
        sum+=raw;
      }
      return sum/divisor;
    });
    players.push({name,values});
  }
  const requested=request.targets.map(target=>{
    const name=[...names.values()].find(value=>value.toLowerCase()===target.toLowerCase());
    if(!name)throw new Error('Für diesen Spielernamen wurden keine zugeordneten Statistikdaten gefunden.');
    const player=players.find(value=>value.name===name);
    if(!player)throw new Error('Für diesen Spieler liegt keine Statistikdatei vor.');
    return player;
  });
  if(requested.length>1) throw new Error('Bitte frage nach einem einzelnen Spieler oder nach der Serverübersicht.');
  const leaders=METRICS.map((_,i)=>Math.max(...players.map(p=>p.values[i])));
  const lines=[];
  if(requested.length===1) {
    const player=requested[0];lines.push('**Minecraft · '+player.name+'**','','| Kategorie | Wert | Rang |','| :-- | --: | :-- |');
    METRICS.forEach(([label,, ,unit],i)=>{
      const rank=1+players.filter(p=>p.values[i]>player.values[i]).length;
      const record=player.values[i]>0 && player.values[i]===leaders[i];
      lines.push(`| ${label} | **${number(player.values[i])} ${unit}** | ${rank}${record?' · Rekord':''} |`);
    });
    if(!player.values.some((value,i)=>value>0 && value===leaders[i])) lines.push('','In diesen fünf Kategorien hält der Spieler derzeit keinen ersten Platz.');
  } else {
    lines.push('**Minecraft · Statistikübersicht**','','| Kategorie | Rekord | Spieler |','| :-- | --: | :-- |');
    METRICS.forEach(([label,,,unit],i)=>{
      const holders=players.filter(p=>p.values[i]===leaders[i]).map(p=>p.name).join(', ');
      lines.push(`| ${label} | **${number(leaders[i])} ${unit}** | ${leaders[i]>0?holders:'Noch kein positiver Rekord'} |`);
    });
  }
  const readAt=now().toISOString();
  lines.push('',`Datenstand: gespeicherte Serverdateien, gelesen ${readAt}. ${players.length} Spieler vollständig geprüft. Gleichstände teilen denselben Rang.`);
  lines.push('Für diese Anfrage frisch gelesen. Neue Spielaktionen sind erst nach dem Speichern durch Minecraft enthalten.');
  return {text:lines.join('\n'),files:players.length,readAt};
}
