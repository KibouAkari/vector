import { requireSession } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import SkillsWorkspace from "./skills-workspace";
export const dynamic = "force-dynamic";
export default async function SkillsPage() {
  const session = await requireSession();
  return (
    <div className="vector-shell">
      <Sidebar session={session} />
      <main className="main">
        <SkillsWorkspace />
      </main>
    </div>
  );
}
