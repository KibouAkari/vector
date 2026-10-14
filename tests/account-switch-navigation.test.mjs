import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  revokeSessionAndNavigate
} from "../lib/logout-navigation.mjs";

const source = path =>
  readFileSync(new URL(path, import.meta.url), "utf8");

test("login discards client-side account cache", () => {
  const login = source("../app/login/login-form.js");
  assert.match(login, /window\.location\.replace\(["']\/["']\)/);
  assert.doesNotMatch(login, /router\.(replace|refresh|push)\(/);
});

test("logout navigation waits for a successful server response", async () => {
  let completeRequest;
  const response = new Promise(resolve => {
    completeRequest = resolve;
  });
  const navigations = [];
  let requestOptions;

  const operation = revokeSessionAndNavigate({
    request: (path, options) => {
      assert.equal(path, "/api/auth/logout");
      requestOptions = options;
      return response;
    },
    navigate: destination => navigations.push(destination)
  });

  assert.deepEqual(navigations, [], "must wait for server acknowledgement");
  assert.equal(requestOptions.method, "POST");
  assert.equal(requestOptions.credentials, "same-origin");
  assert.equal(requestOptions.cache, "no-store");

  completeRequest({ ok: true, status: 200 });
  await operation;

  assert.deepEqual(navigations, ["/login"]);
});

test("failed logout response must not navigate", async () => {
  const navigations = [];
  await assert.rejects(
    revokeSessionAndNavigate({
      request: async () => ({ ok: false, status: 500 }),
      navigate: destination => navigations.push(destination)
    }),
    /not confirmed/
  );
  assert.deepEqual(navigations, []);
});

test("logout network error must not navigate", async () => {
  const navigations = [];
  await assert.rejects(
    revokeSessionAndNavigate({
      request: async () => {
        throw new Error("network unavailable");
      },
      navigate: destination => navigations.push(destination)
    }),
    /network unavailable/
  );
  assert.deepEqual(navigations, []);
});

test("server-side authentication is still required", () => {
  const auth = source("../lib/auth.js");
  assert.match(auth, /await cookies\(\)/);
  assert.match(auth, /getUserById/);
  assert.match(auth, /publicUser\(user\)/);
});
