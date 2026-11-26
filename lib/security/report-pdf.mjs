import {PDFDocument,StandardFonts,rgb} from 'pdf-lib';
const printable=value=>String(value).replace(/\\([\\`*_{}[\]<>|#!])/g,'$1').replace(/[^\x20-\x7e\xa0-\xff]/g,'?');
export async function renderSecurityPdf(markdown) {
 const pdf=await PDFDocument.create();const normal=await pdf.embedFont(StandardFonts.Helvetica),bold=await pdf.embedFont(StandardFonts.HelveticaBold);
 pdf.setTitle(printable(markdown.split('\n')[0].replace(/^# /,'')));pdf.setAuthor('Vector Security Workspace');pdf.setSubject('Evidence-based assessment report');
 let page,y;const pages=[];
 function addPage(){page=pdf.addPage([595.28,841.89]);pages.push(page);y=782;page.drawText('VECTOR / SECURITY WORKSPACE',{x:48,y:808,size:8,font:bold,color:rgb(.24,.36,.31)});}
 function wrap(text,font,size,width){const lines=[];let line='';for(const word of printable(text).split(/\s+/)){
   if(line&&font.widthOfTextAtSize(line+' '+word,size)>width){lines.push(line);line='';}
   if(font.widthOfTextAtSize(word,size)>width){let segment='';for(const char of word){if(font.widthOfTextAtSize(segment+char,size)>width){lines.push(segment);segment='';}segment+=char;}line=segment;}
   else line=line?line+' '+word:word;
 }if(line)lines.push(line);return lines.length?lines:[''];}
 const widths=[132,62,211,90];let tableHeader;
 function row(cells,header=false){const font=header?bold:normal;const lines=cells.map((cell,i)=>wrap(cell,font,8,widths[i]-12));const height=Math.max(...lines.map(value=>value.length))*12+12;
   if(y-height<65){addPage();if(tableHeader&&!header)row(tableHeader,true);}
   if(header)page.drawRectangle({x:48,y:y-height+3,width:495,height,color:rgb(.91,.95,.93)});
   let x=48;for(let i=0;i<4;i++){for(let j=0;j<lines[i].length;j++)page.drawText(lines[i][j],{x:x+6,y:y-9-j*12,size:8,font,color:rgb(.1,.14,.12)});x+=widths[i];}
   y-=height;page.drawLine({start:{x:48,y},end:{x:543,y},thickness:.3,color:rgb(.78,.82,.8)});
 }
 addPage();
 for(const raw of markdown.split('\n')){
   if(raw.startsWith('|')){if(/^\|\s*---/.test(raw))continue;const cells=raw.split(/(?<!\\)\|/).slice(1,-1).map(value=>value.trim());if(cells.length!==4)continue;if(!tableHeader){tableHeader=cells;row(cells,true);}else row(cells);continue;}
   if(tableHeader){tableHeader=undefined;y-=10;}
   const heading=raw.startsWith('#'),font=heading?bold:normal,size=raw.startsWith('# ')?19:heading?12:9;
   if(heading&&y<110)addPage();
   if(!raw){y-=8;continue;}
   for(const line of wrap(raw.replace(/^#{1,6}\s*/,''),font,size,495)){if(y<65)addPage();page.drawText(line,{x:48,y,size,font,color:rgb(.1,.14,.12)});y-=size+5;}
   if(heading)y-=5;
 }
 pages.forEach((p,i)=>p.drawText(`${i+1} / ${pages.length}   |   Imported evidence; no automated vulnerability verdict`,{x:48,y:35,size:7,font:normal,color:rgb(.4,.45,.42)}));
 return Buffer.from(await pdf.save());
}
