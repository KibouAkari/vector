import { requireOwner } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import PoliciesClient from "./policies-client";
export const dynamic = "force-dynamic";
export default async function PermissionsPage() {
  const session = await requireOwner();
  return (
    <div className="vector-shell">
      <Sidebar session={session} />
      <main className="main">
        <PoliciesClient />
      </main>
    </div>
  );
}
