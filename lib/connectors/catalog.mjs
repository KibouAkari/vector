export const CONNECTORS = [
  {
    id: "checkmk",
    name: "Checkmk",
    category: "Monitoring",
    base: "https://monitor.example.com/site/check_mk/api/1.0",
    auth: "automation",
    hint: "API base including site and supported API version. Automation user and secret.",
  },
  {
    id: "wazuh",
    name: "Wazuh",
    category: "Security",
    base: "https://security.example.com:55000",
    auth: "basic",
    hint: "Manager API, not the dashboard. API user with read access to agents.",
  },
  {
    id: "patchmon",
    name: "PatchMon",
    category: "Monitoring",
    base: "https://patch.example.com/api/v1",
    auth: "basic",
    hint: "Scoped integration token key and secret with host:get permission.",
  },
  {
    id: "github",
    name: "GitHub",
    category: "Work",
    base: "https://api.github.com",
    auth: "bearer",
    fixed: true,
    hint: "Fine-grained token. Read metadata; add Issues write only if needed.",
  },
  {
    id: "slack",
    name: "Slack",
    category: "Channels",
    base: "https://slack.com/api",
    auth: "bearer",
    fixed: true,
    hint: "Bot token with auth.test access. chat:write for approved messages.",
  },
  {
    id: "notion",
    name: "Notion",
    category: "Knowledge",
    base: "https://api.notion.com/v1",
    auth: "bearer",
    fixed: true,
    hint: "Integration token. Share only the intended pages with this integration.",
  },
  {
    id: "gmail",
    name: "Gmail",
    category: "Channels",
    base: "https://gmail.googleapis.com/gmail/v1",
    auth: "bearer",
    fixed: true,
    hint: "OAuth access token with gmail.readonly or gmail.compose. Refresh tokens are not managed here.",
  },
  {
    id: "figma",
    name: "Figma",
    category: "Design",
    base: "https://api.figma.com/v1",
    auth: "figma",
    fixed: true,
    hint: "Personal access token with current_user:read scope.",
  },
  {
    id: "salesforce",
    name: "Salesforce",
    category: "Work",
    base: "https://your-instance.my.salesforce.com/services/data/v66.0",
    auth: "bearer",
    hint: "Instance REST API base with an API version supported by your org and an OAuth access token.",
  },
  {
    id: "api",
    name: "HTTP API",
    category: "Custom",
    base: "https://api.example.com/v1",
    auth: "bearer",
    hint: "Fixed-origin read endpoint returning JSON. No redirects or arbitrary remote code.",
  },
];
export function connectionInput(input) {
  const kind = CONNECTORS.find((row) => row.id === input.kind);
  if (!kind) throw Error("INVALID_CONNECTOR");
  const name = String(input.name || "").trim(),
    base = String(input.base || kind.base).replace(/\/$/, "");
  if (name.length < 2 || name.length > 80 || (kind.fixed && base !== kind.base))
    throw Error("INVALID_CONNECTION");
  const username = String(input.username || ""),
    secret = String(input.secret || "");
  if (
    username.length > 160 ||
    /[\r\n]/.test(username) ||
    secret.length > 8000 ||
    !secret ||
    /[\r\n]/.test(secret)
  )
    throw Error("INVALID_CREDENTIAL");
  if (
    ["basic", "automation"].includes(kind.auth) &&
    (!username ||
      username.includes(":") ||
      (kind.auth === "automation" && /\s/.test(username)))
  )
    throw Error("INVALID_CREDENTIAL");
  const readPath = String(input.readPath || "status");
  if (!/^[a-zA-Z0-9/_-]{1,160}$/.test(readPath))
    throw Error("INVALID_READ_PATH");
  return { kind: kind.id, name, base, username, secret, readPath };
}
export function connectorHeaders(kind, credentials) {
  if (kind === "figma") return { "X-Figma-Token": credentials.secret };
  if (kind === "checkmk")
    return {
      Authorization: `Bearer ${credentials.username} ${credentials.secret}`,
    };
  if (["patchmon", "wazuh"].includes(kind))
    return {
      Authorization:
        "Basic " +
        Buffer.from(credentials.username + ":" + credentials.secret).toString(
          "base64",
        ),
    };
  return {
    Authorization: "Bearer " + credentials.secret,
    ...(kind === "notion" ? { "Notion-Version": "2022-06-28" } : {}),
    ...(kind === "github" ? { "X-GitHub-Api-Version": "2022-11-28" } : {}),
  };
}
const list = (value) => (Array.isArray(value) ? value : []);
const text = (v, max = 160) =>
  String(v ?? "")
    .replace(/[\x00-\x1f\x7f]/g, " ")
    .slice(0, max);
export async function readConnector(connection, credentials, request) {
  const headers = connectorHeaders(connection.kind, credentials);
  const get = (path) => request(path, { headers });
  let rows = [],
    summary = {};
  switch (connection.kind) {
    case "checkmk": {
      const data = await get(
        "domain-types/host/collections/all?columns=name&columns=state",
      );
      rows = list(data.value).map((row) => ({
        id: text(row.id),
        name: text(row.title || row.extensions?.name || row.id),
        state: text(row.extensions?.state ?? "unknown"),
      }));
      summary = { hosts: rows.length, scope: "First response page" };
      break;
    }
    case "wazuh": {
      const jwt = await request("security/user/authenticate?raw=true", {
        method: "POST",
        headers,
        raw: true,
      });
      if (!/^[A-Za-z0-9_.-]+$/.test(jwt)) throw Error("WAZUH_AUTH_FAILED");
      const data = await request("agents?limit=100", {
        headers: { Authorization: "Bearer " + jwt },
      });
      if (data.error) throw Error("WAZUH_API_ERROR");
      rows = list(data.data?.affected_items).map((row) => ({
        id: text(row.id),
        name: text(row.name),
        state: text(row.status),
        version: text(row.version),
        address: text(row.ip),
      }));
      summary = {
        agents: data.data?.total_affected_items ?? rows.length,
        displayed: rows.length,
      };
      break;
    }
    case "patchmon": {
      const data = await get("api/hosts");
      rows = list(data.hosts || data.data?.hosts || data.data || data).map(
        (row) => ({
          id: text(row.id),
          name: text(row.friendly_name || row.hostname || row.name),
          state: text(row.status || "reported"),
          version: text(row.os_version || row.os),
          updates: row.updates_count ?? row.outdated_packages ?? null,
        }),
      );
      summary = { hosts: rows.length, scope: "First response page" };
      break;
    }
    case "github": {
      const data = await get("user");
      summary = {
        account: text(data.login),
        publicRepos: data.public_repos,
        privateRepos: data.total_private_repos ?? null,
      };
      break;
    }
    case "slack": {
      const data = await get("auth.test");
      if (!data.ok) throw Error("SLACK_AUTH_FAILED");
      summary = {
        workspace: text(data.team),
        account: text(data.user),
        workspaceId: text(data.team_id),
      };
      break;
    }
    case "notion": {
      const data = await get("users/me");
      summary = {
        account: text(data.name),
        workspace: text(data.bot?.workspace_name),
        type: text(data.type),
      };
      break;
    }
    case "gmail": {
      const data = await get("users/me/profile");
      summary = {
        account: text(data.emailAddress),
        messages: data.messagesTotal,
        threads: data.threadsTotal,
      };
      break;
    }
    case "figma": {
      const data = await get("me");
      summary = { account: text(data.handle), id: text(data.id) };
      break;
    }
    case "salesforce": {
      const data = await get("limits");
      summary = {
        dailyRequestsRemaining: data.DailyApiRequests?.Remaining ?? null,
        dailyRequestsLimit: data.DailyApiRequests?.Max ?? null,
      };
      break;
    }
    case "api": {
      const data = await get(connection.config.readPath);
      summary = {
        responseType: Array.isArray(data) ? "array" : typeof data,
        items: Array.isArray(data)
          ? data.length
          : Object.keys(data || {}).length,
      };
      break;
    }
  }
  return {
    summary,
    resources: rows.slice(0, 100),
    observedAt: new Date().toISOString(),
  };
}
export function actionSpec(kind, input) {
  if (!input || typeof input !== "object") throw Error("INVALID_ACTION");
  if (
    kind === "github" &&
    input.action === "create-issue" &&
    /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(input.repository) &&
    typeof input.title === "string" &&
    input.title.trim().length > 0 &&
    input.title.length <= 200 &&
    typeof input.body === "string" &&
    input.body.length <= 12000
  )
    return {
      method: "POST",
      path: "repos/" + input.repository + "/issues",
      body: { title: input.title, body: input.body },
    };
  if (
    kind === "slack" &&
    input.action === "send-message" &&
    /^[CDG][A-Z0-9]{8,30}$/.test(input.channel) &&
    typeof input.text === "string" &&
    input.text.length > 0 &&
    input.text.length <= 4000
  )
    return {
      method: "POST",
      path: "chat.postMessage",
      body: {
        channel: input.channel,
        text: input.text,
        unfurl_links: false,
        unfurl_media: false,
      },
    };
  throw Error("UNSUPPORTED_CONNECTOR_ACTION");
}
