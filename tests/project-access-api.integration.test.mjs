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
  operator: {role:"admin",features:{chat:true,projects:true,models:true}},
  reader: {role:"readonly",features:{chat:true,projects:true,models:true}},
  creator: { role: "member", features: { projects: true } },
  viewer: { role: "member", features: { projects: true } },
  editor: { role: "member", features: { projects: true } },
  outsider: { role: "member", features: { projects: true } },
  disabled: { role: "member", features: { chat: false, projects: false, server: false, models: false, activity: false } },
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
  if (response.status !== status) {
    const details = (await response.text()).slice(0, 260);
    assert.fail(
      `${options?.as || "anonymous"} ${options?.method || "GET"} ${route}: ${response.status}, expected ${status}: ${details}`
    );
  }
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

    await t.test("original file downloads enforce project access and preserve bytes", async () => {
      const download = `/api/files/${textFile}/download`;
      await expectStatus(download, {}, 401);
      for (const as of ["outsider", "disabled"]) {
        await expectStatus(download, {as}, 404);
      }
      for (const as of ["creator", "viewer", "editor", "admin"]) {
        const response = await expectStatus(download, {as}, 200);
        assert.equal(await response.text(), "PRIVATE_PROJECT_CONTENT");
        assert.equal(response.headers.get("content-type"), "application/octet-stream");
        assert.match(response.headers.get("content-disposition"), /^attachment;/);
        assert.equal(response.headers.get("cache-control"), "private, no-store");
      }
      const binary = await expectStatus(`/api/files/${imageFile}/download`, {as: "viewer"}, 200);
      assert.deepEqual(Buffer.from(await binary.arrayBuffer()), Buffer.from("TEST_IMAGE_BYTES"));
    });

    await t.test("failed sharing updates preserve existing project access", async () => {
      const route = `/api/users/${users.viewer.id}/projects`;
      const before = await db.query(
        "SELECT project_id, access_role FROM project_members WHERE user_id=$1 ORDER BY project_id",
        [users.viewer.id]
      );
      assert.ok(before.rows.some(row => row.project_id === projectId));

      // A mixed valid/invalid selection must not delete old memberships.
      await expectStatus(route, {
        as: "admin",
        method: "PUT",
        body: {
          projectIds: [projectId, "ci-missing-project-" + crypto.randomUUID()],
          accessRole: "viewer"
        }
      }, 400);

      const after = await db.query(
        "SELECT project_id, access_role FROM project_members WHERE user_id=$1 ORDER BY project_id",
        [users.viewer.id]
      );
      assert.deepEqual(after.rows, before.rows);

      // Only the owner may change another account's project grants.
      await expectStatus(route, {
        as: "outsider",
        method: "PUT",
        body: { projectIds: [], accessRole: "viewer" }
      }, 403);
    });

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

    await t.test("dashboard data and disabled features stay tenant-scoped", async () => {
      const ownerOnlyModel = "ci-owner-only-model-" + crypto.randomUUID();
      const creatorOnlyModel = "ci-creator-only-model-" + crypto.randomUUID();
      const disabledOnlyModel = "ci-disabled-only-model-" + crypto.randomUUID();

      for (const [as, model] of [
        ["admin", ownerOnlyModel],
        ["creator", creatorOnlyModel],
        ["disabled", disabledOnlyModel],
      ]) {
        await db.query(
          `INSERT INTO usage_events (id, provider, model, user_id, input_tokens, output_tokens, cost_chf)
           VALUES ($1, 'test', $2, $3, 3, 4, 0.001)`,
          [crypto.randomUUID(), model, users[as].id]
        );
      }

      const disabledPage = await (await expectStatus("/", { as: "disabled" }, 200)).text();
      assert.ok(disabledPage.includes(disabledOnlyModel), "member sees own spend");
      for (const secret of [ownerOnlyModel, creatorOnlyModel, "creator-private-project", "outsider-project"]) {
        assert.ok(!disabledPage.includes(secret), `chat-only account leaked: ${secret}`);
      }

      const creatorPage = await (await expectStatus("/", { as: "creator" }, 200)).text();
      assert.ok(creatorPage.includes(creatorOnlyModel), "creator sees own spend");
      assert.ok(creatorPage.includes("creator-private-project"), "creator sees own project");
      assert.ok(!creatorPage.includes(ownerOnlyModel), "other-user spend hidden");
      assert.ok(!creatorPage.includes("outsider-project"), "other-user project hidden");

      const ownerPage = await (await expectStatus("/", { as: "admin" }, 200)).text();
      assert.ok(ownerPage.includes(ownerOnlyModel), "owner sees operational usage");
      assert.ok(ownerPage.includes("creator-private-project"), "owner sees operational projects");

      for (const route of ["/models", "/audit", "/api/models"]) {
        const response = await request(route, { as: "disabled" });
        assert.ok([302,303,307,308,403].includes(response.status),
          `feature-disabled account unexpectedly accessed ${route}: ${response.status}`);
      }
      // Own cost visibility is available independently of workspace feature flags.
      const ownUsagePage=await (await expectStatus('/usage',{as:'disabled'},200)).text();
      assert.ok(!ownUsagePage.includes(ownerOnlyModel));assert.ok(!ownUsagePage.includes(creatorOnlyModel));
      const ownBudget=(await (await expectStatus('/api/budgets',{as:'disabled'},200)).json());
      assert.equal(ownBudget.canManage,false);assert.ok(ownBudget.reservations.every(row=>row.user_id===users.disabled.id));
      await expectStatus('/api/budgets',{as:'disabled',method:'POST',body:{}},403);
      await expectStatus("/api/models", { as: "disabled" }, 403);
      await expectStatus("/api/models", { as: "creator" }, 403);
      await expectStatus("/api/conversations", { as: "disabled" }, 403);
      await expectStatus("/api/projects", { as: "disabled" }, 403);
      await expectStatus(`/projects/${projectId}`, { as: "disabled" }, 404);
      await expectStatus("/api/chat", { as: "disabled", method: "POST", body: {message: "blocked"} }, 403);
      await expectStatus("/api/chat/attachments", { as: "disabled" }, 403);
      await expectStatus("/api/chat/attachments", { as: "disabled", method: "POST" }, 403);
      await expectStatus("/api/chat/attachments/not-an-attachment", { as: "disabled", method: "DELETE" }, 403);
      await expectStatus("/api/chat/attachments/not-an-attachment/raw", { as: "disabled" }, 403);
      const disabledChatPage = await request("/chat", { as: "disabled" });
      assert.ok([302,303,307,308].includes(disabledChatPage.status), "chat-disabled page must redirect");
      const permittedChatPage = await request("/chat", { as: "creator" });
      assert.equal(permittedChatPage.status, 200, "chat-enabled account keeps access");
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
      // A project editor must be able to delete a disposable file.
      const disposable = await seedEncryptedFile(
        projectId, "disposable.txt", "text/plain", Buffer.from("DELETE_BY_EDITOR"), true
      );
      await expectStatus(`/api/files/${disposable}`, {
        as: "editor", method: "DELETE",
      }, 200);
      const gone = await db.query("SELECT 1 FROM project_files WHERE id=$1", [disposable]);
      assert.equal(gone.rowCount, 0);

      const unchanged = await expectStatus(`/api/files/${textFile}/content`, { as: "creator" }, 200);
      assert.equal((await unchanged.json()).content, "PRIVATE_PROJECT_CONTENT");
    });

    await t.test("project skills require exact owner review and remain tenant scoped", async () => {
      const base = `/api/projects/${projectId}/skills`;
      await expectStatus(base, { as: "outsider" }, 404);
      const draft = (await (await expectStatus(base, { as: "editor", method: "POST", body: {
        action: "create", name: "Evidence reporting", instructions: "Use supplied evidence and disclose missing information."
      } }, 200)).json()).skill;
      assert.equal(draft.status, "draft");
      const unicode=(await (await expectStatus(base,{as:"editor",method:"POST",body:{action:"create",name:"Unicode draft",instructions:"界".repeat(6000)}},200)).json()).skill;
      assert.equal(unicode.instructions.length,6000);
      assert.equal((await (await expectStatus(base, { as: "viewer" }, 200)).json()).skills.length, 0);
      await expectStatus(base, { as: "editor", method: "POST", body: {action:"activate", id:draft.id, contentSha256:draft.content_sha256} }, 403);
      await expectStatus(base, { as: "admin", method: "POST", body: {action:"activate", id:draft.id, contentSha256:"0".repeat(64)} }, 400);
      await expectStatus(base, { as: "admin", method: "POST", body: {action:"activate", id:draft.id, contentSha256:draft.content_sha256} }, 200);
      assert.equal((await (await expectStatus(base, { as: "viewer" }, 200)).json()).skills[0].status, "active");
      await expectStatus(base, { as: "admin", method: "POST", body: {action:"retire", id:draft.id, contentSha256:draft.content_sha256} }, 200);
      assert.equal((await (await expectStatus(base, { as: "viewer" }, 200)).json()).skills.length, 0);
    });

    await t.test("security scope, immutable evidence and local report downloads require platform owner", async () => {
      const base="/api/security/assessments";
      await expectStatus(base,{as:"editor"},403);
      await expectStatus(base,{as:"editor",method:"POST",body:{}},403);
      await expectStatus('/api/approvals/nonexistent/decision',{as:"editor",method:"POST",body:{decision:"approved"}},403);
      await expectStatus('/api/permissions/check',{as:"editor",method:"POST",body:{permission:"network.scan"}},403);
      const draft={action:"create",projectId,name:"Synthetic network evidence",targets:["192.0.2.10"],authorization:"Isolated synthetic fixture owned by CI",
        authorizationConfirmed:true,expiresAt:new Date(Date.now()+3600000).toISOString(),requestId:crypto.randomUUID()};
      const row=(await (await expectStatus(base,{as:"admin",method:"POST",body:draft},200)).json()).assessment;
      const retry=(await (await expectStatus(base,{as:"admin",method:"POST",body:draft},200)).json()).assessment;assert.equal(retry.id,row.id);
      await expectStatus(base,{as:"admin",method:"POST",body:{action:"approve",id:row.id,scopeDigest:"0".repeat(64)}},400);
      await expectStatus(base,{as:"admin",method:"POST",body:{action:"approve",id:row.id,scopeDigest:row.scope_digest}},200);
      const xml='<nmaprun scanner="nmap" version="fixture"><host><status state="up"/><address addr="192.0.2.10" addrtype="ipv4"/><ports><port protocol="tcp" portid="443"><state state="open"/><service name="https"/></port></ports></host><runstats><finished exit="success"/></runstats></nmaprun>';
      await expectStatus(base,{as:"admin",method:"POST",body:{action:"import",id:row.id,xml:xml.replace('192.0.2.10','192.0.2.11')}},400);
      const done=(await (await expectStatus(base,{as:"admin",method:"POST",body:{action:"import",id:row.id,xml}},200)).json()).assessment;
      assert.equal(done.status,"completed");assert.equal(done.result.observations[0].severity,"informational");
      await expectStatus(base,{as:"admin",method:"POST",body:{action:"import",id:row.id,xml}},200);
      await expectStatus(base,{as:"admin",method:"POST",body:{action:"import",id:row.id,xml:xml+' '}},400);
      const report=`${base}/${row.id}/report`;
      await expectStatus(report,{as:"viewer"},403);
      const pdf=await expectStatus(report,{as:"admin"},200);
      assert.match(Buffer.from(await pdf.arrayBuffer()).toString('ascii',0,8),/%PDF/);
      assert.match(pdf.headers.get('content-disposition'),/^attachment/);
      const original=await expectStatus(report+'?format=xml',{as:"admin"},200);assert.equal(await original.text(),xml);
    });

    await t.test("assessment cursor exposes older pages without duplicating equal timestamps",async()=>{
      const base="/api/security/assessments";const stamp=new Date().toISOString();
      for(let i=0;i<27;i++)await db.query(`INSERT INTO security_assessments (id,project_id,created_by,request_id,scope,scope_digest,status,created_at) VALUES ($1,$2,$3,$4,$5,$6,'pending',$7)`,[crypto.randomUUID(),projectId,users.admin.id,crypto.randomUUID(),JSON.stringify({name:"Pagination fixture",targets:["192.0.2.1"],expiresAt:stamp}),"fixture",stamp]);
      const first=await (await expectStatus(base,{as:"admin"},200)).json();assert.equal(first.assessments.length,25);assert.ok(first.nextCursor);
      const second=await (await expectStatus(base+"?after="+first.nextCursor,{as:"admin"},200)).json();assert.ok(second.assessments.length>=3);assert.ok(!second.assessments.some(row=>first.assessments.some(old=>old.id===row.id)));
      await expectStatus(base+"?after=invalid",{as:"admin"},400);
    });

    await t.test("usage call API exposes only authenticated users' own allowlisted counters",async()=>{
      const ids=[crypto.randomUUID(),crypto.randomUUID()];
      for(let i=0;i<2;i++)await db.query(`INSERT INTO usage_events (id,user_id,provider,model,input_tokens,output_tokens,cached_tokens,cost_chf,metadata) VALUES ($1,$2,'ci-ledger','offline',10,2,0,0,$3)`,[ids[i],i?users.outsider.id:users.editor.id,JSON.stringify({kind:"provider-call",usageKnown:true,costStatus:"reported",costUsd:0,reportedCostUsd:0,usdToChfRate:0.8,prompt:"private fixture"})]);
      await expectStatus('/api/usage/calls',{},401);
      const page=await (await expectStatus('/api/usage/calls',{as:"editor"},200)).json();assert.ok(page.calls.some(row=>row.id===ids[0]));assert.ok(!page.calls.some(row=>row.id===ids[1]));assert.ok(!JSON.stringify(page).includes('private fixture'));
      await expectStatus('/api/usage/calls?after='+ids[1],{as:"editor"},400);
      await db.query('DELETE FROM usage_events WHERE id=ANY($1::text[])',[ids]);
    });

    await t.test("read-only roles cannot mutate or spend even when features are enabled",async()=>{
      await expectStatus('/api/chat',{as:"reader",method:"POST",body:{message:"Must not enqueue"}},403);
      await expectStatus('/api/projects',{as:"reader",method:"POST",body:{name:"Must not create"}},403);
      await expectStatus('/api/skills',{as:"reader",method:"POST",body:{action:"create",name:"No write",instructions:"Must not create a skill."}},403);
      await expectStatus('/api/permissions/policies',{as:"reader"},403);
      await expectStatus('/api/budgets',{as:"reader",method:"POST",body:{}},403);
    });
    await t.test("global skills retain immutable versions, owner scope and parameter content",async()=>{
      const draft=(await (await expectStatus('/api/skills',{as:"editor",method:"POST",body:{action:"create",document:'---\nname: Version fixture\nparameters: {"tone":{"type":"string","default":"short"}}\n---\nSummarize supplied facts in a {{tone}} style.'}},200)).json()).skill;
      await expectStatus('/api/skills',{as:"editor",method:"POST",body:{action:"activate",id:draft.id,contentSha256:draft.content_sha256}},200);
      await expectStatus('/api/skills',{as:"outsider",method:"POST",body:{action:"activate",id:draft.id,contentSha256:draft.content_sha256}},400);
      const next=(await (await expectStatus('/api/skills',{as:"editor",method:"POST",body:{action:"revise",parentId:draft.id,baseContentSha256:draft.content_sha256,name:"Version fixture",instructions:"Summarize only supplied facts, with evidence references."}},200)).json()).skill;
      assert.equal(next.version,2);assert.equal(next.family_id,draft.family_id);assert.notEqual(next.content_sha256,draft.content_sha256);
      await expectStatus('/api/skills',{as:"editor",method:"POST",body:{action:"activate",id:next.id,contentSha256:next.content_sha256}},200);
      const skills=(await (await expectStatus('/api/skills',{as:"editor"},200)).json()).skills;assert.equal(skills.find(s=>s.id===draft.id).status,'retired');assert.equal(skills.find(s=>s.id===next.id).status,'active');assert.equal(skills.find(s=>s.id===draft.id).instructions,draft.instructions);
      await db.query('DELETE FROM project_skills WHERE id=ANY($1::text[])',[[draft.id,next.id]]);
    });
    await t.test("active scan API binds saved targets to authorization and never starts an unapproved run",async()=>{
      const endpoint='/api/security/assets';await expectStatus(endpoint,{as:"editor"},403);await expectStatus(endpoint,{as:"reader"},403);
      const input={requestId:crypto.randomUUID(),name:"Isolated CI network fixture",target:"10.255.255.254:443",kind:"web",ports:[443],authorized:true,checkAdvisories:false};
      await expectStatus(endpoint,{as:"operator",method:"POST",body:{...input,authorized:false}},400);
      await expectStatus(endpoint,{as:"operator",method:"POST",body:{...input,target:'169.254.169.254'}},400);
      const asset=await (await expectStatus(endpoint,{as:"operator",method:"POST",body:input},201)).json();assert.equal(asset.approvalStatus,'pending');
      const duplicate=await (await expectStatus(endpoint,{as:"operator",method:"POST",body:input},201)).json();assert.equal(duplicate.id,asset.id);
      await expectStatus('/api/security/scans',{as:"operator",method:"POST",body:{assetId:asset.id}},403);
      await expectStatus('/api/approvals/'+asset.approvalId+'/decision',{as:"admin",method:"POST",body:{decision:'approved'}},200);
      const scan=await (await expectStatus('/api/security/scans',{as:"operator",method:"POST",body:{assetId:asset.id}},202)).json();assert.equal(scan.status,'queued');
      await expectStatus('/api/security/scans/'+scan.id,{as:"admin"},404);
      const owned=(await (await expectStatus('/api/security/scans/'+scan.id,{as:"operator"},200)).json()).run;assert.equal(owned.status,'queued');assert.equal(owned.result,null);
      await expectStatus('/api/security/scans/'+scan.id,{as:"operator",method:"DELETE"},200);
      await expectStatus(endpoint,{as:"operator",method:"DELETE",body:{id:asset.id}},200);
      const state=await db.query('SELECT status FROM security_scan_runs WHERE id=$1',[scan.id]);assert.equal(state.rows[0].status,'cancelled');
      await db.query('DELETE FROM security_scan_runs WHERE id=$1',[scan.id]);await db.query('DELETE FROM security_assets WHERE id=$1',[asset.id]);await db.query('DELETE FROM approvals WHERE id=$1',[asset.approvalId]);
    });
    await t.test("owner policy and budget writes are validated and audited",async()=>{
      await expectStatus('/api/permissions/policies',{as:"editor",method:"POST",body:{role:"admin",policy:{models:[]}}},403);
      await expectStatus('/api/permissions/policies',{as:"admin",method:"POST",body:{role:"admin",policy:{models:['openai/fixture'],tools:['project_search']}}},200);
      const policies=await (await expectStatus('/api/permissions/policies',{as:"admin"},200)).json();assert.deepEqual(policies.roles.find(r=>r.role==='admin').policy.models,['openai/fixture']);
      await expectStatus('/api/budgets',{as:"admin",method:"POST",body:{scope:'user:'+users.editor.id,currency:'CHF',monthlyWarning:'0.1',monthlyHard:'0.2'}},200);
      await expectStatus('/api/budgets',{as:"admin",method:"POST",body:{scope:'user:'+users.editor.id,currency:'CHF',monthlyWarning:'5',monthlyHard:'1'}},400);
      const budgets=await (await expectStatus('/api/budgets',{as:"editor"},200)).json();assert.equal(budgets.canManage,false);assert.ok(budgets.limits.every(row=>row.scope==='workspace'||row.scope==='user:'+users.editor.id));
      await db.query('DELETE FROM budget_limits WHERE scope=$1',['user:'+users.editor.id]);await db.query("DELETE FROM role_capability_policies WHERE role='admin'");
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

