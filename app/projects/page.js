import Link
  from "next/link";

import {
  requireFeature
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

import ProjectsClient
  from "./projects-client";

export const dynamic = "force-dynamic";

const PRIVACY_LABELS = {
  public:
    "Public",

  personal:
    "Personal",

  internal:
    "Internal",

  confidential:
    "Confidential",

  local_only:
    "Local only"
};

export default async function ProjectsPage() {
  const session =
    await requireFeature("projects");

  await initializeFileDatabase();

  const result =
    await db.query(`
      SELECT
        p.id,
        p.name,
        p.description,
        p.privacy_level,
        p.created_at,
        p.updated_at,

        COUNT(
          pf.id
        )::int AS file_count,

        COALESCE(
          SUM(
            pf.size_bytes
          ),
          0
        )::bigint AS storage_bytes

      FROM projects p

      LEFT JOIN project_files pf
        ON
          pf.project_id =
          p.id

      WHERE (
        $1::boolean
        OR p.owner_user_id = $2
        OR EXISTS (
          SELECT 1 FROM project_members pm
          WHERE pm.project_id = p.id AND pm.user_id = $2
        )
      )

      GROUP BY
        p.id

      ORDER BY
        p.updated_at DESC
    `, [session.role === "owner", session.userId]);

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
              Projects
            </h1>

            <p>
              Organize chats, files,
              repositories and future agents
              around real work.
            </p>

          </div>

          <ProjectsClient />

        </header>

        {
          result.rows.length ===
          0
            ? (
              <section className="projects-empty">

                <div className="projects-empty-icon">
                  ◇
                </div>

                <h2>
                  Create your first project
                </h2>

                <p>
                  Projects keep files,
                  conversations and future
                  agent work together.
                </p>

              </section>
            )
            : (
              <section className="projects-grid">

                {
                  result.rows.map(
                    (
                      project
                    ) => (
                      <Link
                        href={
                          `/projects/${project.id}`
                        }
                        className="project-card"
                        key={
                          project.id
                        }
                      >

                        <div className="project-card-top">

                          <div className="project-symbol">
                            →
                          </div>

                          <span
                            className={
                              `project-privacy privacy-${project.privacy_level}`
                            }
                          >
                            {
                              PRIVACY_LABELS[
                                project
                                  .privacy_level
                              ] ||
                              project
                                .privacy_level
                            }
                          </span>

                        </div>

                        <h2>
                          {
                            project.name
                          }
                        </h2>

                        <p>
                          {
                            project.description ||
                            "No description yet."
                          }
                        </p>

                        <div className="project-meta">

                          <span>
                            {
                              project.file_count
                            }
                            {" "}
                            {
                              project.file_count ===
                              1
                                ? "file"
                                : "files"
                            }
                          </span>

                          <span>
                            {
                              humanBytes(
                                project.storage_bytes
                              )
                            }
                          </span>

                        </div>

                      </Link>
                    )
                  )
                }

              </section>
            )
        }

      </main>

    </div>
  );
}
