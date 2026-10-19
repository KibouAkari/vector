export const CHAT_MODES = [
  {value:'auto',label:'Auto'}, {value:'quick',label:'Low'},
  {value:'normal',label:'Normal'}, {value:'deep',label:'High'},
  {value:'research',label:'Search'}, {value:'local',label:'Lokal'}
];

const FOLLOWUP=/^(?:(?:und|and)\s+)?(?:für|for|von)\s+([A-Za-z0-9_]{1,16})\s*[?!.]?$/i;
const METRIC=/\b(rekor[dt]e?n?|rekor[dt]halter(?:n)?|spitzenreiter|statistik(?:en)?|statistics|records?|mobkills|mob kills|spielzeit|playtime|strecke|distance|tode|deaths|spielerkills)\b/i;
const REFRESH=/^(?:bitte\s+)?(?:(?:check(?:e)?|prüf(?:e)?|überprüf(?:e)?|aktualisier(?:e)?)\s+(?:es|das|die\s+(?:statistik(?:en)?|rekorde|rekordhalter))\s*(?:(?:nochmals?|erneut|jetzt|neu|aktuell)\s*)?(?:(?:auf|von)\s+meinem\s+server)?|(?:nochmals?|erneut|neu)\s+(?:prüfen|checken|lesen|aktualisieren))\s*[?!.]?$/i;
const WORDS=new Set(('hi hey hallo bitte kannst könntest du mir ich möchte hätte gerne kann können den die das der dem des ein eine einen einem alle allen gesamte gesamten aktuelle aktuellen momentane momentanen besten beste bestes welche welchen welcher welches was wie viel viele wieviel ist sind hat haben zeigt zeige zeigen zeig gib geben gibt sag sage sagen vom von für auf meinem meinen meines mein unserem unseren unseres unser in im an am und oder zu zum zur über übersicht serverübersicht rangliste rang ränge platz plätze wer meisten meiste rekord rekorde rekorden rekort rekorte rekorten rekordhalter rekordhaltern rekorthalter spitzenreiter statistik statistiken statistics record records mobkills mob kills spielzeit playtime strecke distance tode deaths spielerkills spieler player server servers minecraft fegcraft einfach nur es hält kategorie kategorien jetzt aktuell nochmals nochmal erneut neu bitte please can could you me show give all current best which what is are has have of for on from the a an and who most').split(' '));
const NOT_TARGET=new Set(('mir die der das dem den des ein eine einen einem alle allen meinem meinen meines mein unserem unseren unseres unser minecraft fegcraft the a an all most me').split(' '));

function parseStatistics(text,previous) {
  const current=String(text || '').trim();
  if(!current || current.length>1200)return null;
  const followup=FOLLOWUP.exec(current);
  if(followup)return previous?{targets:[followup[1].toLowerCase()]}:null;
  if(REFRESH.test(current) || /^(?:ich meine|i mean)\s+(?:von|auf|from|on)\s+(?:meinem|my)\s+(?:minecraft[- ]?)?server\s*[?!.]?$/i.test(current))return previous?{targets:[...previous.targets]}:null;
  const normalized=current.replace(/fegcraft-updated/gi,'fegcraft').replace(/minecraft-server/gi,'minecraft server');
  const explicit=/\b(fegcraft|minecraft.{0,20}server|mein(?:em|en)? server)\b/i.test(normalized);
  if((!explicit&&!previous) || !METRIC.test(normalized))return null;
  if(/^(?:was ist (?:ein|eine)|was sind (?:rekorde|statistiken)|what is (?:a|an)|wie (?:funktioniert|funktionieren|berechnet)|how (?:do|does)|erklär(?:e)?)\b/i.test(normalized))return null;
  const targets=[];
  for(const match of normalized.matchAll(/\b(?:von|für|for|of|hat|has|spieler|player)\s+(?:(?:spieler|player)\s+)?([A-Za-z0-9_]{1,16})\b/gi)) {
    if(!NOT_TARGET.has(match[1].toLowerCase()))targets.push(match[1]);
  }
  const words=normalized.match(/[\p{L}\p{N}_-]+/gu) || [];
  // Inherit only the last uninterrupted native statistics task, never facts or
  // names from assistant text. Mixed mail/web/file/admin work keeps its tools.
  if(words.some(word=>!WORDS.has(word.toLowerCase())&&!targets.some(name=>name.toLowerCase()===word.toLowerCase())))return null;
  return {targets:[...new Set(targets.map(name=>name.toLowerCase()))]};
}

export function statisticsRequest(text,recentMessages=[]) {
  let previous=null;
  for(const message of recentMessages.filter(m=>m.role==='user'&&typeof m.content==='string').slice(-40))
    previous=parseStatistics(message.content,previous);
  return parseStatistics(text,previous);
}

export function localStatisticsIntent(text,recentMessages=[]) {
  return statisticsRequest(text,recentMessages)!==null;
}

export function requestDestination({mode='auto',text,recentMessages=[],allowServer=false,localEnabled=false,hasAttachments=false}) {
  if (!CHAT_MODES.some(option=>option.value===mode)) throw new Error('Unbekannter Chatmodus.');
  if(mode==='local') return 'local';
  return mode==='auto' && localEnabled && allowServer && !hasAttachments
    && localStatisticsIntent(text,recentMessages) ? 'local' : 'cloud';
}
