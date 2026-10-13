import test from "node:test";
import assert from "node:assert/strict";
import { projectAccessAllowed } from "../lib/project-access-policy.mjs";

const user = (projects = true) => ({
  userId: "alice",
  role: "member",
  features: { projects },
});
const check = (session, projectOwnerId, membershipRole, action) =>
  projectAccessAllowed({ session, projectOwnerId, membershipRole, action });

test("unauthenticated or feature-disabled users have no access", () => {
  for (const action of ["read", "write", "manage"]) {
    assert.equal(check(null, "alice", "editor", action), false);
    assert.equal(check(user(false), "alice", "editor", action), false);
  }
});
test("unrelated users cannot access another project", () => {
  for (const action of ["read", "write", "manage"]) {
    assert.equal(check(user(), "bob", null, action), false);
  }
});
test("viewer can read, never write or manage", () => {
  assert.equal(check(user(), "bob", "viewer", "read"), true);
  assert.equal(check(user(), "bob", "viewer", "write"), false);
  assert.equal(check(user(), "bob", "viewer", "manage"), false);
});
test("editor may edit files but cannot delete project", () => {
  assert.equal(check(user(), "bob", "editor", "read"), true);
  assert.equal(check(user(), "bob", "editor", "write"), true);
  assert.equal(check(user(), "bob", "editor", "manage"), false);
});
test("project owner controls own project", () => {
  for (const action of ["read", "write", "manage"]) {
    assert.equal(check(user(), "alice", null, action), true);
  }
});
test("platform owner can administer projects", () => {
  const root = { userId: "owner", role: "owner", features: {} };
  assert.equal(check(root, "alice", null, "manage"), true);
});
test("unknown role and action fail closed", () => {
  assert.equal(check(user(), "bob", "admin", "read"), false);
  assert.equal(check(user(), "bob", "editor", "erase",), false);
});
