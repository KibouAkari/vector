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
      async () => {
        await request("/api/teams", { id: owner });
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
            await new Promise((resolve) => setTimeout(resolve, 5));
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
          runVectorAgent: async () => {
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
