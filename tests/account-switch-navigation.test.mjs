import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = path =>
  readFileSync(new URL(path, import.meta.url), "utf8");

test("login discards client-side account cache", () => {
  const login = source("../app/login/login-form.js");
  assert.match(login, /window\.location\.replace\(["']\/["']\)/);
  assert.doesNotMatch(login, /router\.(replace|refresh|push)\(/);
});

test("logout waits for cookie revocation before discarding UI", () => {
  const logout = source("../components/logout-button.js");
  assert.match(logout, /response\.ok/);
  assert.match(logout, /window\.location\.replace\(["']\/login["']\)/);
  assert.doesNotMatch(logout, /router\.(replace|refresh|push)\(/);
});

test("server-side authentication is still required", () => {
  const auth = source("../lib/auth.js");
  assert.match(auth, /await cookies\(\)/);
  assert.match(auth, /getUserById/);
  assert.match(auth, /publicUser\(user\)/);
});
