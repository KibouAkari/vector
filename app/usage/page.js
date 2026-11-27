import { requireSession } from "../../lib/auth";
import Sidebar from "../../components/sidebar";
import UsageCalls from "./usage-calls";
import BudgetControls from "./budget-controls";
export const dynamic = "force-dynamic";
export default async function UsagePage() {
  const session = await requireSession();
  return (
    <div className="vector-shell">
      <Sidebar session={session} />
      <main className="main">
        <div className="ctl-page">
          <header className="ctl-page-header">
            <div>
              <h1>Usage & Budgets</h1>
              <p>Provider calls, token counters and spending controls.</p>
            </div>
          </header>
          <BudgetControls />
          <UsageCalls />
        </div>
      </main>
    </div>
  );
}
