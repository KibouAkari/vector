import test from 'node:test';
import assert from 'node:assert/strict';
import ExcelJS from 'exceljs';
test('patched UUID dependency retains XLSX conditional-format generation and round trips',async()=>{
  const workbook=new ExcelJS.Workbook();
  const sheet=workbook.addWorksheet('Synthetic');sheet.addRow(['Name','Count']);sheet.addRow(['Fixture',42]);
  sheet.addConditionalFormatting({ref:'B2',rules:[{type:'dataBar',minLength:0,maxLength:100,gradient:true,
    cfvo:[{type:'min'},{type:'max'}],color:{argb:'FF8DE0B7'}}]});
  const buffer=await workbook.xlsx.writeBuffer();
  const parsed=new ExcelJS.Workbook();await parsed.xlsx.load(buffer);
  assert.equal(parsed.getWorksheet('Synthetic').getCell('B2').value,42);
});
