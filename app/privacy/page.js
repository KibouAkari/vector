import {
  requireSession
} from "../../lib/auth";

import Sidebar
  from "../../components/sidebar";

import PrivacyTest
  from "./privacy-test";

export const dynamic = "force-dynamic";

export default async function PrivacyPage() {
  const session =
    await requireSession();

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
              Privacy Gateway
            </h1>

            <p className="control-description">
              Vector inspects sensitive
              information locally before
              external AI providers are ever
              contacted.
            </p>

          </header>

          <section className="control-card">

            <div className="control-card-header">

              <div className="control-card-title">
                Local privacy analyser
              </div>

              <div className="control-card-description">
                Nothing entered here leaves
                your Vector server.
              </div>

            </div>

            <div className="control-card-body">

              <PrivacyTest />

            </div>

          </section>

          <section className="control-card">

            <div className="control-card-header">

              <div className="control-card-title">
                Current policy
              </div>

            </div>

            <div className="vector-table-wrap">

              <table className="vector-table">

                <thead>
                  <tr>
                    <th>Level</th>
                    <th>External AI</th>
                    <th>Behaviour</th>
                  </tr>
                </thead>

                <tbody>

                  <tr>
                    <td className="privacy-public">
                      Public
                    </td>

                    <td>Allowed</td>

                    <td>
                      Normal provider routing
                    </td>
                  </tr>

                  <tr>
                    <td className="privacy-internal">
                      Internal
                    </td>

                    <td>Allowed</td>

                    <td>
                      Approved providers only
                    </td>
                  </tr>

                  <tr>
                    <td className="privacy-confidential">
                      Confidential
                    </td>

                    <td>Blocked</td>

                    <td>
                      Local processing or
                      explicit future approval
                    </td>
                  </tr>

                  <tr>
                    <td className="privacy-restricted">
                      Restricted
                    </td>

                    <td>Blocked</td>

                    <td>
                      Never automatically sent
                      externally
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
