"""Bounded local PERSON extraction. No network, routing, persistence or tools."""
from dataclasses import dataclass
import re

MAX_INPUT_BYTES = 160000
MAX_WORDS = 64
MAX_TEXT_TOKENS = 192
OVERLAP_WORDS = 12
MAX_CHUNKS = 1024
MAX_RECHECKS = 32

@dataclass(frozen=True)
class TextChunk:
    start: int
    end: int
    text: str
    text_tokens: int
    words: int


def split_context(text, splitter, encode):
    if not isinstance(text,str) or len(text.encode('utf8')) > MAX_INPUT_BYTES:
        raise ValueError('Context exceeds the local privacy input limit.')
    words=list(splitter(text))
    previous=0
    for word,start,end in words:
        if not isinstance(word,str) or not isinstance(start,int) or not isinstance(end,int) \
                or not previous<=start<end<=len(text) or text[start:end]!=word \
                or text[previous:start].strip():
            raise ValueError('Word splitter did not preserve the complete input.')
        previous=end
    if text[previous:].strip():
        raise ValueError('Word splitter omitted the end of the input.')
    chunks=[];index=0
    while index<len(words):
        end=min(index+MAX_WORDS,len(words))
        while end>index:
            start_char=words[index][1]
            end_char=words[end-1][2]
            part=text[start_char:end_char]
            token_count=len(encode(part))
            if token_count<=MAX_TEXT_TOKENS:break
            end-=1
        if end==index:
            raise ValueError('An individual word exceeds the safe model token budget.')
        chunks.append(TextChunk(start_char,end_char,part,token_count,end-index))
        if len(chunks)>MAX_CHUNKS:
            raise ValueError('Context needs too many model chunks.')
        if end==len(words):break
        index=max(index+1,end-OVERLAP_WORDS)
    return chunks


def exact_entities(text, chunk, entities):
    findings=[]
    for entity in entities:
        if not isinstance(entity,dict) or entity.get('label') not in ('person','organization','software'):
            raise ValueError('Unexpected entity result.')
        start,end=entity.get('start'),entity.get('end')
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(chunk.text) \
                or entity.get('text')!=chunk.text[start:end]:
            raise ValueError('Entity is not an exact input span.')
        if entity['label']!='person':continue
        value=text[chunk.start+start:chunk.start+end]
        if not 2<=len(value)<=2048:
            raise ValueError('Person span length is outside the privacy contract.')
        findings.append({'type':'PERSON','value':value})
    return findings


def focused_context(text,start,end,splitter,encode):
    """Use the original sentence or a bounded original word neighborhood."""
    if not 0<=start<end<=len(text):raise ValueError('Invalid context anchor.')
    begin=0;finish=len(text)
    for boundary in re.finditer(r'[.!?]+(?=\s|$)|[\r\n]+',text):
        if boundary.end()<=start:begin=boundary.end()
        elif boundary.start()>=end:
            finish=boundary.end();break
    while begin<start and text[begin].isspace():begin+=1
    while finish>end and text[finish-1].isspace():finish-=1
    part=text[begin:finish]
    words=list(splitter(part));count=len(encode(part))
    if len(words)<=MAX_WORDS and count<=MAX_TEXT_TOKENS:
        return TextChunk(begin,finish,part,count,len(words))
    words=list(splitter(text))
    left=next(i for i,w in enumerate(words) if w[2]>start)
    after=next((i for i,w in enumerate(words) if w[1]>=end),len(words))
    first=max(0,left-OVERLAP_WORDS);last=min(len(words),after+OVERLAP_WORDS)
    while first<=left and last>=after:
        begin=words[first][1];finish=words[last-1][2]
        part=text[begin:finish];count=len(encode(part))
        if last-first<=MAX_WORDS and count<=MAX_TEXT_TOKENS:
            return TextChunk(begin,finish,part,count,last-first)
        if left-first>=last-after and first<left:first+=1
        elif last>after:last-=1
        else:return None
    return None


class LocalPersonDetector:
    def __init__(self,model_dir='/models/entity'):
        # Imports are deferred so pure coverage/validation tests need no model.
        from pathlib import Path
        with (Path(model_dir)/'model.safetensors').open('rb') as handle:
            if not handle.read(8):raise ValueError('Empty model weights.')
        import torch
        from gliner import GLiNER
        torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(42)
        self.torch=torch
        self.model=GLiNER.from_pretrained(model_dir,local_files_only=True,map_location='cpu',strict=True).eval()
        if not 0<getattr(self.model.config,'max_width',0)<=OVERLAP_WORDS:
            raise ValueError('Model span width exceeds the verified chunk overlap.')
        if getattr(self.model.config,'max_len',0)<MAX_WORDS:
            raise ValueError('Model word budget is smaller than the chunk limit.')
        self.tokenizer=self.model.data_processor.transformer_tokenizer

    def inspect(self,text):
        splitter=self.model.data_processor.words_splitter
        encode=lambda value:self.tokenizer.encode(value,add_special_tokens=False,truncation=False)
        chunks=split_context(text,splitter,encode)
        findings=[];seen=set();rechecks={}
        def extract(chunk):
            with self.torch.inference_mode():
                # Retain complete names even when a nested first-name span has
                # a higher score. Keep the qualified confidence threshold.
                entities=self.model.predict_entities(chunk.text,['person','organization','software'],threshold=0.35,flat_ner=False)
            for finding in exact_entities(text,chunk,entities):
                key=(finding['type'],finding['value'])
                if key not in seen:
                    seen.add(key);findings.append(finding)
                    if len(findings)>100:raise ValueError('Too many private entities for a single review.')
            return entities
        primary_ranges={(c.start,c.end) for c in chunks}
        for chunk in chunks:
            entities=extract(chunk)
            if len(chunks)<=1:continue
            for entity in entities:
                if entity['label']!='person':continue
                window=focused_context(text,chunk.start+entity['start'],chunk.start+entity['end'],splitter,encode)
                if window and (window.start,window.end) not in primary_ranges:
                    rechecks[(window.start,window.end)]=window
                    if len(rechecks)>MAX_RECHECKS:raise ValueError('Too many focused contexts for a single review.')
        # One bounded, non-recursive second pass; existing findings remain.
        for window in rechecks.values():extract(window)
        processed=[*chunks,*rechecks.values()]
        return {'findings':findings,'chunks':len(processed),'primary_chunks':len(chunks),
            'context_rechecks':len(rechecks),'span_decoding':'nested',
            'processed_text_tokens':sum(c.text_tokens for c in processed),
            'token_count_kind':'raw_text_subwords_including_overlap_and_rechecks',
            'max_chunk_words':max((c.words for c in processed),default=0),
            'max_chunk_text_tokens':max((c.text_tokens for c in processed),default=0)}
