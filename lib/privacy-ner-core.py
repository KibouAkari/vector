"""Bounded local PERSON extraction. No network, routing, persistence or tools."""
from dataclasses import dataclass
import re

MAX_INPUT_BYTES = 160000
MAX_WORDS = 64
MAX_TEXT_TOKENS = 192
OVERLAP_WORDS = 12
MAX_CHUNKS = 1024

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


class LocalPersonDetector:
    def __init__(self,model_dir='/models/entity',tokenizer_dir='/models/backbone'):
        # Imports are deferred so pure coverage/validation tests need no model.
        from pathlib import Path
        with (Path(model_dir)/'model.safetensors').open('rb') as handle:
            if not handle.read(8):raise ValueError('Empty model weights.')
        import torch
        from gliner import GLiNER
        from transformers import AutoTokenizer
        torch.set_num_threads(2);torch.set_num_interop_threads(1);torch.manual_seed(42)
        self.torch=torch
        self.model=GLiNER.from_pretrained(model_dir,local_files_only=True,map_location='cpu',strict=True).eval()
        if not 0<getattr(self.model.config,'max_width',0)<=OVERLAP_WORDS:
            raise ValueError('Model span width exceeds the verified chunk overlap.')
        if getattr(self.model.config,'max_len',0)<MAX_WORDS:
            raise ValueError('Model word budget is smaller than the chunk limit.')
        self.tokenizer=AutoTokenizer.from_pretrained(tokenizer_dir,local_files_only=True)

    def inspect(self,text):
        chunks=split_context(text,self.model.data_processor.words_splitter,
            lambda value:self.tokenizer.encode(value,add_special_tokens=False,truncation=False))
        findings=[];seen=set()
        for chunk in chunks:
            with self.torch.inference_mode():
                entities=self.model.predict_entities(chunk.text,['person','organization','software'],threshold=0.35)
            for finding in exact_entities(text,chunk,entities):
                key=(finding['type'],finding['value'])
                if key not in seen:
                    seen.add(key);findings.append(finding)
                    if len(findings)>100:
                        raise ValueError('Too many private entities for a single review.')
        return {'findings':findings,'chunks':len(chunks),
            # Actual raw-text tokenizer counts including overlap, not provider
            # billing tokens or the model's label/special-token overhead.
            'processed_text_tokens':sum(c.text_tokens for c in chunks),
            'token_count_kind':'raw_text_subwords_including_overlap',
            'max_chunk_words':max((c.words for c in chunks),default=0),
            'max_chunk_text_tokens':max((c.text_tokens for c in chunks),default=0)}
