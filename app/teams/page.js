import { requireFeature } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import Teams from "./teams-client";
export const dynamic = "force-dynamic";
export default async function Page() {
  const session = await requireFeature("projects");
  return (
    <div className="vector-shell">
      <Sidebar session={session} />
      <main className="main">
        <Teams canRun={session.role !== "readonly"} />
      </main>
    </div>
  );
}
