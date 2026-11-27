import net, { isIP } from "node:net";
import tls from "node:tls";
import http from "node:http";
import https from "node:https";
import crypto from "node:crypto";
const printable = (value, max = 180) =>
  String(value || "")
    .replace(/[\u0000-\u001f\u007f-\u009f]/g, " ")
    .slice(0, max);
const hash = (value) => crypto.createHash("sha256").update(value).digest("hex");
export function tcpProbe(address, port, { signal, timeout = 1200 } = {}) {
  return new Promise((resolve) => {
    let done = false,
      banner = "";
    const started = performance.now();
    let bannerTimer;
    const socket = net.createConnection({ host: address, port, signal });
    const finish = (state) => {
      if (done) return;
      done = true;
      clearTimeout(bannerTimer);
      socket.destroy();
      resolve({
        address,
        port,
        state,
        latencyMs: Math.round(performance.now() - started),
        banner: printable(banner),
      });
    };
    socket.setTimeout(timeout, () => finish("filtered"));
    socket.on("connect", () => {
      bannerTimer = setTimeout(() => finish("open"), 180);
    });
    socket.on("data", (chunk) => {
      banner += chunk.toString("utf8");
      finish("open");
    });
    socket.on("error", (error) =>
      finish(error.code === "ECONNREFUSED" ? "closed" : "filtered"),
    );
    socket.on("close", () => {
      if (!done) finish("filtered");
    });
  });
}
export function tlsProbe(address, port, host, { signal, timeout = 2500 } = {}) {
  return new Promise((resolve) => {
    let done = false;
    const socket = tls.connect({
      host: address,
      port,
      servername: isIP(host) ? undefined : host,
      rejectUnauthorized: false,
      signal,
    });
    const finish = (result) => {
      if (done) return;
      done = true;
      socket.destroy();
      resolve(result);
    };
    socket.setTimeout(timeout, () => finish({ error: "TLS_TIMEOUT" }));
    socket.on("error", () => finish({ error: "TLS_HANDSHAKE_FAILED" }));
    socket.on("close", () => finish({ error: "TLS_HANDSHAKE_FAILED" }));
    socket.on("secureConnect", () => {
      const cert = socket.getPeerCertificate();
      const identity = tls.checkServerIdentity(host, cert);
      const validTo = Date.parse(cert.valid_to);
      finish({
        protocol: socket.getProtocol(),
        cipher: socket.getCipher()?.name,
        verified: socket.authorized && !identity,
        validationError: printable(
          identity?.code || socket.authorizationError || "",
        ),
        issuer: printable(cert.issuer?.CN),
        subject: printable(cert.subject?.CN),
        validTo: Number.isFinite(validTo)
          ? new Date(validTo).toISOString()
          : null,
        daysRemaining: Number.isFinite(validTo)
          ? Math.floor((validTo - Date.now()) / 86400000)
          : null,
        fingerprint: cert.fingerprint256 || null,
      });
    });
  });
}
export function httpProbe(
  address,
  port,
  host,
  secure,
  path = "/",
  { signal, timeout = 2500 } = {},
) {
  return new Promise((resolve) => {
    let done = false;
    const chunks = [];
    let bytes = 0;
    const request = (secure ? https : http).request(
      {
        hostname: address,
        port,
        path,
        method: "GET",
        servername: isIP(host) ? undefined : host,
        rejectUnauthorized: false,
        agent: false,
        signal,
        maxHeaderSize: 16384,
        headers: {
          Host: (isIP(host) === 6 ? `[${host}]` : host) + ":" + port,
          "User-Agent": "Vector-Owned-Asset-Scanner/1",
          "Accept-Encoding": "identity",
          Accept: "text/plain,text/html,application/json",
        },
      },
      (response) => {
        const finish = (truncated = false) => {
          if (done) return;
          done = true;
          const headers = {};
          for (const name of [
            "content-type",
            "server",
            "x-powered-by",
            "strict-transport-security",
            "content-security-policy",
            "x-frame-options",
            "x-content-type-options",
            "referrer-policy",
            "permissions-policy",
          ])
            if (response.headers[name])
              headers[name] = printable(response.headers[name], 500);
          let redirect = null;
          try {
            if (!response.headers.location) throw Error();
            const url = new URL(
              response.headers.location,
              `${secure ? "https" : "http"}://${host}:${port}`,
            );
            if (["http:", "https:"].includes(url.protocol))
              redirect = url.origin + url.pathname;
          } catch {}
          resolve({
            status: response.statusCode,
            headers,
            body: Buffer.concat(chunks).toString("utf8"),
            truncated,
            redirect,
          });
          response.destroy();
          request.destroy();
        };
        response.on("data", (chunk) => {
          const remaining = 65536 - bytes;
          if (remaining > 0) chunks.push(chunk.subarray(0, remaining));
          bytes += chunk.length;
          if (bytes >= 65536) finish(true);
        });
        response.on("end", () => finish());
        response.on("error", () => finish(true));
        response.on("aborted", () => finish(true));
        response.on("close", () => finish(true));
      },
    );
    request.setTimeout(timeout, () => request.destroy(Error("timeout")));
    request.on("error", () => {
      if (!done) {
        done = true;
        resolve({ error: "HTTP_UNAVAILABLE" });
      }
    });
    request.end();
  });
}
export function varInt(number) {
  let value = number >>> 0,
    bytes = [];
  do {
    let byte = value & 127;
    value >>>= 7;
    if (value) byte |= 128;
    bytes.push(byte);
  } while (value);
  return Buffer.from(bytes);
}
function readVarInt(buffer, offset = 0) {
  let result = 0;
  for (let i = 0; i < 5; i++) {
    if (offset + i >= buffer.length) return null;
    const byte = buffer[offset + i];
    result += (byte & 127) * 2 ** (7 * i);
    if (!(byte & 128)) return { value: result, bytes: i + 1 };
  }
  throw Error("Invalid packet");
}
export function parseMinecraftStatus(buffer) {
  const frame = readVarInt(buffer);
  if (!frame) return null;
  if (frame.value > 65536) throw Error("Oversized packet");
  if (buffer.length < frame.bytes + frame.value) return null;
  const packet = buffer.subarray(frame.bytes, frame.bytes + frame.value);
  const id = readVarInt(packet);
  if (id?.value !== 0) throw Error("Invalid packet");
  const size = readVarInt(packet, id.bytes);
  if (
    !size ||
    size.value > 32767 ||
    id.bytes + size.bytes + size.value !== packet.length
  )
    throw Error("Invalid status");
  const data = JSON.parse(
    packet.subarray(id.bytes + size.bytes).toString("utf8"),
  );
  const plain = (value, depth = 0) =>
    depth > 8
      ? ""
      : typeof value === "string"
        ? value
        : Array.isArray(value)
          ? value
              .slice(0, 50)
              .map((v) => plain(v, depth + 1))
              .join("")
          : value && typeof value === "object"
            ? plain(value.text || "", depth + 1) +
              plain(value.extra || [], depth + 1)
            : "";
  const count = (value) =>
    Number.isSafeInteger(value) && value >= 0 ? value : null;
  return {
    version: printable(data.version?.name),
    protocol: count(data.version?.protocol),
    motd: printable(plain(data.description).replace(/§./g, ""), 300),
    playersOnline: count(data.players?.online),
    playersMax: count(data.players?.max),
    onlineMode: null,
    authentication: "Not exposed by the public status protocol",
  };
}
export function minecraftProbe(
  address,
  port,
  host,
  { signal, timeout = 2500 } = {},
) {
  return new Promise((resolve) => {
    let done = false,
      buffer = Buffer.alloc(0);
    const socket = net.createConnection({ host: address, port, signal });
    const finish = (result) => {
      if (done) return;
      done = true;
      socket.destroy();
      resolve(result);
    };
    socket.setTimeout(timeout, () => finish({ error: "MINECRAFT_TIMEOUT" }));
    socket.on("error", () => finish({ error: "MINECRAFT_UNAVAILABLE" }));
    socket.on("close", () => finish({ error: "MINECRAFT_UNAVAILABLE" }));
    socket.on("connect", () => {
      const name = Buffer.from(host);
      const p = Buffer.alloc(2);
      p.writeUInt16BE(port);
      const handshake = Buffer.concat([
        varInt(0),
        varInt(-1),
        varInt(name.length),
        name,
        p,
        varInt(1),
      ]);
      socket.write(
        Buffer.concat([
          varInt(handshake.length),
          handshake,
          Buffer.from([1, 0]),
        ]),
      );
    });
    socket.on("data", (chunk) => {
      buffer = Buffer.concat([buffer, chunk]);
      if (buffer.length > 65542)
        return finish({ error: "MINECRAFT_INVALID_STATUS" });
      try {
        const value = parseMinecraftStatus(buffer);
        if (value) finish(value);
      } catch {
        finish({ error: "MINECRAFT_INVALID_STATUS" });
      }
    });
  });
}
export async function webAudit(address, port, host, secure, options = {}) {
  const home = await httpProbe(address, port, host, secure, "/", options);
  const checks = [],
    findings = [];
  const finding = (id, severity, title, evidence, remediation) =>
    findings.push({
      id,
      severity,
      title,
      evidence,
      remediation,
      confidence: "observed",
    });
  const tlsResult = secure
    ? await tlsProbe(address, port, host, options)
    : null;
  if (tlsResult && !tlsResult.error) {
    if (!tlsResult.verified)
      finding(
        "tls-certificate",
        "medium",
        "Certificate validation failed",
        tlsResult.validationError,
        "Install a trusted certificate covering this hostname and verify its full chain.",
      );
    if (tlsResult.daysRemaining !== null && tlsResult.daysRemaining < 0)
      finding(
        "tls-expired",
        "high",
        "TLS certificate expired",
        tlsResult.validTo,
        "Renew and deploy the certificate, then verify the served chain.",
      );
    else if (tlsResult.daysRemaining !== null && tlsResult.daysRemaining < 15)
      finding(
        "tls-expiring",
        "low",
        "TLS certificate expires soon",
        tlsResult.validTo,
        "Renew the certificate before its expiry.",
      );
    if (!["TLSv1.2", "TLSv1.3"].includes(tlsResult.protocol))
      finding(
        "tls-version",
        "medium",
        "Legacy TLS negotiated",
        tlsResult.protocol,
        "Disable legacy TLS after checking client compatibility.",
      );
  }
  if (!home.error) {
    for (const [header, title] of [
      ["content-security-policy", "Content Security Policy"],
      ["x-frame-options", "Frame protection"],
      ["x-content-type-options", "Content type protection"],
      ...(secure ? [["strict-transport-security", "HSTS"]] : []),
    ]) {
      const cspFrames =
        header === "x-frame-options" &&
        /frame-ancestors/i.test(home.headers["content-security-policy"] || "");
      if (!home.headers[header] && !cspFrames)
        finding(
          "header-" + header,
          "low",
          title + " header not observed",
          `GET / returned ${home.status}`,
          "Review applicability and configure " +
            header +
            " for this application.",
        );
    }
    for (const path of ["/.env", "/.git/HEAD", "/robots.txt", "/admin"]) {
      if (options.signal?.aborted) break;
      const response = await httpProbe(
        address,
        port,
        host,
        secure,
        path,
        options,
      );
      const same =
        typeof response.body === "string" &&
        hash(response.body) === hash(home.body || "");
      let exposed = false;
      if (response.status === 200 && !same) {
        if (path === "/.env")
          exposed =
            !/^\s*(?:<!doctype|<html)/i.test(response.body) &&
            (/^(?:APP_KEY|DATABASE_URL|DB_PASSWORD|AWS_SECRET_ACCESS_KEY|API_KEY|SECRET_KEY)\s*=/m.test(
              response.body,
            ) ||
              (response.body.match(/^[A-Z][A-Z0-9_]{2,}\s*=/gm) || []).length >=
                2);
        if (path === "/.git/HEAD")
          exposed = /^(?:ref: refs\/[\w/.-]+|[a-f0-9]{40})\s*$/.test(
            response.body.trim(),
          );
        if (exposed)
          finding(
            "exposed-" + path,
            "high",
            "Sensitive file publicly readable",
            `GET ${path} matched ${path === "/.env" ? "environment assignments" : "Git HEAD format"}. Contents were discarded.`,
            "Deny access to this path, remove it from public deployment and rotate any exposed credentials.",
          );
        if (
          path === "/robots.txt" &&
          /^\s*(?:User-agent|Disallow|Allow):/im.test(response.body)
        )
          finding(
            "robots",
            "info",
            "Crawler rules published",
            "robots.txt is accessible.",
            "Review listed paths; robots.txt is not access control.",
          );
        if (path === "/admin")
          finding(
            "admin",
            "info",
            "Administrative route responds",
            "GET /admin returned HTTP 200. Authentication was not tested.",
            "Verify authorization and MFA; a responding login page alone is not a vulnerability.",
          );
      }
      checks.push({
        path,
        status: response.status || null,
        error: response.error || null,
        exposed,
      });
    }
  }
  return {
    address,
    port,
    scheme: secure ? "https" : "http",
    status: home.status || null,
    error: home.error || null,
    headers: home.headers || {},
    redirect: home.redirect || null,
    tls: tlsResult,
    checks,
    findings,
  };
}
