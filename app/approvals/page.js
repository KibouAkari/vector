import { requireOwner } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import ApprovalQueue from "./approval-queue";
export const dynamic = "force-dynamic";
export default async function ApprovalsPage() {
  const session = await requireOwner();
  return (
    <div className="vector-shell">
      <Sidebar session={session} />
      <main className="main">
        <ApprovalQueue />
      </main>
    </div>
  );
}
