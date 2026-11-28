import { teamMessages, nonReplayable } from "../lib/teams/context.mjs";
import { readFileSync } from "node:fs";
import { SPECIALISTS, teamPolicy } from "../lib/teams/policy.mjs";
import { withTeamCalls, admitTeamCall } from "../lib/teams/call-scope.mjs";
/** Isolated CI only. No external requests, provider calls, messages or scans. */
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import pg from "pg";
const target = new URL(process.env.DATABASE_URL || "postgres://missing");
if (
  process.env.CI !== "true" ||
  !["localhost", "127.0.0.1"].includes(target.hostname) ||
  target.pathname !== "/vector_ci"
)
  throw Error("Requires isolated CI PostgreSQL");
const origin = process.env.VECTOR_AUTHZ_TEST_ORIGIN || "http://127.0.0.1:3187";
const db = new pg.Pool({ connectionString: target.href, max: 2 });
const prefix = "ops-fixture-" + crypto.randomUUID();
const key = process.env.VECTOR_SECRET;
function cookie(id) {
  const encoded = Buffer.from(
    JSON.stringify({
      userId: id,
      username: id,
      role: "member",
      expiresAt: Date.now() + 60000,
    }),
  ).toString("base64url");
  return (
    "vector_session=" +
    encoded +
    "." +
    crypto.createHmac("sha256", key).update(encoded).digest("base64url")
  );
}
async function request(path, { id, method = "GET", body, headers = {} } = {}) {
  const response = await fetch(origin + path, {
    method,
    headers: {
      ...(id ? { cookie: cookie(id) } : {}),
      "Content-Type": "application/json",
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
    redirect: "manual",
  });
  return { status: response.status, data: await response.json() };
}
const users = ["owner", "member", "readonly"].map((role) => ({
  id: prefix + "-" + role,
  role,
}));
const owner = users[0].id,
  member = users[1].id,
  readonly = users[2].id;
test("operations APIs enforce account scope, revisions, signature replay and exact action approvals", async (t) => {
  let connectionId;
  try {
    await request("/api/projects");
    for (const user of users)
      await db.query(
        `INSERT INTO vector_users(id,username,password_salt,password_hash,role,enabled,features) VALUES($1,$1,'unused','unused',$2,TRUE,'{"projects":true,"chat":true,"server":true}')`,
        [user.id, user.role],
      );
    await t.test("anonymous and read-only writes are rejected", async () => {
      assert.equal((await request("/api/brain")).status, 401);
      assert.equal(
        (
          await request("/api/brain", {
            id: readonly,
            method: "POST",
            body: {},
          })
        ).status,
        403,
      );
      assert.equal(
        (await request("/api/connections", { id: member })).status,
        403,
      );
      assert.equal((await request("/api/traffic", { id: member })).status, 403);
    });
    let memory;
    await t.test(
      "Brain CRUD is encrypted and isolated with compare-and-swap correction",
      async () => {
        const result = await request("/api/brain", {
          id: owner,
          method: "POST",
          body: {
            title: "Fixture preference",
            body: "Use metric units for fixture reports.",
            tags: ["fixture"],
            pinned: true,
          },
        });
        assert.equal(result.status, 200);
        memory = result.data.memory;
        assert.equal(
          (await request("/api/brain", { id: member })).data.memories.length,
          0,
        );
        const stored = (
          await db.query(
            "SELECT encrypted_body FROM brain_memories WHERE id=$1",
            [memory.id],
          )
        ).rows[0];
        assert.ok(!stored.encrypted_body.includes("metric units"));
        assert.equal(
          (
            await request("/api/brain", {
              id: member,
              method: "POST",
              body: { ...memory, body: "Unauthorized change" },
            })
          ).status,
          409,
        );
        const changed = await request("/api/brain", {
          id: owner,
          method: "POST",
          body: { ...memory, body: "Use Celsius in fixture reports." },
        });
        assert.equal(changed.data.memory.revision, 2);
        assert.equal(
          (
            await request("/api/brain", {
              id: owner,
              method: "DELETE",
              body: { id: memory.id, revision: 1 },
            })
          ).status,
          409,
        );
        assert.equal(
          (
            await request("/api/brain", {
              id: owner,
              method: "DELETE",
              body: { id: memory.id, revision: 2 },
            })
          ).status,
          200,
        );
        assert.equal(
          (await request("/api/brain", { id: owner })).data.memories.length,
          0,
        );
      },
    );
    await t.test(
      "expired memories free capacity without exposing unreadable expired records",
      async () => {
        const ids = Array.from({ length: 200 }, () => crypto.randomUUID());
        await db.query(
          "INSERT INTO brain_memories(id,owner_user_id,title,encrypted_body,source,expires_at) SELECT unnest($1::text[]),$2,'Expired fixture','unread expired ciphertext','Fixture',NOW()-INTERVAL '1 day'",
          [ids, owner],
        );
        const saved = await request("/api/brain", {
          id: owner,
          method: "POST",
          body: {
            title: "Fresh fixture",
            body: "Use source references.",
            tags: [],
            pinned: false,
          },
        });
        assert.equal(saved.status, 200);
        assert.equal(
          (
            await db.query(
              "SELECT COUNT(*)::int AS n FROM brain_memories WHERE owner_user_id=$1",
              [owner],
            )
          ).rows[0].n,
          1,
        );
        await request("/api/brain", {
          id: owner,
          method: "DELETE",
          body: { id: saved.data.memory.id, revision: 1 },
        });
      },
    );
    await t.test(
      "connection save stores credentials privately without contacting the service",
      async () => {
        const result = await request("/api/connections", {
          id: owner,
          method: "POST",
          body: {
            action: "create",
            kind: "api",
            name: "Fixture API",
            base: "https://93.184.216.34",
            secret: "fixture-not-a-real-token",
            readPath: "status",
          },
        });
        assert.equal(result.status, 200);
        connectionId = result.data.id;
        const listed = (await request("/api/connections", { id: owner })).data;
        assert.equal(
          listed.connections.find((row) => row.id === connectionId)
            .lastSyncedAt,
          null,
        );
        assert.ok(!JSON.stringify(listed).includes("fixture-not-a-real-token"));
        assert.ok(
          !(
            await db.query(
              "SELECT encrypted_credentials FROM connector_connections WHERE id=$1",
              [connectionId],
            )
          ).rows[0].encrypted_credentials.includes("fixture-not-a-real-token"),
        );
      },
    );
    await t.test(
      "connector actions bind exact content and cannot execute without approval",
      async () => {
        await db.query(
          "UPDATE connector_connections SET kind='github' WHERE id=$1",
          [connectionId],
        );
        const action = await request("/api/connections", {
          id: owner,
          method: "POST",
          body: {
            action: "request-action",
            id: connectionId,
            spec: {
              action: "create-issue",
              repository: "example/fixture",
              title: "Fixture only",
              body: "No real issue will be sent.",
            },
          },
        });
        assert.equal(action.status, 200);
        assert.equal(
          (
            await request("/api/connections", {
              id: owner,
              method: "POST",
              body: { action: "execute", id: action.data.id },
            })
          ).status,
          400,
        );
        const approvals = (await request("/api/approvals", { id: owner })).data
          .approvals;
        const row = approvals.find((row) => row.id === action.data.approvalId);
        assert.equal(row.scope.body.title, "Fixture only");
        assert.equal(
          (
            await request("/api/approvals/" + row.id + "/decision", {
              id: owner,
              method: "POST",
              body: { decision: "approved", scopeDigest: "wrong" },
            })
          ).status,
          409,
        );
        assert.equal(
          (
            await request("/api/approvals/" + row.id + "/decision", {
              id: owner,
              method: "POST",
              body: { decision: "approved", scopeDigest: row.scope_digest },
            })
          ).status,
          200,
        );
        await db.query("UPDATE approvals SET consumed_at=NOW() WHERE id=$1", [
          row.id,
        ]);
        assert.equal(
          (
            await request("/api/connections", {
              id: owner,
              method: "POST",
              body: { action: "execute", id: action.data.id },
            })
          ).status,
          400,
        );
      },
    );
    await t.test(
      "team forks share the real PostgreSQL call counter and retry cannot reset it",
      { timeout: 10000 },
      async () => {
        await request("/api/teams", { id: owner });
        let releaseSpecialists;
        const pairedSpecialists = new Promise((resolve) => {
          releaseSpecialists = resolve;
        });
        let calls = 0,
          active = 0,
          peak = 0;
        const runtime = {
          provider: "fixture",
          model: "fixture",
          requestingUserId: owner,
          freeOnly: true,
        };
        const dependencies = {
          teamMessages,
          nonReplayable,
          db,
          initializeDatabase: async () => {},
          SPECIALISTS,
          teamPolicy,
          withTeamCalls,
          resolveProviderForTask: async (options) => {
            assert.equal(options.billingPolicy, "free-only");
            return runtime;
          },
          requestSimpleProviderText: async (input) => {
            await admitTeamCall();
            calls++;
            active++;
            peak = Math.max(peak, active);
            if (!input.instructions.startsWith("Review")) {
              if (active === 2) releaseSpecialists();
              await pairedSpecialists;
            }
            active--;
            return {
              text: input.instructions.startsWith("Review")
                ? "PASS"
                : "Fixture contribution",
              inputTokens: 10,
              outputTokens: 5,
              cachedTokens: 0,
            };
          },
          runVectorAgent: async (options) => {
            assert.equal(options.executionClass, "artifact");
            assert.equal(options.toolDomains.artifact, true);
            assert.ok(options.roundLimit >= 2);
            await admitTeamCall();
            calls++;
            await admitTeamCall();
            calls++;
            return {
              text: "Fixture result",
              toolTrace: [],
              inputTokens: 20,
              outputTokens: 10,
              cachedTokens: 0,
            };
          },
        };
        const source = readFileSync(
          new URL("../lib/teams/runtime.js", import.meta.url),
          "utf8",
        )
          .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, "")
          .replace(/^export\s+/gm, "");
        const { runAgentTeam } = new Function(
          ...Object.keys(dependencies),
          source + ";return {runAgentTeam};",
        )(...Object.values(dependencies));
        const jobId = prefix + "-team",
          args = {
            jobId,
            executionClass: "artifact",
            toolDomains: { artifact: true },
            userId: owner,
            projectId: null,
            messages: [{ role: "user", content: "Fixture task" }],
            originalUserMessage: "Fixture task",
            providerRuntime: runtime,
          };
        const result = await runAgentTeam(args, {
          roles: ["research", "data"],
          maxCalls: 5,
        });
        assert.equal(result.text, "Fixture result");
        assert.equal(calls, 5);
        assert.equal(peak, 2);
        assert.equal(
          (
            await db.query(
              "SELECT used_calls FROM agent_team_limits WHERE job_id=$1",
              [jobId],
            )
          ).rows[0].used_calls,
          5,
        );
        await assert.rejects(
          runAgentTeam(args, { roles: ["research", "data"], maxCalls: 5 }),
          /shared provider-call limit/,
        );
        assert.equal(calls, 5);
        await db.query("DELETE FROM agent_team_steps WHERE job_id=$1", [jobId]);
        await db.query("DELETE FROM agent_team_limits WHERE job_id=$1", [
          jobId,
        ]);
      },
    );
    await t.test(
      "traffic ingest requires exact HMAC and refuses replay",
      async () => {
        const ingestKey = process.env.VECTOR_TRAFFIC_INGEST_TOKEN;
        if (!ingestKey)
          return t.skip("Signed ingest key is not configured in this fixture.");
        const body = {
            events: [
              {
                sourceIp: "192.0.2.5",
                service: "Fixture web",
                kind: "http-request",
                observedAt: new Date().toISOString(),
              },
            ],
          },
          stamp = String(Date.now()),
          nonce = crypto.randomUUID(),
          signature = crypto
            .createHmac("sha256", ingestKey)
            .update(stamp + "\n" + nonce + "\n" + JSON.stringify(body))
            .digest("hex"),
          headers = {
            "X-Vector-Timestamp": stamp,
            "X-Vector-Nonce": nonce,
            "X-Vector-Signature": signature,
          };
        assert.equal(
          (
            await request("/api/traffic", {
              method: "POST",
              body,
              headers: { ...headers, "X-Vector-Signature": "0".repeat(64) },
            })
          ).status,
          401,
        );
        assert.equal(
          (await request("/api/traffic", { method: "POST", body, headers }))
            .status,
          200,
        );
        assert.equal(
          (await request("/api/traffic", { method: "POST", body, headers }))
            .data.error,
          "TRAFFIC_REPLAY",
        );
        assert.ok(
          (await request("/api/traffic", { id: owner })).data.clients.some(
            (row) => row.service === "Fixture web",
          ),
        );
      },
    );
    await t.test(
      "parallel cold login schema initialization is serialized across module copies",
      async () => {
        const name = "fixture_login_" + crypto.randomBytes(6).toString("hex");
        const source = readFileSync(
          new URL("../lib/login-security.js", import.meta.url),
          "utf8",
        )
          .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, "")
          .replace(/^export\s+/gm, "")
          .replaceAll("vector_login_rate_limits", name);
        const create = () =>
          new Function("db", "crypto", source + ";return ensureTable;")(
            db,
            crypto,
          );
        try {
          const first = create(),
            second = create();
          await Promise.all([first(), first(), second()]);
          assert.equal(
            (await db.query("SELECT COUNT(*) FROM " + name)).rows[0].count,
            "0",
          );
        } finally {
          await db.query("DROP TABLE IF EXISTS " + name);
        }
      },
    );
    await t.test(
      "host telemetry is encrypted, scoped, bounded and rejects stale source state",
      async () => {
        assert.equal((await request("/api/server/resources")).status, 401);
        assert.equal((await request("/api/operations/activity")).status, 401);
        const sourceId = crypto.randomUUID(),
          now = Date.now();
        const sample = {
          source: {
            id: sourceId,
            name: "Synthetic sampler",
            observedAt: new Date(now).toISOString(),
            connectionSampleAt: new Date(now).toISOString(),
            readers: [
              { kind: "conntrack", status: "ok" },
              { kind: "metrics", status: "ok" },
            ],
            dropped: 0,
          },
          connections: [
            {
              connectionId: "a".repeat(64),
              sourceIp: "198.51.100.52",
              destinationIp: "203.0.113.1",
              sourcePort: 52000,
              destinationPort: 25565,
              transport: "tcp",
              service: "Fixture game",
              state: "ESTABLISHED",
              observedAt: new Date(now).toISOString(),
              country: "CH",
            },
          ],
          vitals: {
            observedAt: new Date(now).toISOString(),
            cpuPercent: 32,
            logicalCpus: 8,
            memory: { totalBytes: 1000, availableBytes: 600 },
            storage: [
              { name: "System", totalBytes: 10000, availableBytes: 9000 },
            ],
          },
        };
        async function signed(body) {
          const nonce = crypto.randomUUID(),
            timestamp = String(Date.now()),
            raw = JSON.stringify(body),
            signature = crypto
              .createHmac("sha256", process.env.VECTOR_TRAFFIC_INGEST_TOKEN)
              .update(timestamp + "\n" + nonce + "\n" + raw)
              .digest("hex");
          return request("/api/traffic", {
            method: "POST",
            body,
            headers: {
              "x-vector-nonce": nonce,
              "x-vector-timestamp": timestamp,
              "x-vector-signature": signature,
            },
          });
        }
        try {
          assert.equal((await signed(sample)).status, 200);
          const state = await db.query(
            "SELECT encrypted_state FROM traffic_sources WHERE id=$1",
            [sourceId],
          );
          assert.equal(
            state.rows[0].encrypted_state.includes("198.51.100.52"),
            false,
          );
          const host = await request("/api/server/resources", { id: owner });
          assert.equal(host.status, 200);
          assert.equal(host.data.cpuPercent, 32);
          assert.equal(host.data.memory.usedBytes, 400);
          const view = await request("/api/traffic?minutes=60", { id: owner });
          assert.equal(view.status, 200);
          assert.ok(
            view.data.activeConnections.some(
              (row) =>
                row.destinationPort === 25565 && row.collectorId === sourceId,
            ),
          );
          assert.equal(
            (
              await signed({
                ...sample,
                source: {
                  ...sample.source,
                  observedAt: new Date(now - 1000).toISOString(),
                },
              })
            ).data.error,
            "STALE_COLLECTOR_SAMPLE",
          );
          assert.equal(
            (await signed({ ...sample, events: {} })).data.error,
            "INVALID_TRAFFIC_EVENTS",
          );
          assert.equal(
            (await request("/api/traffic?minutes=999", { id: owner })).status,
            400,
          );
          await db.query(
            "UPDATE vector_users SET features=$2::jsonb WHERE id=$1",
            [readonly, { chat: false, projects: false }],
          );
          assert.equal(
            (await request("/api/server/resources", { id: readonly })).status,
            403,
          );
          assert.equal(
            (await request("/api/operations/activity", { id: readonly }))
              .status,
            403,
          );
          await request("/api/security/assets", { id: owner });
          const jobSchema = readFileSync(
            new URL("../lib/background-jobs.js", import.meta.url),
            "utf8",
          ).match(/CREATE TABLE IF NOT EXISTS agent_jobs[\s\S]*?\n    \)/)[0];
          await db.query(jobSchema);
          const jobIds = [prefix + "-visible-job", prefix + "-hidden-job"],
            recentJobIds = Array.from(
              { length: 13 },
              (_, index) => `${prefix}-recent-job-${index}`,
            ),
            oldActiveJobId = prefix + "-old-active-job",
            projectId = prefix + "-activity-project",
            projectConversationId = prefix + "-project-conversation",
            assetId = prefix + "-asset",
            scanId = prefix + "-scan";
          try {
            await db.query(
              "INSERT INTO conversations(id,owner_user_id,title) VALUES($1,$2,'Visible fixture task'),($3,$4,'Hidden fixture task')",
              [jobIds[0], owner, jobIds[1], member],
            );
            await db.query(
              "INSERT INTO agent_jobs(id,user_id,conversation_id,status,payload) VALUES($1,$2,$1,'completed','{}'),($3,$4,$3,'completed','{}')",
              [jobIds[0], owner, jobIds[1], member],
            );
            await db.query("INSERT INTO projects(id,name) VALUES($1,'Fixture project')", [
              projectId,
            ]);
            await db.query(
              "INSERT INTO conversations(id,owner_user_id,project_id,title) VALUES($1,$2,$3,'Project task fixture')",
              [projectConversationId, owner, projectId],
            );
            await db.query(
              "INSERT INTO agent_jobs(id,user_id,conversation_id,project_id,status,created_at,payload) VALUES($1,$2,$3,$4,'running',NOW()-INTERVAL '2 days','{}')",
              [oldActiveJobId, owner, projectConversationId, projectId],
            );
            await db.query(
              "INSERT INTO agent_jobs(id,user_id,status,payload) SELECT unnest($1::text[]),$2,'completed','{}'",
              [recentJobIds, owner],
            );
            await db.query(
              "INSERT INTO security_assets(id,owner_user_id,request_id,request_digest,name,kind,scope,scope_digest,active) VALUES($1,$2,$1,'fixture','Visible fixture asset','web','{}','fixture',FALSE)",
              [assetId, owner],
            );
            await db.query(
              "INSERT INTO security_scan_runs(id,asset_id,user_id,scope_digest,status) VALUES($1,$2,$3,'fixture','completed')",
              [scanId, assetId, owner],
            );
            const owned = (
              await request("/api/operations/activity", { id: owner })
            ).data;
            assert.ok(owned.jobs.some((row) => row.id === jobIds[0]));
            const oldActiveJob = owned.activeJobs.find(
              (row) => row.id === oldActiveJobId,
            );
            assert.equal(oldActiveJob?.status, "running");
            assert.equal(oldActiveJob?.projectId, projectId);
            assert.equal(
              owned.jobs.some((row) => row.id === jobIds[1]),
              false,
            );
            assert.ok(owned.scans.some((row) => row.id === scanId));
            const others = (
              await request("/api/operations/activity", { id: member })
            ).data;
            assert.equal(
              others.scans.some((row) => row.id === scanId),
              false,
            );
            assert.equal(
              others.jobs.some((row) => row.id === jobIds[0]),
              false,
            );
          } finally {
            await db.query("DELETE FROM security_scan_runs WHERE id=$1", [
              scanId,
            ]);
            await db.query("DELETE FROM security_assets WHERE id=$1", [
              assetId,
            ]);
            await db.query("DELETE FROM agent_jobs WHERE id=ANY($1)", [
              [...jobIds, ...recentJobIds, oldActiveJobId],
            ]);
            await db.query("DELETE FROM conversations WHERE id=ANY($1)", [
              [...jobIds, projectConversationId],
            ]);
            await db.query("DELETE FROM projects WHERE id=$1", [projectId]);
          }
          const activity = await request("/api/operations/activity", {
            id: member,
          });
          assert.equal(activity.status, 200);
          assert.ok(Array.isArray(activity.data.jobs));
        } finally {
          await db.query(
            "DELETE FROM host_resource_samples WHERE source_id=$1",
            [sourceId],
          );
          await db.query("DELETE FROM traffic_sources WHERE id=$1", [sourceId]);
        }
      },
    );
  } finally {
    await db
      .query("DELETE FROM connector_connections WHERE owner_user_id=ANY($1)", [
        users.map((row) => row.id),
      ])
      .catch(() => {});
    await db
      .query("DELETE FROM brain_memories WHERE owner_user_id=ANY($1)", [
        users.map((row) => row.id),
      ])
      .catch(() => {});
    await db
      .query("DELETE FROM approvals WHERE requested_by=ANY($1)", [
        users.map((row) => row.id),
      ])
      .catch(() => {});
    await db.query("DELETE FROM vector_users WHERE id=ANY($1)", [
      users.map((row) => row.id),
    ]);
    await db.end();
  }
});
