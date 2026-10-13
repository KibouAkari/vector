import crypto from "node:crypto";
import { db, initializeDatabase } from "./db";
import { getUserUsageTotals } from "./usage-store.mjs";
import { projectAccessAllowed } from "./project-access-policy.mjs";

export const FEATURES = ["chat","projects","server","models","activity"];

function normalizeFeatures(value = {}, role = "member") {
  if (role === "owner") {
    return Object.fromEntries(FEATURES.map((x) => [x, true]));
  }

  return {
    chat: value.chat !== false,
    projects: Boolean(value.projects),
    server: Boolean(value.server),
    models: Boolean(value.models),
    activity: Boolean(value.activity)
  };
}

function hashPassword(password) {
  const salt = crypto.randomBytes(24).toString("hex");
  const hash = crypto.scryptSync(String(password), salt, 64).toString("hex");
  return { salt, hash };
}

function passwordMatches(password, salt, stored) {
  if (!password || !salt || !stored) return false;
  try {
    const calculated = crypto.scryptSync(String(password), salt, 64).toString("hex");
    const a = Buffer.from(calculated, "hex");
    const b = Buffer.from(stored, "hex");
    return a.length === b.length && crypto.timingSafeEqual(a, b);
  } catch {
    return false;
  }
}

export async function initializeIdentity() {
  await initializeDatabase();

  await db.query(`
    CREATE TABLE IF NOT EXISTS vector_users (
      id TEXT PRIMARY KEY,
      username TEXT NOT NULL,
      display_name TEXT,
      password_salt TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'member',
      enabled BOOLEAN NOT NULL DEFAULT TRUE,
      features JSONB NOT NULL DEFAULT '{}'::jsonb,
      monthly_budget_chf NUMERIC,
      total_budget_chf NUMERIC,
      expires_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      last_login_at TIMESTAMPTZ
    );
  `);

  await db.query(`CREATE UNIQUE INDEX IF NOT EXISTS idx_vector_users_username ON vector_users (LOWER(username));`);

  await db.query(`
    CREATE TABLE IF NOT EXISTS project_members (
      project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      user_id TEXT NOT NULL REFERENCES vector_users(id) ON DELETE CASCADE,
      access_role TEXT NOT NULL DEFAULT 'viewer',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (project_id,user_id)
    );
  `);

  await db.query(`ALTER TABLE projects ADD COLUMN IF NOT EXISTS owner_user_id TEXT;`);
  await db.query(`ALTER TABLE conversations ADD COLUMN IF NOT EXISTS owner_user_id TEXT;`);

  const username = process.env.VECTOR_ADMIN_USER;
  const salt = process.env.VECTOR_ADMIN_SALT;
  const hash = process.env.VECTOR_ADMIN_PASSWORD_HASH;

  if (username && salt && hash) {
    let owner = await db.query(`SELECT id FROM vector_users WHERE role='owner' ORDER BY created_at LIMIT 1`);

    if (owner.rowCount === 0) {
      const id = crypto.randomUUID();
      await db.query(`
        INSERT INTO vector_users (
          id,username,display_name,password_salt,password_hash,role,enabled,features
        ) VALUES ($1,$2,$3,$4,$5,'owner',TRUE,$6::jsonb)
      `,[id,username,username,salt,hash,JSON.stringify(normalizeFeatures({},"owner"))]);
      owner = { rows: [{ id }], rowCount: 1 };
    }

    const ownerId = owner.rows[0].id;
    await db.query(`UPDATE projects SET owner_user_id=$1 WHERE owner_user_id IS NULL`,[ownerId]);
    await db.query(`UPDATE conversations SET owner_user_id=$1 WHERE owner_user_id IS NULL`,[ownerId]);
  }
}

export function publicUser(user) {
  return {
    userId: user.id,
    username: user.username,
    displayName: user.display_name || user.username,
    role: user.role,
    enabled: Boolean(user.enabled),
    features: normalizeFeatures(user.features || {}, user.role),
    monthlyBudgetChf: user.monthly_budget_chf == null ? null : Number(user.monthly_budget_chf),
    totalBudgetChf: user.total_budget_chf == null ? null : Number(user.total_budget_chf),
    expiresAt: user.expires_at || null
  };
}

export async function getUserById(id) {
  await initializeIdentity();
  const r = await db.query(`SELECT * FROM vector_users WHERE id=$1 LIMIT 1`,[id]);
  return r.rows[0] || null;
}

export async function getUserByUsername(username) {
  await initializeIdentity();
  const r = await db.query(`SELECT * FROM vector_users WHERE LOWER(username)=LOWER($1) LIMIT 1`,[String(username||"").trim()]);
  return r.rows[0] || null;
}

export async function authenticateUser(username,password) {
  const user = await getUserByUsername(username);
  if (!user || !user.enabled) return null;
  if (user.expires_at && new Date(user.expires_at).getTime() <= Date.now()) return null;
  if (!passwordMatches(password,user.password_salt,user.password_hash)) return null;
  await db.query(`UPDATE vector_users SET last_login_at=NOW() WHERE id=$1`,[user.id]);
  return publicUser(user);
}

export async function createUser(body) {
  await initializeIdentity();
  const username = String(body.username||"").trim();
  const password = String(body.password||"");
  if (!/^[A-Za-z0-9._-]{2,64}$/.test(username)) throw new Error("Invalid username.");
  if (password.length < 8) throw new Error("Password must have at least 8 characters.");
  if (await getUserByUsername(username)) throw new Error("Username already exists.");

  const id = crypto.randomUUID();
  const {salt,hash} = hashPassword(password);
  const role = body.role === "owner" ? "owner" : "member";

  await db.query(`
    INSERT INTO vector_users (
      id,username,display_name,password_salt,password_hash,role,enabled,features,
      monthly_budget_chf,total_budget_chf,expires_at
    ) VALUES ($1,$2,$3,$4,$5,$6,TRUE,$7::jsonb,$8,$9,$10)
  `,[
    id,username,String(body.displayName||username).trim(),salt,hash,role,
    JSON.stringify(normalizeFeatures(body.features||{},role)),
    body.monthlyBudgetChf === "" ? null : body.monthlyBudgetChf ?? null,
    body.totalBudgetChf === "" ? null : body.totalBudgetChf ?? null,
    body.expiresAt || null
  ]);
  return id;
}

export async function updateUser(id,body) {
  const current = await getUserById(id);
  if (!current) throw new Error("User not found.");

  let salt = current.password_salt;
  let hash = current.password_hash;
  if (body.password) ({salt,hash} = hashPassword(body.password));

  const role = body.role === "owner" ? "owner" : (body.role === "member" ? "member" : current.role);

  await db.query(`
    UPDATE vector_users SET
      display_name=$2,password_salt=$3,password_hash=$4,role=$5,enabled=$6,
      features=$7::jsonb,monthly_budget_chf=$8,total_budget_chf=$9,expires_at=$10,updated_at=NOW()
    WHERE id=$1
  `,[
    id,
    body.displayName !== undefined ? String(body.displayName||current.username) : current.display_name,
    salt,hash,role,
    body.enabled !== undefined ? Boolean(body.enabled) : current.enabled,
    JSON.stringify(normalizeFeatures(body.features !== undefined ? body.features : current.features,role)),
    body.monthlyBudgetChf !== undefined ? (body.monthlyBudgetChf === "" ? null : body.monthlyBudgetChf) : current.monthly_budget_chf,
    body.totalBudgetChf !== undefined ? (body.totalBudgetChf === "" ? null : body.totalBudgetChf) : current.total_budget_chf,
    body.expiresAt !== undefined ? (body.expiresAt || null) : current.expires_at
  ]);
}

export async function listUsers() {
  await initializeIdentity();
  const r = await db.query(`SELECT * FROM vector_users ORDER BY CASE WHEN role='owner' THEN 0 ELSE 1 END,LOWER(username)`);
  return r.rows.map(publicUser);
}

export function hasFeature(session,feature) {
  return Boolean(session && (session.role === "owner" || session.features?.[feature]));
}

/**
 * Check database-owned membership on every project resource request.
 */
export async function canUseProject(session, projectId, action = "read") {
  if (!session?.userId || typeof projectId !== "string" || !projectId) {
    return false;
  }
  if (!hasFeature(session, "projects")) return false;

  const result = await db.query(`
    SELECT p.owner_user_id, pm.access_role
    FROM projects p
    LEFT JOIN project_members pm
      ON pm.project_id = p.id AND pm.user_id = $2
    WHERE p.id = $1 LIMIT 1
  `, [projectId, session.userId]);

  if (result.rowCount !== 1) return false;
  return projectAccessAllowed({
    session,
    projectOwnerId: result.rows[0].owner_user_id,
    membershipRole: result.rows[0].access_role,
    action,
  });
}

export async function canAccessProject(session, projectId) {
  return canUseProject(session, projectId, "read");
}
export async function canEditProject(session, projectId) {
  return canUseProject(session, projectId, "write");
}
export async function canManageProject(session, projectId) {
  return canUseProject(session, projectId, "manage");
}

export async function assertUserBudget(session) {
  if (!session || session.role === "owner") return {allowed:true};
  const { total, month } = await getUserUsageTotals(db, session.userId);
  if (session.monthlyBudgetChf != null && month >= session.monthlyBudgetChf) return {allowed:false,reason:`Monthly AI budget of CHF ${session.monthlyBudgetChf.toFixed(2)} has been reached.`};
  if (session.totalBudgetChf != null && total >= session.totalBudgetChf) return {allowed:false,reason:`Total AI budget of CHF ${session.totalBudgetChf.toFixed(2)} has been reached.`};
  return {allowed:true};
}
