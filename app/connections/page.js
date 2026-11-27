import { redirect } from "next/navigation";
import { requireSession } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import Connections from "./connections-client";
export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await requireSession();
  if (!["owner", "admin"].includes(session.role)) redirect("/");
  return (
    <div className="vector-shell">
      <Sidebar session={session} />
      <main className="main">
        <Connections />
      </main>
    </div>
  );
}
