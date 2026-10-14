import {
  requireSession
} from "../lib/auth";


import {
  db
} from "../lib/db";


import {
  initializeModelConfigs
} from "../lib/model-config";


import Sidebar
  from "../components/sidebar";


import VectorIntro
  from "../components/vector-intro";


import DashboardClient
  from "../components/dashboard-client";


export const dynamic =
  "force-dynamic";


async function query(
  sql,
  params = []
) {
  try {
    return (
      await db.query(
        sql,
        params
      )
    ).rows;
  } catch {
    return [];
  }
}


export default async function Home() {
  const session =
    await requireSession();

  // Scope all dashboard reads to the authenticated account.
  // The platform owner retains the global operational overview.
  const scopedQuery = (sql, includeProjectPermission = false) =>
    query(sql, includeProjectPermission
      ? [
          session.role === "owner",
          session.userId,
          session.role === "owner" || session.features?.projects === true
        ]
      : [session.role === "owner", session.userId]);


  await initializeModelConfigs();


  const [
    totals,
    modelUsage,
    timeline,
    projects
  ] =
    await Promise.all([

      scopedQuery(`
        SELECT
          COUNT(*)::int
            AS requests,

          COALESCE(
            SUM(input_tokens),
            0
          )::bigint
            AS input_tokens,

          COALESCE(
            SUM(output_tokens),
            0
          )::bigint
            AS output_tokens,

          COALESCE(
            SUM(cached_tokens),
            0
          )::bigint
            AS cached_tokens,

          COALESCE(
            SUM(input_tokens),
            0
          )::bigint
          +
          COALESCE(
            SUM(output_tokens),
            0
          )::bigint
            AS total_tokens,

          COALESCE(
            SUM(cost_chf),
            0
          )::numeric
            AS spend_chf

        FROM usage_events

        WHERE
          created_at >
          NOW() - INTERVAL '30 days'
          AND ($1::boolean OR user_id = $2)
      `),


      scopedQuery(`
        SELECT
          COALESCE(
            provider,
            'unknown'
          )
            AS provider,

          COALESCE(
            model,
            'unknown'
          )
            AS model,

          COUNT(*)::int
            AS requests,

          COALESCE(
            SUM(input_tokens),
            0
          )::bigint
            AS input_tokens,

          COALESCE(
            SUM(output_tokens),
            0
          )::bigint
            AS output_tokens,

          COALESCE(
            SUM(cached_tokens),
            0
          )::bigint
            AS cached_tokens,

          COALESCE(
            SUM(input_tokens),
            0
          )::bigint
          +
          COALESCE(
            SUM(output_tokens),
            0
          )::bigint
            AS total_tokens,

          COALESCE(
            SUM(cost_chf),
            0
          )::numeric
            AS spend_chf

        FROM usage_events

        WHERE
          created_at >
          NOW() - INTERVAL '30 days'
          AND ($1::boolean OR user_id = $2)

        GROUP BY
          provider,
          model

        ORDER BY
          spend_chf DESC,
          requests DESC
      `),


      scopedQuery(`
        WITH days AS (
          SELECT
            generate_series(
              CURRENT_DATE
                - INTERVAL '29 days',

              CURRENT_DATE,

              INTERVAL '1 day'
            )::date
              AS day
        )

        SELECT
          days.day,

          COUNT(
            usage.id
          )::int
            AS requests,

          COALESCE(
            SUM(
              usage.input_tokens
            ),
            0
          )::bigint
            AS input_tokens,

          COALESCE(
            SUM(
              usage.output_tokens
            ),
            0
          )::bigint
            AS output_tokens,

          COALESCE(
            SUM(
              usage.input_tokens
            ),
            0
          )::bigint
          +
          COALESCE(
            SUM(
              usage.output_tokens
            ),
            0
          )::bigint
            AS total_tokens,

          COALESCE(
            SUM(
              usage.cost_chf
            ),
            0
          )::numeric
            AS spend_chf

        FROM days

        LEFT JOIN usage_events
          AS usage

          ON
            usage.created_at >=
              days.day

            AND
            usage.created_at <
              days.day
              + INTERVAL '1 day'
            AND ($1::boolean OR usage.user_id = $2)

        GROUP BY
          days.day

        ORDER BY
          days.day
      `),


      scopedQuery(`
        SELECT
          id,
          name,
          description,
          updated_at

        FROM projects p

        WHERE (
          $1::boolean
          OR (
            $3::boolean AND (
              p.owner_user_id = $2
              OR EXISTS (
                SELECT 1 FROM project_members pm
                WHERE pm.project_id = p.id AND pm.user_id = $2
              )
            )
          )
        )

        ORDER BY
          updated_at DESC

        LIMIT 5
      `, true)

    ]);


  const total =
    totals[0] ||
    {};


  const displayName =
    session.displayName ||
    session.username;


  return (
    <div className="vector-shell vx85-dashboard-shell">

      <VectorIntro
        displayName={
          displayName
        }
      />


      <Sidebar
        session={
          session
        }
      />


      <main className="main v5-main vx85-dashboard-main">

        <DashboardClient
          displayName={
            displayName
          }
          totals={{
            requests:
              Number(
                total.requests ||
                0
              ),

            inputTokens:
              Number(
                total.input_tokens ||
                0
              ),

            outputTokens:
              Number(
                total.output_tokens ||
                0
              ),

            cachedTokens:
              Number(
                total.cached_tokens ||
                0
              ),

            totalTokens:
              Number(
                total.total_tokens ||
                0
              ),

            spend:
              Number(
                total.spend_chf ||
                0
              )
          }}
          models={
            modelUsage.map(
              row => {
                const requests =
                  Number(
                    row.requests ||
                    0
                  );


                const totalTokens =
                  Number(
                    row.total_tokens ||
                    0
                  );


                const spend =
                  Number(
                    row.spend_chf ||
                    0
                  );


                return {
                  provider:
                    row.provider,

                  model:
                    row.model,

                  requests,

                  inputTokens:
                    Number(
                      row.input_tokens ||
                      0
                    ),

                  outputTokens:
                    Number(
                      row.output_tokens ||
                      0
                    ),

                  cachedTokens:
                    Number(
                      row.cached_tokens ||
                      0
                    ),

                  totalTokens,

                  spend,

                  avgCost:
                    requests > 0
                      ? spend /
                        requests
                      : 0,

                  effectiveCost:
                    totalTokens > 0
                      ? (
                          spend *
                          1000000
                        ) /
                        totalTokens
                      : 0
                };
              }
            )
          }
          timeline={
            timeline.map(
              row => ({
                day:
                  String(
                    row.day
                  ),

                label:
                  new Date(
                    row.day
                  )
                    .toLocaleDateString(
                      "en",
                      {
                        month:
                          "short",

                        day:
                          "numeric"
                      }
                    ),

                requests:
                  Number(
                    row.requests ||
                    0
                  ),

                inputTokens:
                  Number(
                    row.input_tokens ||
                    0
                  ),

                outputTokens:
                  Number(
                    row.output_tokens ||
                    0
                  ),

                totalTokens:
                  Number(
                    row.total_tokens ||
                    0
                  ),

                spend:
                  Number(
                    row.spend_chf ||
                    0
                  )
              })
            )
          }
          projects={
            projects.map(
              project => ({
                id:
                  project.id,

                name:
                  project.name,

                description:
                  project.description,

                updatedAt:
                  project.updated_at
                    ? new Date(
                        project.updated_at
                      ).toISOString()
                    : null
              })
            )
          }
        />

      </main>

    </div>
  );
}
