import fs from "node:fs";
import http from "node:http";

const SOCKET_PATH =
  "/host/vector-host-agent.sock";

const TOKEN_PATH =
  "/run/secrets/vector-host-agent-token";


function token() {
  return fs
    .readFileSync(
      TOKEN_PATH,
      "utf8"
    )
    .trim();
}


function requestHost({
  path,
  method = "GET",
  body = null
}) {
  return new Promise(
    (
      resolve,
      reject
    ) => {
      const encoded =
        body === null
          ? null
          : Buffer.from(
              JSON.stringify(
                body
              ),
              "utf8"
            );

      const request =
        http.request(
          {
            socketPath:
              SOCKET_PATH,

            path,

            method,

            headers: {
              "X-Vector-Host-Token":
                token(),

              ...(encoded
                ? {
                    "Content-Type":
                      "application/json",

                    "Content-Length":
                      encoded.length
                  }
                : {})
            },

            timeout:
              15000
          },

          (
            response
          ) => {
            const chunks = [];

            response.on(
              "data",
              (
                chunk
              ) =>
                chunks.push(
                  chunk
                )
            );

            response.on(
              "end",
              () => {
                const raw =
                  Buffer
                    .concat(
                      chunks
                    )
                    .toString(
                      "utf8"
                    );

                let payload;

                try {
                  payload =
                    raw
                      ? JSON.parse(
                          raw
                        )
                      : {};
                } catch {
                  reject(
                    new Error(
                      `Host Agent returned invalid JSON: ${raw.slice(
                        0,
                        500
                      )}`
                    )
                  );

                  return;
                }

                if (
                  response.statusCode <
                    200 ||
                  response.statusCode >=
                    300 ||
                  payload.ok ===
                    false
                ) {
                  reject(
                    new Error(
                      payload.error ||
                      `Host Agent HTTP ${response.statusCode}`
                    )
                  );

                  return;
                }

                resolve(
                  payload.result ??
                  payload
                );
              }
            );
          }
        );

      request.on(
        "timeout",
        () => {
          request.destroy(
            new Error(
              "Host Agent request timed out."
            )
          );
        }
      );

      request.on(
        "error",
        reject
      );

      if (encoded) {
        request.write(
          encoded
        );
      }

      request.end();
    }
  );
}


export async function hostSnapshot() {
  return requestHost({
    path:
      "/snapshot"
  });
}


export async function hostInspect(
  input = {}
) {
  return requestHost({
    path:
      "/inspect",

    method:
      "POST",

    body:
      input
  });
}
