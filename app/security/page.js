import { requireSession } from "../../lib/auth";
import { redirect } from "next/navigation";
import Sidebar from "../../components/sidebar";
import SecurityScanner from "./security-scanner";
export const dynamic = "force-dynamic";
export default async function SecurityPage() {
  const session = await requireSession();
  if (!["owner", "admin"].includes(session.role)) redirect("/");
  return (
    <div className="vector-shell">
      <Sidebar session={session} />
      <main className="main">
        <SecurityScanner />
      </main>
    </div>
  );
}
