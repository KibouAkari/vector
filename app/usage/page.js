import {
  requireSession
} from "../../lib/auth";

import {
  getCostLimits,
  getCurrentUsage
} from "../../lib/cost";

import Sidebar
  from "../../components/sidebar";

export const dynamic = "force-dynamic";

function money(value) {
  return `CHF ${Number(value).toFixed(2)}`;
}

export default async function UsagePage() {
  const session =
    await requireSession();

  const limits =
    getCostLimits();

  const usage =
    await getCurrentUsage();

  return (
    <div className="vector-shell">

      <Sidebar session={session} />

      <main className="main">

        <div className="content-container">

          <header className="control-header">

            <div className="eyebrow">
              Cost Gateway
            </div>

            <h1 className="control-title">
              Usage
            </h1>

            <p className="control-description">
              Every future model call will be
              checked against task, daily and
              monthly budgets before it is
              executed.
            </p>

          </header>

          <section className="control-card">

            <div className="control-card-header">

              <div className="control-card-title">
                Current usage
              </div>

            </div>

            <div className="control-card-body">

              <div className="limit-grid">

                <div className="limit-card">

                  <div className="limit-name">
                    Today
                  </div>

                  <div className="limit-value">
                    {money(usage.daily)}
                  </div>

                  <div className="limit-detail">
                    Hard limit{" "}
                    {money(limits.dailyHard)}
                  </div>

                </div>

                <div className="limit-card">

                  <div className="limit-name">
                    This month
                  </div>

                  <div className="limit-value">
                    {money(usage.monthly)}
                  </div>

                  <div className="limit-detail">
                    Hard limit{" "}
                    {money(limits.monthlyHard)}
                  </div>

                </div>

                <div className="limit-card">

                  <div className="limit-name">
                    Normal task
                  </div>

                  <div className="limit-value">
                    {money(limits.normalTask)}
                  </div>

                  <div className="limit-detail">
                    Default budget
                  </div>

                </div>

                <div className="limit-card">

                  <div className="limit-name">
                    Deep task
                  </div>

                  <div className="limit-value">
                    {money(limits.deepTask)}
                  </div>

                  <div className="limit-detail">
                    Default budget
                  </div>

                </div>

              </div>

            </div>

          </section>

          <section className="control-card">

            <div className="vector-table-wrap">

              <table className="vector-table">

                <thead>
                  <tr>
                    <th>Limit</th>
                    <th>Soft</th>
                    <th>Hard</th>
                  </tr>
                </thead>

                <tbody>

                  <tr>
                    <td>Daily</td>
                    <td>
                      {money(limits.dailySoft)}
                    </td>
                    <td>
                      {money(limits.dailyHard)}
                    </td>
                  </tr>

                  <tr>
                    <td>Monthly</td>
                    <td>
                      {money(limits.monthlySoft)}
                    </td>
                    <td>
                      {money(limits.monthlyHard)}
                    </td>
                  </tr>

                  <tr>
                    <td>Single task</td>
                    <td>
                      {money(limits.deepTask)}
                    </td>
                    <td>
                      {money(limits.maxTask)}
                    </td>
                  </tr>

                </tbody>

              </table>

            </div>

          </section>

        </div>

      </main>

    </div>
  );
}
