import pg from "pg";

const { Pool } = pg;

const globalForDb = globalThis;

export const db =
  globalForDb.vectorDb ||
  new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 5,
    idleTimeoutMillis: 30000,
    connectionTimeoutMillis: 5000
  });

if (process.env.NODE_ENV !== "production") {
  globalForDb.vectorDb = db;
}

let initialized = false;

export async function initializeDatabase() {
  if (initialized) {
    return;
  }

  await db.query(`
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      description TEXT,
      privacy_level TEXT NOT NULL DEFAULT 'internal',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS conversations (
      id TEXT PRIMARY KEY,
      project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
      title TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS messages (
      id TEXT PRIMARY KEY,
      conversation_id TEXT REFERENCES conversations(id) ON DELETE CASCADE,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      model TEXT,
      cost_chf NUMERIC(12, 6) NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY,
      project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
      title TEXT NOT NULL,
      description TEXT,
      status TEXT NOT NULL DEFAULT 'pending',
      task_type TEXT NOT NULL DEFAULT 'normal',
      privacy_level TEXT NOT NULL DEFAULT 'internal',
      budget_chf NUMERIC(12, 6),
      spent_chf NUMERIC(12, 6) NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      started_at TIMESTAMPTZ,
      completed_at TIMESTAMPTZ
    );
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS approvals (
      id TEXT PRIMARY KEY,
      task_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
      permission TEXT NOT NULL,
      action TEXT NOT NULL,
      description TEXT,
      status TEXT NOT NULL DEFAULT 'pending',
      requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      decided_at TIMESTAMPTZ,
      decided_by TEXT
    );
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS audit_log (
      id TEXT PRIMARY KEY,
      actor TEXT NOT NULL,
      action TEXT NOT NULL,
      resource TEXT,
      details JSONB,
      source TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS usage_events (
      id TEXT PRIMARY KEY,
      provider TEXT,
      model TEXT,
      task_id TEXT REFERENCES tasks(id) ON DELETE SET NULL,
      user_id TEXT,
      input_tokens BIGINT NOT NULL DEFAULT 0,
      output_tokens BIGINT NOT NULL DEFAULT 0,
      cached_tokens BIGINT NOT NULL DEFAULT 0,
      cost_chf NUMERIC(12, 6) NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await db.query(`
    ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS user_id TEXT;
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_usage_user_created_at
    ON usage_events(user_id, created_at DESC);
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS privacy_events (
      id TEXT PRIMARY KEY,
      actor TEXT NOT NULL,
      classification TEXT NOT NULL,
      finding_count INTEGER NOT NULL DEFAULT 0,
      finding_types JSONB,
      source TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  await db.query(`
    CREATE TABLE IF NOT EXISTS permission_policies (
      permission TEXT PRIMARY KEY,
      decision TEXT NOT NULL,
      description TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);

  const permissionDefaults = [
    [
      "filesystem.read",
      "ALLOW",
      "Read files Vector has explicitly been given access to."
    ],
    [
      "filesystem.write_sandbox",
      "ALLOW",
      "Write files inside an isolated Vector workspace."
    ],
    [
      "filesystem.write_host",
      "ASK",
      "Write or modify files on the host system."
    ],
    [
      "process.inspect",
      "ALLOW",
      "Inspect allowed processes and system state."
    ],
    [
      "process.execute_sandbox",
      "ALLOW",
      "Execute commands inside an isolated sandbox."
    ],
    [
      "process.execute_host",
      "ASK",
      "Execute commands directly on the Vector host."
    ],
    [
      "docker.inspect",
      "ALLOW",
      "Inspect Docker containers and their status."
    ],
    [
      "docker.modify",
      "ASK",
      "Start, stop, recreate or modify Docker resources."
    ],
    [
      "service.restart",
      "ASK",
      "Restart or reload host services."
    ],
    [
      "git.read",
      "ALLOW",
      "Read repositories, history and diffs."
    ],
    [
      "git.commit",
      "ALLOW",
      "Create commits in Vector workspaces."
    ],
    [
      "git.push",
      "ASK",
      "Push changes to remote repositories."
    ],
    [
      "email.read",
      "ALLOW",
      "Read mail from connected approved accounts."
    ],
    [
      "email.draft",
      "ALLOW",
      "Create mail drafts."
    ],
    [
      "email.send",
      "ASK",
      "Send email externally."
    ],
    [
      "network.scan",
      "ASK",
      "Perform active network or vulnerability scanning."
    ],
    [
      "server.modify",
      "ASK",
      "Make persistent server configuration changes."
    ],
    [
      "server.destructive",
      "DENY",
      "Potentially destructive host operations."
    ],
    [
      "secret.read",
      "DENY",
      "Directly expose protected secrets to agents."
    ]
  ];

  for (const [
    permission,
    decision,
    description
  ] of permissionDefaults) {
    await db.query(
      `
        INSERT INTO permission_policies (
          permission,
          decision,
          description
        )
        VALUES ($1, $2, $3)
        ON CONFLICT (permission)
        DO NOTHING
      `,
      [
        permission,
        decision,
        description
      ]
    );
  }

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_audit_log_created_at
    ON audit_log(created_at DESC);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_tasks_status
    ON tasks(status);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_usage_created_at
    ON usage_events(created_at DESC);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_approvals_status
    ON approvals(status);
  `);

  await db.query(`
    CREATE INDEX IF NOT EXISTS idx_privacy_created
    ON privacy_events(created_at DESC);
  `);

  initialized = true;
}
