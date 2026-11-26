import {getSession} from '../../../../lib/auth';
import {PLATFORM_CAPABILITIES} from '../../../../lib/platform-catalog.mjs';
export const dynamic='force-dynamic';
export async function GET(){const session=await getSession();if(!session)return Response.json({error:'Unauthorized'},{status:401});if(session.role!=='owner')return Response.json({error:'Owner access required'},{status:403});return Response.json({inventoryType:'source-only',runtimeVerified:false,capabilities:PLATFORM_CAPABILITIES},{headers:{'Cache-Control':'private, no-store'}});}
