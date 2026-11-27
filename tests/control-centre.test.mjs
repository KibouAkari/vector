import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { readFileSync } from "node:fs";
import { skillDocument, renderSkill } from "../lib/skill-document.mjs";
import { previewRanges, previewSegments } from "../lib/privacy-preview.mjs";
import { roleAllows, normalizeRolePolicy } from "../lib/role-policy.mjs";
import { callCostLabel } from "../lib/cost-display.mjs";
import { projectAccessAllowed } from "../lib/project-access-policy.mjs";
import {
  deterministicFindings,
  literalReplace,
  makePrivacyPlan,
} from "../lib/privacy-review-core.mjs";
const load = (path, deps, names) =>
  new Function(
    ...Object.keys(deps),
    readFileSync(new URL(path, import.meta.url), "utf8")
      .replace(/^import\s[\s\S]*?from\s+["'][^"']+["'];\s*/gm, "")
      .replace(/^export\s+/gm, "") + `\nreturn {${names.join(",")}};`,
  )(...Object.values(deps));
test("skill documents validate frontmatter, parameters and exact non-recursive interpolation", () => {
  const skill = skillDocument({
    document:
      '---\nname: Fixture skill\nparameters: {"tone":{"type":"string","default":"concise"}}\n---\nUse a {{tone}} style. Keep facts grounded.',
  });
  assert.equal(renderSkill(skill), "Use a concise style. Keep facts grounded.");
  assert.equal(
    renderSkill(skill, { tone: "{{secret}}" }),
    "Use a {{secret}} style. Keep facts grounded.",
  );
  for (const input of [
    { document: "---\nexecute: malicious\n---\nDo something with facts." },
    {
      name: "Fixture",
      instructions: "Summarize all relevant facts.",
      parameters: { x: { type: "object", default: {} } },
    },
    {
      name: "Fixture",
      instructions: "Summarize all relevant facts.",
      parameters: JSON.parse('{"__proto__":{"type":"string","default":"x"}}'),
    },
  ])
    assert.throws(() => skillDocument(input));
  assert.throws(() => renderSkill(skill, { unknown: "value" }));
});
test("live privacy preview uses offsets without returning secret values in metadata", () => {
  const text =
    'Write to fixture@example.invalid. Password: "Synthetic phrase!"';
  const plan = makePrivacyPlan(text, deterministicFindings(text));
  const ranges = previewRanges(text, plan.selected);
  assert.ok(!JSON.stringify(ranges).includes("Synthetic phrase!"));
  const ids = plan.selected
    .filter((m) => m.type === "PASSWORD")
    .map((m) => m.placeholder);
  const preview = previewSegments(text, ranges, ids)
    .map((p) => p.text)
    .join("");
  assert.ok(preview.includes("fixture@example.invalid"));
  assert.ok(!preview.includes("Synthetic phrase!"));
  assert.match(preview, /PASSWORD_1/);
});
test("read-only role cannot edit even its own project and role policies fail closed on empty lists", () => {
  const session = {
    role: "readonly",
    userId: "reader",
    features: { projects: true },
  };
  assert.equal(
    projectAccessAllowed({ session, projectOwnerId: "reader", action: "read" }),
    true,
  );
  assert.equal(
    projectAccessAllowed({
      session,
      projectOwnerId: "reader",
      action: "write",
    }),
    false,
  );
  assert.equal(
    projectAccessAllowed({
      session,
      projectOwnerId: "other",
      membershipRole: "editor",
      action: "manage",
    }),
    false,
  );
  assert.equal(
    roleAllows(normalizeRolePolicy({ models: [] }), "models", "openai/fixture"),
    false,
  );
  assert.equal(
    roleAllows(normalizeRolePolicy({}), "tools", "project_search"),
    true,
  );
  assert.deepEqual(normalizeRolePolicy({ models: null, tools: null }), {
    models: null,
    tools: null,
  });
  assert.throws(() => normalizeRolePolicy({ tools: "all" }));
});
test("readonly API mutation returns before parsing or database side effects", async () => {
  for (const path of [
    "../app/api/chat/route.js",
    "../app/api/projects/route.js",
    "../app/api/projects/[id]/tasks/route.js",
  ]) {
    const api = load(
      path,
      {
        getSession: async () => ({ userId: "reader", role: "readonly" }),
        selectedChatSkillContext: async () => "",
      },
      ["POST"],
    );
    const response = await api.POST({
      json: () => {
        throw Error("must not parse");
      },
    });
    assert.equal(response.status, 403);
  }
});
test("execution-time model and tool policies block before provider or host effects", async () => {
  let role = "member",
    policy = { models: [], tools: [] };
  const api = load(
    "../lib/access-controls.js",
    {
      crypto,
      initializeDatabase: async () => {},
      normalizeRolePolicy,
      roleAllows,
      ROLES: ["owner", "admin", "member", "readonly"],
      db: {
        query: async (sql) => ({
          rows: sql.includes("SELECT u.id")
            ? [{ id: "u", role, enabled: true, policy }]
            : [],
        }),
      },
    },
    ["assertModelAccess", "assertToolAccess"],
  );
  await assert.rejects(
    api.assertModelAccess({
      requestingUserId: "u",
      provider: "openai",
      model: "fixture",
    }),
    { code: "MODEL_POLICY_DENIED" },
  );
  await assert.rejects(api.assertToolAccess("u", "sandbox_run"), {
    code: "TOOL_POLICY_DENIED",
  });
  role = "readonly";
  await assert.rejects(api.assertToolAccess("u", "project_read_file"), {
    code: "EXECUTION_FORBIDDEN",
  });
  role = "owner";
  await api.assertModelAccess({
    requestingUserId: "u",
    provider: "openai",
    model: "fixture",
  });
});
test("tool approval binds exact arguments and consumes a grant only once", async () => {
  let approved = false,
    consumed = false,
    created = 0;
  let savedHash;
  const db = {
    connect: async () => ({
      release() {},
      query: async (sql, args) => {
        if (sql.includes("SELECT decision"))
          return { rows: [{ decision: "ASK" }] };
        if (sql.startsWith("UPDATE approvals SET consumed_at")) {
          if (approved && !consumed && args[0] === savedHash) {
            consumed = true;
            return { rowCount: 1, rows: [{ id: "grant" }] };
          }
          return { rowCount: 0, rows: [] };
        }
        if (sql.includes("COUNT(*)::int")) return { rows: [{ n: 0 }] };
        if (sql.startsWith("SELECT id FROM approvals"))
          return { rows: created && !consumed ? [{ id: "pending" }] : [] };
        if (sql.startsWith("INSERT INTO approvals")) {
          created++;
          savedHash = args[5];
        }
        return { rows: [], rowCount: 0 };
      },
    }),
  };
  const { toolApproval } = load(
    "../lib/tool-approvals.js",
    {
      crypto,
      db,
      initializeDatabase: async () => {},
      deterministicFindings,
      literalReplace,
      makePrivacyPlan,
    },
    ["toolApproval"],
  );
  const input = {
    userId: "u",
    projectId: "p",
    name: "network_scan",
    args: { target: "owned.example", profile: "web" },
  };
  assert.equal((await toolApproval(input)).error, "APPROVAL_REQUIRED");
  assert.equal(created, 1);
  await toolApproval(input);
  assert.equal(created, 1);
  approved = true;
  assert.equal(await toolApproval(input), null);
  assert.equal(consumed, true);
  assert.equal(
    (
      await toolApproval({
        ...input,
        args: { target: "other.example", profile: "web" },
      })
    ).error,
    "APPROVAL_REQUIRED",
  );
});
test("chat cost labels distinguish estimates, unknown charges and local execution", () => {
  assert.equal(callCostLabel(0, "incomplete"), "Cost unknown");
  assert.match(callCostLabel(0.001, "estimated"), /^≈ /);
  assert.equal(callCostLabel(0.001, "reported"), "< CHF 0.01");
  assert.equal(callCostLabel(0, "local-no-api"), "Local · no API fee");
});
