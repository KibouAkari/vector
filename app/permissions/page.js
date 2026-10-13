import {
  requireSession
} from "../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../lib/db";

import Sidebar
  from "../../components/sidebar";

export const dynamic = "force-dynamic";

export default async function PermissionsPage() {
  const session =
    await requireSession();

  await initializeDatabase();

  const result =
    await db.query(`
      SELECT
        permission,
        decision,
        description
      FROM permission_policies
      ORDER BY permission ASC
    `);

  return (
    <div className="vector-shell">

      <Sidebar session={session} />

      <main className="main">

        <div className="content-container">

          <header className="control-header">

            <div className="eyebrow">
              Safety Core
            </div>

            <h1 className="control-title">
              Permissions
            </h1>

            <p className="control-description">
              Every tool action passes through
              this policy layer. Agents cannot
              bypass it through prompts or
              instructions.
            </p>

          </header>

          <section className="control-card">

            <div className="vector-table-wrap">

              <table className="vector-table">

                <thead>

                  <tr>
                    <th>Permission</th>
                    <th>Policy</th>
                    <th>Description</th>
                  </tr>

                </thead>

                <tbody>

                  {
                    result.rows.map(
                      (policy) => (
                        <tr
                          key={
                            policy.permission
                          }
                        >

                          <td>
                            {
                              policy.permission
                            }
                          </td>

                          <td>

                            <span
                              className={
                                `policy ${policy.decision.toLowerCase()}`
                              }
                            >
                              {
                                policy.decision
                              }
                            </span>

                          </td>

                          <td>
                            {
                              policy.description
                            }
                          </td>

                        </tr>
                      )
                    )
                  }

                </tbody>

              </table>

            </div>

          </section>

        </div>

      </main>

    </div>
  );
}
