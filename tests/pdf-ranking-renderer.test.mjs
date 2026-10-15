
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as pdfLib from 'pdf-lib';
import {extractText} from 'unpdf';

const source=readFileSync(new URL('../lib/artifact-runtime.js',import.meta.url),'utf8')
  .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm,'')
  .replace(/^export\s+/gm,'')
  .replace(/await import\(\s*"pdf-lib"\s*\)/,'pdfLib');

test('block-bar recognition preserves quantities without interpreting ordinary content as a chart',()=>{
  const {pdfBarUnits}=new Function('pdfLib',source+'\nreturn {pdfBarUnits};')(pdfLib);
  assert.equal(pdfBarUnits('████'),4);
  assert.equal(pdfBarUnits('██▌'),2.5);
  for(const value of ['42','CPU 50%','????','█ label','', '▁▂▃'])assert.equal(pdfBarUnits(value),null);
});

test('real PDF renderer draws proportional vector bars and keeps all five ten-row categories',async()=>{
  const rectangles=[];
  const wrapped={...pdfLib,PDFDocument:{create:async()=>{
    const doc=await pdfLib.PDFDocument.create();
    const add=doc.addPage.bind(doc);
    doc.addPage=(...args)=>{
      const page=add(...args);
      const draw=page.drawRectangle.bind(page);
      page.drawRectangle=options=>{rectangles.push(options);return draw(options);};
      return page;
    };
    return doc;
  }}};
  const {createPdf}=new Function('pdfLib',source+'\nreturn {createPdf};')(wrapped);
  const content=['Playtime','Distance','Mob kills','Player kills','Deaths'].map((category,index)=>
    '## '+category+'\n\n| Rank | Player | Score | Comparison |\n| --- | --- | --- | --- |\n'+
    Array.from({length:10},(_,i)=>'| '+(i+1)+' | Fixture'+index+'Player'+(i+1)+' | '+(100-i)+' | '+ '█'.repeat(i===0?16:8)+' |').join('\n')
  ).join('\n\n');
  const bytes=await createPdf({title:'Synthetic rankings',content});
  const doc=await pdfLib.PDFDocument.load(bytes);
  assert.ok(doc.getPageCount()>=2);
  const result=await extractText(new Uint8Array(bytes),{mergePages:true});
  const text=Array.isArray(result.text)?result.text.join('\n'):result.text;
  for(const category of ['Playtime','Distance','Mob kills','Player kills','Deaths'])assert.ok(text.includes(category));
  for(let c=0;c<5;c++)for(let i=1;i<=10;i++)assert.ok(text.includes('Fixture'+c+'Player'+i));
  assert.ok(!text.includes('?'));
  const bars=rectangles.filter(x=>x.height===6);
  assert.equal(bars.length,100);
  assert.equal(bars[1].width,bars[0].width);
  assert.equal(bars[3].width,bars[2].width/2);
});
