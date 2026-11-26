import {requireOwner} from '../../lib/auth';
import Sidebar from '../../components/sidebar';
import SecurityWorkspace from './security-workspace';
import '../platform/platform.css';
export const dynamic='force-dynamic';
export default async function SecurityPage(){const session=await requireOwner();return <div className="vector-shell"><Sidebar session={session}/><main className="main"><SecurityWorkspace/></main></div>;}
