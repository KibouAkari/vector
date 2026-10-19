// Keep the current user input byte-for-byte and discard oldest complete turns.
// Never pass a partial assistant turn or silently truncate the current request.
export function boundedLocalContext(messages, maxBytes=6000) {
  if(!Array.isArray(messages) || !Number.isSafeInteger(maxBytes) || maxBytes<1)
    throw new Error('Invalid local context budget.');
  const last=messages.findLastIndex(message=>message.role==='user');
  if(last<0) throw new Error('Der lokale Chat benötigt eine aktuelle Nachricht.');
  const current=messages.slice(last,last+1);
  const size=value=>Buffer.byteLength(JSON.stringify(value));
  if(size(current)>maxBytes)
    throw new Error('Die aktuelle Nachricht ist zu gross für den lokalen Textkontext (6 KB). Bitte kürze diese Nachricht.');
  let selected=current;
  let cursor=last;
  while(cursor>0) {
    let start=cursor-1;
    while(start>=0 && messages[start].role!=='user')start--;
    if(start<0)break;
    const candidate=[...messages.slice(start,cursor),...selected];
    if(size(candidate)>maxBytes)break;
    selected=candidate;cursor=start;
  }
  return {messages:selected,omittedMessages:last+1-selected.length};
}
