import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = path => readFileSync(new URL(path, import.meta.url), "utf8");

const guarded = [
  ["../app/api/projects/[id]/route.js", ["canManageProject"]],
  ["../app/api/projects/[id]/files/route.js", ["canAccessProject", "canEditProject"]],
  ["../app/api/projects/[id]/files/create/route.js", ["canEditProject"]],
  ["../app/api/projects/[id]/tasks/route.js", ["canAccessProject", "canEditProject"]],
  ["../app/api/projects/[id]/tools/test/route.js", ["canEditProject"]],
  ["../app/api/projects/[id]/conversations/route.js", ["canAccessProject"]],
  ["../app/api/projects/[id]/conversations/[conversationId]/route.js", ["canAccessProject"]],
  ["../app/api/files/[id]/content/route.js", ["canAccessProject", "canEditProject"]],
  ["../app/api/files/[id]/route.js", ["canEditProject"]],
  ["../app/api/files/[id]/preview/route.js", ["canAccessProject"]],
  ["../app/api/files/[id]/raw/route.js", ["canAccessProject"]],
  ["../app/api/tasks/[id]/route.js", ["canEditProject"]],
  ["../app/projects/[id]/page.js", ["canAccessProject"]],
];
for (const [path, guards] of guarded) {
  test(`resource authorization guards exist in ${path}`, () => {
    const src = read(path);
    for (const guard of guards) {
      assert.match(src, new RegExp(`await ${guard}\\(`));
    }
  });
}
test("project listing filters membership and creation sets owner", () => {
  const route = read("../app/api/projects/route.js");
  const page = read("../app/projects/page.js");
  assert.match(route, /EXISTS\s*\(\s*SELECT 1 FROM project_members/);
  assert.match(page, /EXISTS\s*\(\s*SELECT 1 FROM project_members/);
  assert.match(route, /owner_user_id/);
  assert.match(route, /session\.userId/);
  assert.match(page, /requireFeature\("projects"\)/);
});
test("host snapshot enforces server feature", () => {
  const route = read("../app/api/server/snapshot/route.js");
  assert.match(route, /!hasFeature\(session, "server"\)/);
});


test("every project permission reference is imported from the identity module", () => {
  for (const [path] of guarded) {
    if (!path.includes("/api/")) continue;
    const src = read(path);
    const declaration = src.match(
      /import\s*\{([^}]+)\}\s*from\s*["'][^"']+\/lib\/identity["']/
    );
    assert.ok(declaration, `identity import missing in ${path}`);
    const exported = declaration[1]
      .split(",")
      .map(token => token.trim());
    const invoked = new Set(
      src.match(/\bcan(?:Access|Edit|Manage)Project(?=\s*\()/g) || []
    );
    for (const name of invoked) {
      assert.ok(exported.includes(name), `${path}: ${name} not imported`);
    }
  }
});
