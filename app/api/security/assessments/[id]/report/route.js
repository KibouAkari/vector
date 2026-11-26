import {getSession} from '../../../../../../lib/auth';
import {getAssessment,assessmentOriginal} from '../../../../../../lib/security/store';
import {securityReport} from '../../../../../../lib/security/evidence.mjs';
import {renderSecurityPdf} from '../../../../../../lib/security/report-pdf.mjs';
export const runtime='nodejs';export const dynamic='force-dynamic';
export async function GET(request,context){
  const session=await getSession();if(!session)return new Response('Unauthorized',{status:401});if(session.role!=='owner')return new Response('Owner access required',{status:403});
  const {id}=await context.params;const assessment=await getAssessment(id);
  if(!assessment || assessment.status!=='completed')return new Response('Completed assessment not found',{status:404});
  const format=new URL(request.url).searchParams.get('format') || 'pdf';
  if(!['pdf','md','xml'].includes(format))return new Response('Unsupported report format',{status:400});
  const markdown=securityReport({scope:assessment.scope,result:assessment.result,approvedAt:assessment.approved_at?.toISOString?.() || assessment.approved_at,approvedBy:assessment.approved_by});
  const body=format==='pdf'?await renderSecurityPdf(markdown):format==='xml'?await assessmentOriginal(id):markdown;
  return new Response(body,{headers:{'Content-Type':format==='pdf'?'application/pdf':format==='md'?'text/markdown; charset=utf-8':'application/octet-stream','Content-Disposition':`attachment; filename="vector-security-report.${format}"`,'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"}});
}
