import test from 'node:test';
import assert from 'node:assert/strict';
import {conversationLabel,submitsOnEnter} from '../lib/chat-presentation.mjs';
test('chat titles make full and truncated privacy tokens readable without changing stored data',()=>{
 const stored='Write to <VEC_EMAIL_'+'a'.repeat(32)+'>';
 assert.equal(conversationLabel(stored),'Write to [email]');assert.equal(stored.includes('a'.repeat(32)),true);
 assert.equal(conversationLabel('Write to <VEC_EMAIL_'+'a'.repeat(17)),'Write to [email]');
 assert.equal(conversationLabel('Key: <VEC_API_KEY_'+'b'.repeat(12)+'…'),'Key: [API key]…');
 assert.equal(conversationLabel('A normal title'),'A normal title');assert.equal(conversationLabel(null),'New conversation');assert.equal(conversationLabel('',''),'');
});
test('Enter sends only after composition finishes; Shift Enter and IME confirmation stay in the editor',()=>{
 assert.equal(submitsOnEnter({key:'Enter'}),true);
 for(const event of [{key:'Enter',shiftKey:true},{key:'Enter',isComposing:true},{key:'Enter',nativeEvent:{isComposing:true}},{key:'Enter',keyCode:229},{key:'Enter',nativeEvent:{keyCode:229}},{key:'a'}])assert.equal(submitsOnEnter(event),false);
});
