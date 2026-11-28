import https from "node:https";
import http from "node:http";
import { isIP } from "node:net";
import { resolveTarget } from "../security/targets.mjs";
import { pinnedLookup } from "../source-fetch.mjs";
export function connectionUrl(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw Error("INVALID_CONNECTION_URL");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.href.length > 500
  )
    throw Error("INVALID_CONNECTION_URL");
  url.pathname = url.pathname.replace(/\/$/, "");
  return url;
}
export async function connectionAddresses(url) {
  const cidrs = (process.env.VECTOR_CONNECTOR_PRIVATE_CIDRS || "")
    .split(",")
    .filter(Boolean);
  const addresses = await resolveTarget(
    { host: url.hostname.replace(/^\[|\]$/g, "") },
    { privateCidrs: cidrs },
  );
  if (
    url.protocol !== "https:" &&
    !(
      process.env.VECTOR_CONNECTOR_ALLOW_PRIVATE_HTTP === "true" &&
      addresses.every((ip) =>
        /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(ip),
      )
    )
  )
    throw Error("HTTPS_REQUIRED");
  return addresses;
}
export async function connectorRequest(
  base,
  path,
  {
    method = "GET",
    headers = {},
    body,
    addresses,
    raw = false,
    requestImpl,
  } = {},
) {
  const origin = connectionUrl(base),
    url = new URL(
      origin.href.replace(/\/$/, "") + "/" + String(path).replace(/^\//, ""),
    );
  if (
    url.origin !== origin.origin ||
    !url.pathname.startsWith(origin.pathname.replace(/\/$/, "") + "/")
  )
    throw Error("CONNECTION_PATH_BLOCKED");
  const current = await connectionAddresses(url);
  if (addresses && JSON.stringify(current) !== JSON.stringify(addresses))
    throw Error("CONNECTION_DNS_CHANGED");
  const destination = { address: current[0], family: isIP(current[0]) };
  return await new Promise((resolve, reject) => {
    const signal = AbortSignal.timeout(8000);
    const req = (
      requestImpl || (url.protocol === "https:" ? https : http).request
    )(
      url,
      {
        method,
        headers: {
          Accept: "application/json",
          "Accept-Encoding": "identity",
          "User-Agent": "VectorConnections/1.0",
          ...headers,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        lookup: pinnedLookup(destination),
        agent: false,
        signal,
        maxHeaderSize: 16384,
      },
      (res) => {
        let bytes = 0;
        const parts = [];
        if (
          res.statusCode < 200 ||
          res.statusCode >= 300 ||
          (res.headers["content-encoding"] &&
            res.headers["content-encoding"] !== "identity")
        ) {
          res.destroy();
          reject(
            Object.assign(Error("CONNECTOR_HTTP_" + res.statusCode), {
              status: res.statusCode,
            }),
          );
          return;
        }
        res.on("data", (chunk) => {
          bytes += chunk.length;
          if (bytes > 1024 * 1024) {
            res.destroy();
            reject(Error("CONNECTOR_RESPONSE_LIMIT"));
          } else parts.push(chunk);
        });
        res.on("error", reject);
        res.on("aborted", () => reject(Error("CONNECTOR_RESPONSE_ABORTED")));
        res.on("end", () => {
          try {
            const text = Buffer.concat(parts).toString("utf8");
            resolve(raw ? text : JSON.parse(text));
          } catch {
            reject(Error("CONNECTOR_INVALID_JSON"));
          }
        });
      },
    );
    req.on("error", reject);
    req.end(body ? JSON.stringify(body) : undefined);
  });
}
