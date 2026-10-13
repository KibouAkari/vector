import {
  requireSession
} from "../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../lib/db";

import Sidebar
  from "../../components/sidebar";

import ApprovalActions
  from "./approval-actions";

export const dynamic = "force-dynamic";

export default async function ApprovalsPage() {
  const session =
    await requireSession();

  await initializeDatabase();

  const result =
    await db.query(`
      SELECT
        id,
        permission,
        action,
        description,
        status,
        requested_at
      FROM approvals
      ORDER BY requested_at DESC
      LIMIT 100
    `);

  return (
    <div className="vector-shell">

      <Sidebar session={session} />

      <main className="main">

        <div className="content-container">

          <header className="control-header">

            <div className="eyebrow">
              Control
            </div>

            <h1 className="control-title">
              Approvals
            </h1>

            <p className="control-description">
              Host modifications, outbound
              actions and sensitive operations
              can pause here until you approve
              them.
            </p>

          </header>

          <section className="control-card">

            {
              result.rows.length === 0
                ? (
                  <div className="empty-control">
                    No approval requests.
                  </div>
                )
                : (
                  <div className="vector-table-wrap">

                    <table className="vector-table">

                      <thead>
                        <tr>
                          <th>Permission</th>
                          <th>Action</th>
                          <th>Status</th>
                          <th>Requested</th>
                          <th>Decision</th>
                        </tr>
                      </thead>

                      <tbody>

                        {
                          result.rows.map(
                            (approval) => (
                              <tr key={approval.id}>

                                <td>
                                  {
                                    approval.permission
                                  }
                                </td>

                                <td>
                                  <strong>
                                    {
                                      approval.action
                                    }
                                  </strong>

                                  {
                                    approval.description && (
                                      <div className="panel-subtitle">
                                        {
                                          approval.description
                                        }
                                      </div>
                                    )
                                  }
                                </td>

                                <td>
                                  {
                                    approval.status
                                  }
                                </td>

                                <td>
                                  {
                                    new Date(
                                      approval.requested_at
                                    ).toLocaleString(
                                      "en-GB"
                                    )
                                  }
                                </td>

                                <td>

                                  {
                                    approval.status ===
                                    "pending"
                                      ? (
                                        <ApprovalActions
                                          id={approval.id}
                                        />
                                      )
                                      : approval.status
                                  }

                                </td>

                              </tr>
                            )
                          )
                        }

                      </tbody>

                    </table>

                  </div>
                )
            }

          </section>

        </div>

      </main>

    </div>
  );
}
