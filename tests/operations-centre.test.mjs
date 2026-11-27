import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import {
  words,
  keywordHashes,
  memoryInput,
  renderMemories,
} from "../lib/brain/retrieval.mjs";
import { teamPolicy, teamContext } from "../lib/teams/policy.mjs";
import { withTeamCalls, admitTeamCall } from "../lib/teams/call-scope.mjs";
import {
  connectionInput,
  connectorHeaders,
  readConnector,
  actionSpec,
} from "../lib/connectors/catalog.mjs";
import { connectionUrl } from "../lib/connectors/http.mjs";
import {
  verifyTrafficSignature,
  normalizeTraffic,
} from "../lib/traffic/events.mjs";
import { githubSkillUrl, parseAgentSkill } from "../lib/skill-import.mjs";
import { runActiveScan } from "../lib/security/active-scan.mjs";
import { securityApprovalScope } from "../lib/security/approval-scope.mjs";

test("memory normalizes bounded facts, rejects credentials and does not expose searchable cleartext", () => {
  const input = memoryInput({
    title: "Preferred reports",
    body: "Use metric units and include source references.",
    pinned: false,
    tags: ["reports"],
  });
  assert.equal(input.tags[0], "reports");
  assert.deepEqual(words("REPORTS reports Wörter"), ["reports", "wörter"]);
  const hashes = keywordHashes(input.body, "fixture-key");
  assert.equal(hashes[0].length, 64);
  assert.notEqual(hashes[0], keywordHashes(input.body, "different-key")[0]);
  assert.throws(
    () => memoryInput({ ...input, body: "password: supersecret123" }),
    /CREDENTIAL/,
  );
  assert.throws(
    () => memoryInput({ ...input, expiresAt: "2000-01-01" }),
    /EXPIRY/,
  );
});
test("shared Brain context stays within its UTF-8 budget and includes provenance", () => {
  const rows = Array.from({ length: 6 }, (_, i) => ({
    id: String(i),
    title: "Saved choice",
    revision: 2,
    body: "近".repeat(1500),
    source: "User supplied",
  }));
  const rendered = renderMemories(rows);
  assert.ok(Buffer.byteLength(rendered) <= 2400);
  assert.match(rendered, /revision 2/);
  assert.match(rendered, /not instructions/);
  assert.equal(renderMemories([]), "");
});
test("team selection is explicit and bounded; async branches share one admission scope", async () => {
  assert.equal(teamPolicy(undefined), null);
  assert.throws(() =>
    teamPolicy({ roles: ["research", "research"], maxCalls: 8 }),
  );
  assert.throws(() => teamPolicy({ roles: ["__proto__"], maxCalls: 4 }));
  assert.match(
    teamContext(teamPolicy({ roles: ["data"], maxCalls: 4 })),
    /Maximum 4/,
  );
  let used = 0;
  await withTeamCalls(
    async () => {
      if (used >= 2) throw Error("cap");
      used++;
    },
    async () => {
      const results = await Promise.allSettled([
        admitTeamCall(),
        admitTeamCall(),
        admitTeamCall(),
      ]);
      assert.equal(
        results.filter((row) => row.status === "fulfilled").length,
        2,
      );
    },
  );
  await admitTeamCall();
  assert.equal(used, 2);
});
test("connections prohibit URL credentials, injected headers, forged fixed origins and unbounded actions", () => {
  assert.throws(() => connectionUrl("https://user:secret@example.org"));
  assert.throws(() => connectionUrl("file:///etc/passwd"));
  assert.throws(() =>
    connectionInput({
      kind: "github",
      name: "GitHub",
      base: "https://evil.example",
      secret: "token",
    }),
  );
  assert.throws(() =>
    connectionInput({
      kind: "checkmk",
      name: "Checkmk",
      username: "a b",
      secret: "token",
    }),
  );
  assert.equal(
    connectorHeaders("patchmon", { username: "key", secret: "secret" })
      .Authorization,
    "Basic a2V5OnNlY3JldA==",
  );
  assert.throws(() => actionSpec("github", { action: "delete-repository" }));
  assert.throws(() =>
    actionSpec("slack", {
      action: "send-message",
      channel: "../bad",
      text: "hello",
    }),
  );
  assert.equal(
    actionSpec("github", {
      action: "create-issue",
      repository: "example/repo",
      title: "Test",
      body: "Evidence",
    }).path,
    "repos/example/repo/issues",
  );
});
test("typed connectors use documented endpoints and normalize only selected fields", async () => {
  const paths = [];
  const snapshot = await readConnector(
    { kind: "patchmon" },
    { username: "key", secret: "secret" },
    async (path, options) => {
      paths.push(path);
      assert.match(options.headers.Authorization, /^Basic /);
      return {
        hosts: [
          {
            id: "1",
            hostname: "fixture-host",
            os_version: "1",
            api_key: "NEVER_RETURN",
          },
        ],
      };
    },
  );
  assert.deepEqual(paths, ["api/hosts"]);
  assert.equal(snapshot.resources[0].name, "fixture-host");
  assert.ok(!JSON.stringify(snapshot).includes("NEVER_RETURN"));
  let count = 0;
  await assert.rejects(
    readConnector(
      { kind: "wazuh" },
      { username: "reader", secret: "secret" },
      async (path) => {
        count++;
        return path.startsWith("security") ? "bad token" : "x";
      },
    ),
    /WAZUH_AUTH_FAILED/,
  );
  assert.equal(count, 1);
});
test("traffic signatures bind timestamp, nonce and exact bytes; stale and modified events fail", () => {
  const key = "fixture-".repeat(8),
    timestamp = String(Date.now()),
    nonce = crypto.randomUUID(),
    body = Buffer.from('{"events":[]}'),
    signature = crypto
      .createHmac("sha256", key)
      .update(timestamp + "\n" + nonce + "\n")
      .update(body)
      .digest("hex");
  const args = { key, timestamp, nonce, body, signature };
  assert.equal(verifyTrafficSignature(args), true);
  assert.equal(
    verifyTrafficSignature({ ...args, body: Buffer.from("changed") }),
    false,
  );
  assert.equal(
    verifyTrafficSignature({ ...args, now: Date.now() + 120000 }),
    false,
  );
  assert.equal(verifyTrafficSignature({ ...args, key: "" }), false);
});
test("traffic never invents location or conflates HTTP requests with connections", () => {
  const input = {
    sourceIp: "192.0.2.20",
    service: "Example web",
    kind: "http-request",
    observedAt: new Date().toISOString(),
    latitude: 12,
    longitude: 8,
  };
  assert.equal(normalizeTraffic({ events: [input] })[0].country, null);
  assert.equal(normalizeTraffic({ events: [input] })[0].latitude, undefined);
  assert.throws(() =>
    normalizeTraffic({ events: [{ ...input, kind: "users" }] }),
  );
  assert.throws(() =>
    normalizeTraffic({ events: [{ ...input, sourceIp: "example.org" }] }),
  );
});
test("Agent Skills import pins GitHub syntax, parses YAML, refuses aliases and executable grants", () => {
  const source =
    "---\nname: source-report\ndescription: Summarize source evidence.\nlicense: MIT\nallowed-tools: Bash\n---\nUse citations and distinguish observations from assumptions.";
  const parsed = parseAgentSkill(source);
  assert.equal(parsed.license, "MIT");
  assert.equal(parsed.parameters.constructor, Object);
  assert.ok(!Object.hasOwn(parsed, "tools"));
  assert.equal(
    githubSkillUrl(
      "https://github.com/example/repo/blob/main/skills/report/SKILL.md",
    ).path,
    "skills/report/SKILL.md",
  );
  for (const url of [
    "https://evil.example/example/repo/blob/main/SKILL.md",
    "https://github.com/example/repo/raw/main/SKILL.md",
    "https://github.com/example/repo/blob/main/SKILL.md?token=x",
  ])
    assert.throws(() => githubSkillUrl(url));
  assert.throws(
    () =>
      parseAgentSkill(
        "---\nname: &a source-report\ndescription: *a\n---\nMake a source report.",
      ),
    /FRONTMATTER/,
  );
});
test("web profile uses Host/SNI probes without TCP discovery and remains bound to authorization hash", async () => {
  const target = {
      host: "app.example.org",
      ports: [443],
      scheme: "https",
      explicitPort: 443,
      profile: "web",
    },
    scope = {
      target,
      addresses: ["93.184.216.34"],
      packages: [],
      checkAdvisories: false,
    };
  const digest = crypto
    .createHash("sha256")
    .update(JSON.stringify(scope))
    .digest("hex");
  assert.deepEqual(
    securityApprovalScope({
      scope,
      active: true,
      requested_by: "owner",
      owner_user_id: "owner",
      resource_id: "asset",
      asset_id: "asset",
      id: "approval",
      approval_id: "approval",
      scope_digest: digest,
      asset_scope_digest: digest,
    }),
    scope,
  );
  let tcpCalls = 0,
    webCalls = 0;
  await runActiveScan(scope, {
    resolve: async () => scope.addresses,
    tcp: async () => {
      tcpCalls++;
      throw Error("should not happen");
    },
    web: async (address, port, host, secure) => {
      webCalls++;
      assert.equal(host, "app.example.org");
      assert.equal(secure, true);
      return { address, port, status: 200, findings: [] };
    },
  });
  assert.equal(tcpCalls, 0);
  assert.equal(webCalls, 1);
  await assert.rejects(
    runActiveScan(
      {
        ...scope,
        kind: "web",
        target: { ...target, profile: undefined, ports: [22, 443] },
      },
      { resolve: async () => scope.addresses },
    ),
    /WEB_SCOPE_REAUTHORIZE/,
  );
});
