/**
 * Authenticated API integration tests against an isolated PostgreSQL service.
 * This test must NEVER be pointed at production resources.
 * Uses real login sessions, Next.js route handlers, and encrypted test files.
 */
import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import pg from "pg";

const database = new URL(process.env.DATABASE_URL || "postgres://missing");
const storage = process.env.FILE_STORAGE_PATH || "";
const origin = process.env.VECTOR_AUTHZ_TEST_ORIGIN || "http://127.0.0.1:3187";

if (
  process.env.CI !== "true" ||
  !["127.0.0.1", "localhost"].includes(database.hostname) ||
  database.pathname !== "/vector_ci" ||
  !storage.startsWith("/tmp/vector-auth-ci-") ||
  origin !== "http://127.0.0.1:3187"
) {
  throw new Error("Refusing to run authorization integration tests outside isolated CI.");
}

const { Pool } = pg;
const db = new Pool({ connectionString: process.env.DATABASE_URL, max: 3 });
const users = {
  admin: { role: "owner", features: {} },
  creator: { role: "member", features: { projects: true } },
  viewer: { role: "member", features: { projects: true } },
  editor: { role: "member", features: { projects: true } },
  outsider: { role: "member", features: { projects: true } },
  disabled: { role: "member", features: { projects: false, server: false } },
};
const cookies = {};
const password = "ci-integration-password-only";

async function request(route, { as, method = "GET", body } = {}) {
  const headers = {};
  if (as) headers.cookie = cookies[as];
  if (body !== undefined) headers["content-type"] = "application/json";
  return fetch(origin + route, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    redirect: "manual",
  });
}

async function expectStatus(route, options, status) {
  const response = await request(route, options);
  assert.equal(
    response.status, status,
    `${options?.as || "anonymous"} ${options?.method || "GET"} ${route}: ${response.status} ${(await response.text()).slice(0, 260)}`
  );
  return response;
}

async function login(as) {
  const response = await expectStatus("/api/auth/login", {
    method: "POST",
    body: { username: as, password },
  }, 200);
  const setCookie = response.headers.get("set-cookie");
  assert.ok(setCookie?.startsWith("vector_session="), "real login must set a session cookie");
  cookies[as] = setCookie.split(";")[0];
}

async function seedUser(name, config) {
  const id = crypto.randomUUID();
  const salt = crypto.randomBytes(24).toString("hex");
  const hash = crypto.scryptSync(password, salt, 64).toString("hex");
  await db.query(`
    INSERT INTO vector_users
      (id, username, password_salt, password_hash, role, enabled, features)
    VALUES ($1,$2,$3,$4,$5,TRUE,$6::jsonb)
  `, [id, name, salt, hash, config.role, JSON.stringify(config.features)]);
  config.id = id;
}

async function seedEncryptedFile(projectId, name, mimeType, plain, previewable) {
  const id = crypto.randomUUID();
  const storedName = `${id}.vfile`;
  const key = Buffer.from(process.env.FILE_ENCRYPTION_KEY, "hex");
  assert.equal(key.length, 32);
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
  const ciphertext = Buffer.concat([cipher.update(plain), cipher.final()]);
  const encrypted = Buffer.concat([
    Buffer.from("VEC1"), iv, cipher.getAuthTag(), ciphertext,
  ]);
  const directory = path.join(storage, projectId);
  await fs.mkdir(directory, { recursive: true, mode: 0o700 });
  await fs.writeFile(path.join(directory, storedName), encrypted, { mode: 0o600 });
  await db.query(`
    INSERT INTO project_files
      (id, project_id, original_name, stored_name, mime_type,
       extension, size_bytes, sha256, previewable, encryption_version)
    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,1)
  `, [id, projectId, name, storedName, mimeType,
    name.split(".").pop(), plain.length,
    crypto.createHash("sha256").update(plain).digest("hex"), previewable]);
  return id;
}

test("real authenticated API permissions and project isolation", async t => {
  try {
    // The first anonymous request creates the production schema.
    await expectStatus("/api/projects", {}, 401);

    for (const [name, config] of Object.entries(users)) {
      await seedUser(name, config);
      await login(name);
    }

    const created = await expectStatus("/api/projects", {
      as: "creator", method: "POST",
      body: { name: "creator-private-project", privacyLevel: "personal" },
    }, 200);
    const projectId = (await created.json()).project.id;

    const other = await expectStatus("/api/projects", {
      as: "outsider", method: "POST",
      body: { name: "outsider-project" },
    }, 200);
    const otherId = (await other.json()).project.id;

    const ownership = await db.query("SELECT owner_user_id FROM projects WHERE id=$1", [projectId]);
    assert.equal(ownership.rows[0].owner_user_id, users.creator.id);

    await db.query(`
      INSERT INTO project_members (project_id, user_id, access_role)
      VALUES ($1,$2,'viewer'), ($1,$3,'editor'), ($1,$4,'viewer')
    `, [projectId, users.viewer.id, users.editor.id, users.disabled.id]);

    // Existing migration-compatible columns used by task and conversation APIs.
    await db.query("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()");
    await db.query("ALTER TABLE conversations ADD COLUMN IF NOT EXISTS user_id TEXT");

    const taskId = crypto.randomUUID();
    await db.query("INSERT INTO tasks (id, project_id, title) VALUES ($1,$2,$3)",
      [taskId, projectId, "private task"]);

    const conversationId = crypto.randomUUID();
    await db.query(
      "INSERT INTO conversations (id,project_id,title,user_id) VALUES ($1,$2,$3,$4)",
      [conversationId, projectId, "private conversation", users.creator.id]
    );

    const textFile = await seedEncryptedFile(
      projectId, "internal.txt", "text/plain", Buffer.from("PRIVATE_PROJECT_CONTENT"), true
    );
    const imageFile = await seedEncryptedFile(
      projectId, "image.png", "image/png", Buffer.from("TEST_IMAGE_BYTES"), false
    );

    await t.test("project listings include only owned/shared projects", async () => {
      for (const [as, allowed, forbidden] of [
        ["creator", projectId, otherId],
        ["viewer", projectId, otherId],
        ["editor", projectId, otherId],
        ["outsider", otherId, projectId],
      ]) {
        const list = await expectStatus("/api/projects", { as }, 200);
        const ids = (await list.json()).projects.map(p => p.id);
        assert.ok(ids.includes(allowed), `${as}: owned/shared project is visible`);
        assert.ok(!ids.includes(forbidden), `${as}: unrelated project must be hidden`);
      }
      const root = await expectStatus("/api/projects", { as: "admin" }, 200);
      assert.equal((await root.json()).projects.length, 2);
      await expectStatus("/api/projects", { as: "disabled" }, 403);
      await expectStatus("/api/projects", {
        as: "disabled", method: "POST", body: { name: "forbidden" },
      }, 403);
      await expectStatus(`/projects/${projectId}`, { as: "outsider" }, 404);
    });

    await t.test("project mutations require ownership, not viewer/editor", async () => {
      for (const as of ["viewer", "editor", "outsider", "disabled"]) {
        await expectStatus(`/api/projects/${projectId}`, {
          as, method: "PATCH", body: { name: "malicious rename" },
        }, 404);
        await expectStatus(`/api/projects/${projectId}`, {
          as, method: "DELETE",
        }, 404);
      }
      await expectStatus(`/api/projects/${projectId}`, {
        as: "creator", method: "PATCH", body: { name: "approved rename" },
      }, 200);
      await expectStatus(`/api/projects/${projectId}`, {
        as: "admin", method: "PATCH", body: { description: "owner review" },
      }, 200);
      const result = await db.query("SELECT name FROM projects WHERE id=$1", [projectId]);
      assert.equal(result.rows[0].name, "approved rename");
    });

    await t.test("direct file IDs cannot bypass membership or write permissions", async () => {
      for (const route of [
        `/api/projects/${projectId}/files`,
        `/api/files/${textFile}/content`,
        `/api/files/${textFile}/preview`,
        `/api/files/${imageFile}/raw`,
      ]) {
        await expectStatus(route, { as: "viewer" }, 200);
        await expectStatus(route, { as: "outsider" }, 404);
        await expectStatus(route, { as: "disabled" }, 404);
      }
      const text = await expectStatus(`/api/files/${textFile}/content`, { as: "viewer" }, 200);
      assert.equal((await text.json()).content, "PRIVATE_PROJECT_CONTENT");

      for (const as of ["viewer", "outsider", "disabled"]) {
        await expectStatus(`/api/files/${textFile}/content`, {
          as, method: "PATCH", body: { content: "UNAUTHORIZED" },
        }, 404);
        await expectStatus(`/api/files/${imageFile}`, {
          as, method: "DELETE",
        }, 404);
        await expectStatus(`/api/projects/${projectId}/files/create`, {
          as, method: "POST", body: { name: "unauthorized.txt", content: "bad" },
        }, 404);
      }
      const unchanged = await expectStatus(`/api/files/${textFile}/content`, { as: "creator" }, 200);
      assert.equal((await unchanged.json()).content, "PRIVATE_PROJECT_CONTENT");
    });

    await t.test("tasks are readable by viewer, writable by editor", async () => {
      await expectStatus(`/api/projects/${projectId}/tasks`, { as: "viewer" }, 200);
      await expectStatus(`/api/projects/${projectId}/tasks`, { as: "outsider" }, 404);
      for (const as of ["viewer", "outsider", "disabled"]) {
        await expectStatus(`/api/tasks/${taskId}`, {
          as, method: "PATCH", body: { status: "cancelled" },
        }, 404);
        await expectStatus(`/api/projects/${projectId}/tasks`, {
          as, method: "POST", body: { title: "unauthorized task" },
        }, 404);
      }
      await expectStatus(`/api/tasks/${taskId}`, {
        as: "editor", method: "PATCH", body: { status: "completed" },
      }, 200);
      await expectStatus(`/api/projects/${projectId}/tasks`, {
        as: "editor", method: "POST", body: { title: "authorized editor task" },
      }, 200);
      const actual = await db.query("SELECT status FROM tasks WHERE id=$1", [taskId]);
      assert.equal(actual.rows[0].status, "completed");
    });

    await t.test("conversation owner privacy is stricter than project sharing", async () => {
      const list = await expectStatus(`/api/projects/${projectId}/conversations`, { as: "creator" }, 200);
      assert.ok((await list.json()).conversations.some(c => c.id === conversationId));
      const viewerList = await expectStatus(`/api/projects/${projectId}/conversations`, { as: "viewer" }, 200);
      assert.equal((await viewerList.json()).conversations.length, 0);
      await expectStatus(`/api/projects/${projectId}/conversations`, { as: "outsider" }, 404);
      await expectStatus(`/api/projects/${projectId}/conversations/${conversationId}`, { as: "creator" }, 200);
      await expectStatus(`/api/projects/${projectId}/conversations/${conversationId}`, { as: "viewer" }, 404);
      await expectStatus(`/api/projects/${projectId}/conversations/${conversationId}`, { as: "outsider" }, 404);
    });

    await t.test("server snapshot requires server feature, not merely login", async () => {
      await expectStatus("/api/server/snapshot", {}, 401);
      await expectStatus("/api/server/snapshot", { as: "viewer" }, 403);
      await expectStatus("/api/server/snapshot", { as: "disabled" }, 403);
    });

    await t.test("removing membership revokes direct access on next request", async () => {
      await db.query("DELETE FROM project_members WHERE project_id=$1 AND user_id=$2",
        [projectId, users.viewer.id]);
      await expectStatus(`/api/projects/${projectId}/files`, { as: "viewer" }, 404);
      await expectStatus(`/api/files/${textFile}/content`, { as: "viewer" }, 404);
      await expectStatus(`/api/tasks/${taskId}`, {
        as: "viewer", method: "PATCH", body: { status: "cancelled" },
      }, 404);
    });

    await t.test("a user can delete only their own project", async () => {
      await expectStatus(`/api/projects/${otherId}`, { as: "creator", method: "DELETE" }, 404);
      await expectStatus(`/api/projects/${otherId}`, { as: "outsider", method: "DELETE" }, 200);
      const rows = await db.query("SELECT 1 FROM projects WHERE id=$1", [otherId]);
      assert.equal(rows.rowCount, 0);
    });
  } finally {
    await db.end();
  }
});
