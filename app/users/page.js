import { requireOwner } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import UsersClient from "./users-client";

export const dynamic = "force-dynamic";

export default async function UsersPage(){ const session=await requireOwner(); return <div className="vector-shell"><Sidebar session={session}/><main className="main v5-main"><UsersClient currentUserId={session.userId}/></main></div>; }
