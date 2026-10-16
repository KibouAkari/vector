import importlib.util
from pathlib import Path
import re
import sys
import unittest
from types import SimpleNamespace
from contextlib import nullcontext
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('privacy_ner_core',ROOT/'lib/privacy-ner-core.py')
core=importlib.util.module_from_spec(spec);sys.modules[spec.name]=core;spec.loader.exec_module(core)

def splitter(text):
    return ((m.group(),m.start(),m.end()) for m in re.finditer(r'\w+(?:[-_]\w+)*|\S',text))

class ContextTests(unittest.TestCase):
    def test_full_coverage_and_overlap_without_truncation(self):
        text='  '+' '.join('word'+str(i) for i in range(600))+'  '
        chunks=core.split_context(text,splitter,lambda t:t.split())
        self.assertGreater(len(chunks),1)
        covered=set()
        for c in chunks:
            self.assertEqual(c.text,text[c.start:c.end]);self.assertLessEqual(c.words,64)
            covered.update(range(c.start,c.end))
        self.assertTrue(all(i in covered for i,c in enumerate(text) if not c.isspace()))
        for left,right in zip(chunks,chunks[1:]):
            self.assertEqual(len(list(splitter(text[right.start:left.end]))),12)

    def test_subword_budget_shrinks_chunks_and_oversized_word_blocks(self):
        chunks=core.split_context(' '.join('abcdefgh' for _ in range(80)),splitter,list)
        self.assertTrue(all(c.text_tokens<=192 for c in chunks))
        self.assertTrue(all(c.words<64 for c in chunks))
        with self.assertRaises(ValueError):core.split_context('x'*193,splitter,list)

    def test_unicode_offsets_are_exact_and_bad_model_spans_block(self):
        text='😀 Nachricht an Zoë Beispiel.'
        chunk=core.TextChunk(2,len(text),text[2:],5,5)
        start=chunk.text.index('Zoë')
        entity=dict(label='person',start=start,end=start+len('Zoë Beispiel'),text='Zoë Beispiel')
        self.assertEqual(core.exact_entities(text,chunk,[entity]),[dict(type='PERSON',value='Zoë Beispiel')])
        with self.assertRaises(ValueError):core.exact_entities(text,chunk,[dict(entity,text='Zoe Beispiel')])
        self.assertEqual(core.exact_entities(text,chunk,[dict(entity,label='software')]),[])

    def test_focused_sentence_keeps_only_original_context_and_long_window_is_bounded(self):
        text='Allgemeine Notiz. '*170+'Bitte schreibe an Zoë Beispiel.'
        start=text.index('Zoë')
        window=core.focused_context(text,start,start+3,splitter,lambda s:s.split())
        self.assertEqual(window.text,'Bitte schreibe an Zoë Beispiel.')
        self.assertEqual(window.text,text[window.start:window.end])
        long='Wort '*200+'Zoë Beispiel '+'Wort '*200
        start=long.index('Zoë')
        window=core.focused_context(long,start,start+3,splitter,lambda s:s.split())
        self.assertIn('Zoë Beispiel',window.text)
        self.assertLessEqual(window.words,64)
        self.assertLessEqual(window.text_tokens,192)
        self.assertEqual(window.text,long[window.start:window.end])

    def fake_detector(self,predict):
        detector=object.__new__(core.LocalPersonDetector)
        detector.torch=SimpleNamespace(inference_mode=nullcontext)
        detector.tokenizer=SimpleNamespace(encode=lambda text,**_:text.split())
        detector.model=SimpleNamespace(data_processor=SimpleNamespace(words_splitter=splitter),predict_entities=predict)
        return detector

    def test_nested_decoding_retains_source_confirmed_full_name_and_first_name(self):
        def predict(text,labels,threshold,flat_ner=True):
            start=text.index('Zoë')
            short=dict(label='person',start=start,end=start+3,text='Zoë')
            full=dict(label='person',start=start,end=start+12,text='Zoë Beispiel')
            return [short] if flat_ner else [short,full]
        report=self.fake_detector(predict).inspect('Bitte schreibe an Zoë Beispiel.')
        self.assertEqual({f['value'] for f in report['findings']},{'Zoë','Zoë Beispiel'})
        self.assertEqual(report['context_rechecks'],0)

    def test_focused_rechecks_are_nonrecursive_counted_and_bounded(self):
        calls=[]
        def predict(text,labels,threshold,flat_ner=True):
            calls.append(text)
            match=re.search(r'Anna\d+',text)
            if not match:return []
            return [dict(label='person',start=match.start(),end=match.end(),text=match.group())]
        text=' '.join('Anna'+str(i)+' hat Geburtstag.' for i in range(80))
        report=self.fake_detector(predict).inspect(text)
        self.assertEqual(len(calls),report['primary_chunks']+report['context_rechecks'])
        self.assertGreater(report['context_rechecks'],0)
        self.assertEqual(report['processed_text_tokens'],sum(len(t.split()) for t in calls))
        with patch.object(core,'MAX_RECHECKS',1):
            with self.assertRaises(ValueError):self.fake_detector(predict).inspect(text)

    def test_bad_splitter_omissions_and_input_limits_block(self):
        with self.assertRaises(ValueError):core.split_context('Anna',lambda _:[],list)
        with self.assertRaises(ValueError):core.split_context('Anna Mia',lambda _:[('Mia',5,8)],list)
        with self.assertRaises(ValueError):core.split_context('x'*160001,splitter,list)
        self.assertEqual(core.split_context(' \n\t',splitter,list),[])

if __name__=='__main__':unittest.main()
