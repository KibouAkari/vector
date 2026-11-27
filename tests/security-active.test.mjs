import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import net from "node:net";
import {
  parseTarget,
  permittedAddress,
  resolveTarget,
} from "../lib/security/targets.mjs";
import {
  webAudit,
  tcpProbe,
  minecraftProbe,
  parseMinecraftStatus,
  varInt,
} from "../lib/security/probes.mjs";
import { runActiveScan, scanMarkdown } from "../lib/security/active-scan.mjs";
import {
  packageAdvisories,
  serviceAdvisories,
  serviceCpes,
} from "../lib/security/advisories.mjs";
const listen = (server) =>
  new Promise((resolve) =>
    server.listen(0, "127.0.0.1", () => resolve(server.address().port)),
  );
const close = (server) => new Promise((resolve) => server.close(resolve));
test("targets accept domains and explicit ports without credentials, shell syntax or metadata routes", async () => {
  assert.deepEqual(parseTarget("Example.com:80", [22]).ports, [22, 80]);
  assert.equal(parseTarget("https://example.com", [22]).explicitPort, 443);
  assert.equal(
    parseTarget("2001:4860:4860::8888", [443]).host,
    "2001:4860:4860::8888",
  );
  for (const value of [
    "https://user:secret@example.com",
    "example.com/path",
    "example.com;id",
    "https://example.com/?url=internal",
    "file:///etc/passwd",
    "example.com:70000",
  ])
    assert.throws(() => parseTarget(value));
  for (const ip of [
    "127.0.0.1",
    "169.254.169.254",
    "168.63.129.16",
    "100.100.100.200",
    "::1",
    "::ffff:127.0.0.1",
    "fd00:ec2::254",
    "2001::1",
    "2002:7f00:1::",
    "192.0.2.1",
    "3fff::1",
  ])
    assert.equal(
      permittedAddress(ip, ["0.0.0.0/8", "169.254.0.0/16"]),
      false,
      ip,
    );
  assert.equal(permittedAddress("192.168.1.2"), false);
  assert.equal(permittedAddress("192.168.1.2", ["192.168.1.0/24"]), true);
  assert.equal(permittedAddress("10.0.0.2", ["192.168.1.0/24"]), false);
  await assert.rejects(
    resolveTarget(parseTarget("example.com"), {
      lookupImpl: async () => [
        { address: "8.8.8.8" },
        { address: "127.0.0.1" },
      ],
    }),
    { code: "TARGET_ADDRESS_BLOCKED" },
  );
});
test("DNS changes abort the real scan pipeline before a socket is opened", async () => {
  let calls = 0;
  await assert.rejects(
    runActiveScan(
      { target: parseTarget("example.com", [443]), addresses: ["8.8.8.8"] },
      {
        resolve: async () => ["1.1.1.1"],
        tcp: async () => {
          calls++;
        },
      },
    ),
    { code: "TARGET_CHANGED_REAUTHORIZE" },
  );
  assert.equal(calls, 0);
});
test("TCP probes read a bounded passive banner on an isolated loopback fixture", async () => {
  const server = net.createServer((socket) =>
    socket.end("SSH-2.0-Fixture_1.0\r\n"),
  );
  const port = await listen(server);
  try {
    const result = await tcpProbe("127.0.0.1", port);
    assert.equal(result.state, "open");
    assert.match(result.banner, /SSH/);
    assert.ok(result.latencyMs >= 0);
  } finally {
    await close(server);
  }
});
test("web checks detect sensitive files but discard their contents and never follow a redirect", async () => {
  const paths = [];
  const server = http.createServer((req, res) => {
    paths.push(req.url);
    res.setHeader("set-cookie", "fixture-private-cookie");
    res.setHeader("server", "Fixture/1.0");
    if (req.url === "/.env")
      res.end("DATABASE_URL=fixture-private-value\nAPP_KEY=fixture-key-value");
    else if (req.url === "/.git/HEAD") res.end("ref: refs/heads/main\n");
    else if (req.url === "/robots.txt") {
      res.writeHead(302, {
        Location: "http://169.254.169.254/latest/meta-data/",
      });
      res.end();
    } else res.end("<html>Fixture login page</html>");
  });
  const port = await listen(server);
  try {
    const result = await webAudit("127.0.0.1", port, "fixture.invalid", false);
    assert.ok(result.findings.some((f) => f.id === "exposed-/.env"));
    assert.ok(result.findings.some((f) => f.id === "exposed-/.git/HEAD"));
    assert.equal(
      result.checks.find((c) => c.path === "/robots.txt").status,
      302,
    );
    assert.deepEqual(paths, [
      "/",
      "/.env",
      "/.git/HEAD",
      "/robots.txt",
      "/admin",
    ]);
    const serialized = JSON.stringify(result);
    for (const secret of [
      "fixture-private-value",
      "fixture-key-value",
      "fixture-private-cookie",
    ])
      assert.ok(!serialized.includes(secret));
    assert.equal(result.redirect, null);
  } finally {
    await close(server);
  }
});
test("Minecraft parser handles fragmented status while preserving unknown authentication", async () => {
  const value = {
    version: { name: "Fixture Java", protocol: 1 },
    players: { online: 3, max: 20, sample: [{ name: "must-not-be-retained" }] },
    description: { text: "Owned fixture" },
  };
  const json = Buffer.from(JSON.stringify(value));
  const body = Buffer.concat([varInt(0), varInt(json.length), json]);
  const frame = Buffer.concat([varInt(body.length), body]);
  assert.equal(parseMinecraftStatus(frame.subarray(0, 3)), null);
  const parsed = parseMinecraftStatus(frame);
  assert.equal(parsed.playersOnline, 3);
  assert.equal(parsed.onlineMode, null);
  assert.ok(!JSON.stringify(parsed).includes("must-not-be-retained"));
  assert.throws(() =>
    parseMinecraftStatus(Buffer.from([255, 255, 255, 255, 255])),
  );
  const server = net.createServer((socket) =>
    socket.once("data", () => socket.end(frame)),
  );
  const port = await listen(server);
  try {
    const status = await minecraftProbe("127.0.0.1", port, "fixture.invalid");
    assert.equal(status.version, "Fixture Java");
  } finally {
    await close(server);
  }
});
test("scan concurrency is bounded and incomplete advisory lookups cannot become a clean conclusion", async () => {
  let active = 0,
    peak = 0;
  const asset = {
    name: "Fixture",
    kind: "network",
    target: parseTarget(
      "example.com",
      Array.from({ length: 12 }, (_, i) => 10000 + i),
    ),
    addresses: ["8.8.8.8"],
    checkAdvisories: true,
    packages: [],
  };
  const result = await runActiveScan(asset, {
    resolve: async () => ["8.8.8.8"],
    tcp: async (address, port) => {
      active++;
      peak = Math.max(peak, active);
      await new Promise((resolve) => setTimeout(resolve, 2));
      active--;
      return { address, port, state: "closed", banner: "" };
    },
    osv: async () => ({
      findings: [],
      lookups: [{ source: "OSV", status: "unavailable" }],
    }),
    nvd: async () => ({ findings: [], lookups: [] }),
  });
  assert.ok(peak <= 4);
  assert.equal(result.coverage.portsAttempted, 12);
  assert.equal(result.advisories.status, "partial");
  assert.equal(result.findings.length, 0);
  assert.match(
    scanMarkdown(asset, result),
    /lookup failures are not a clean result/,
  );
});
test("advisories send only explicit package versions and report candidate confidence", async () => {
  const requests = [];
  const data = await packageAdvisories(
    [{ ecosystem: "npm", name: "fixture-package", version: "1.0.0" }],
    {
      fetchImpl: async (url, options) => {
        requests.push({ url, body: JSON.parse(options.body) });
        return Response.json({
          vulns: [
            {
              id: "GHSA-fixture",
              summary: "Fixture advisory",
              database_specific: { severity: "HIGH" },
              affected: [{ ranges: [{ events: [{ fixed: "1.0.1" }] }] }],
            },
          ],
        });
      },
    },
  );
  assert.equal(requests[0].url, "https://api.osv.dev/v1/query");
  assert.deepEqual(requests[0].body, {
    package: { name: "fixture-package", ecosystem: "npm" },
    version: "1.0.0",
  });
  assert.equal(data.findings[0].confidence, "version-match");
  assert.match(data.findings[0].remediation, /1.0.1/);
  const unknown = await packageAdvisories(
    [{ ecosystem: "npm", name: "fixture", version: "1" }],
    { fetchImpl: async () => Response.json({ unexpected: "body" }) },
  );
  assert.equal(unknown.lookups[0].status, "unavailable");
  const cpes = serviceCpes(
    [{ banner: "SSH-2.0-OpenSSH_9.0p1" }],
    [{ headers: { server: "nginx/1.26.3" } }],
  );
  assert.equal(cpes.length, 2);
  const nvd = await serviceAdvisories(cpes.slice(0, 1), {
    fetchImpl: async () =>
      Response.json({
        totalResults: 1,
        vulnerabilities: [
          {
            cve: {
              id: "CVE-2099-0001",
              descriptions: [{ lang: "en", value: "Synthetic advisory" }],
            },
          },
        ],
      }),
  });
  assert.equal(nvd.findings[0].confidence, "banner-version-match");
  assert.equal(nvd.findings[0].severity, "info");
});
