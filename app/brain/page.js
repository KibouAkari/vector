import { requireSession } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import Brain from "./brain-client";
export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await requireSession();
  return (
    <div className="vector-shell">
      <Sidebar session={session} />
      <main className="main">
        <Brain />
      </main>
    </div>
  );
}
