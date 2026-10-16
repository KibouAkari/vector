export const CHAT_MODES = [
  {value:'auto',label:'Auto'}, {value:'quick',label:'Low'},
  {value:'normal',label:'Normal'}, {value:'deep',label:'High'},
  {value:'research',label:'Search'}, {value:'local',label:'Lokal'}
];

export function localStatisticsIntent(text, recentMessages=[]) {
  const current=String(text || '').trim();
  if(/\b(pdf|docx|xlsx|csv|datei|files?|skript|scripts?|logs?|backup|konfiguration|configuration|seed|passw(?:ort|örter)|passwords?|tokens?|api.?keys?)\b/i.test(current)) return false;
  const previous=recentMessages.filter(m=>m.role==='user').slice(-3).map(m=>m.content).join('\n');
  const followup=/^(?:(?:und|and)\s+)?(?:für|for|von)\s+[A-Za-z0-9_]{1,16}\s*[?!.]?$/i.test(current);
  const subject=/\b(fegcraft|minecraft.{0,20}server|mein(?:em|en)? server)\b/i;
  const metric=/\b(rekor[dt]e?n?|statistik\w*|statistics|records?|mobkills|mob kills|spielzeit|playtime|strecke|distance|tode|deaths|spielerkills)\b/i;
  return (subject.test(current) && metric.test(current)) || (followup && subject.test(previous) && metric.test(previous));
}

export function requestDestination({mode='auto',text,recentMessages=[],allowServer=false,localEnabled=false,hasAttachments=false}) {
  if (!CHAT_MODES.some(option=>option.value===mode)) throw new Error('Unbekannter Chatmodus.');
  if(mode==='local') return 'local';
  return mode==='auto' && localEnabled && allowServer && !hasAttachments
    && localStatisticsIntent(text,recentMessages) ? 'local' : 'cloud';
}
