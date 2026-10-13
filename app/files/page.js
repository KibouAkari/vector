import Link
  from "next/link";

import {
  requireSession
} from "../../lib/auth";

import {
  db
} from "../../lib/db";

import {
  humanBytes,
  initializeFileDatabase
} from "../../lib/project-files";

import Sidebar
  from "../../components/sidebar";

export const dynamic = "force-dynamic";

export default async function FilesPage() {
  const session =
    await requireSession();

  await initializeFileDatabase();

  const result =
    await db.query(`
      SELECT
        pf.id,
        pf.original_name,
        pf.mime_type,
        pf.extension,
        pf.size_bytes,
        pf.sha256,
        pf.previewable,
        pf.created_at,

        p.id AS project_id,
        p.name AS project_name,
        p.privacy_level

      FROM project_files pf

      JOIN projects p
        ON
          p.id =
          pf.project_id

      ORDER BY
        pf.created_at DESC

      LIMIT 500
    `);

  const storage =
    result.rows.reduce(
      (
        total,
        file
      ) =>
        total +
        Number(
          file.size_bytes
        ),
      0
    );

  return (
    <div className="vector-shell">

      <Sidebar
        session={
          session
        }
      />

      <main className="main workspace-main">

        <header className="workspace-header">

          <div>

            <div className="eyebrow">
              Workspace
            </div>

            <h1>
              Files
            </h1>

            <p>
              Encrypted local files across
              all Vector projects.
            </p>

          </div>

          <div className="files-summary">

            <strong>
              {
                result.rows.length
              }
            </strong>

            <span>
              files
            </span>

            <strong>
              {
                humanBytes(
                  storage
                )
              }
            </strong>

            <span>
              stored
            </span>

          </div>

        </header>

        <section className="global-files-card">

          {
            result.rows.length ===
            0
              ? (
                <div className="workspace-files-empty">
                  No files yet.
                </div>
              )
              : (
                <div className="global-file-table">

                  {
                    result.rows.map(
                      (
                        file
                      ) => (
                        <Link
                          href={
                            `/projects/${file.project_id}`
                          }
                          key={
                            file.id
                          }
                        >

                          <span className="file-type">
                            {
                              file.extension
                                ? file.extension
                                    .slice(
                                      0,
                                      4
                                    )
                                    .toUpperCase()
                                : "FILE"
                            }
                          </span>

                          <span className="global-file-name">

                            <strong>
                              {
                                file.original_name
                              }
                            </strong>

                            <small>
                              {
                                file.project_name
                              }
                            </small>

                          </span>

                          <span>
                            {
                              humanBytes(
                                file.size_bytes
                              )
                            }
                          </span>

                          <span>
                            {
                              file.sha256
                                .slice(
                                  0,
                                  10
                                )
                            }
                          </span>

                        </Link>
                      )
                    )
                  }

                </div>
              )
          }

        </section>

      </main>

    </div>
  );
}
