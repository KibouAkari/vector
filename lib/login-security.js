import crypto
  from "node:crypto";


import {
  db
} from "./db";


/*
 * VECTOR_LOGIN_SECURITY_584C1
 *
 * Fixed-window protection stored in PostgreSQL.
 *
 * No raw username or client IP is persisted.
 * Buckets are HMAC-derived using VECTOR_SECRET.
 */


const WINDOW_SECONDS =
  15 * 60;


const USER_LIMIT =
  8;


const IP_LIMIT =
  30;


const UNKNOWN_IP_LIMIT =
  100;


let initialized =
  false;


function secret() {
  const value =
    process.env.VECTOR_SECRET;


  if (!value) {
    throw new Error(
      "VECTOR_SECRET missing"
    );
  }


  return value;
}


function bucket(
  type,
  value
) {
  const digest =
    crypto
      .createHmac(
        "sha256",
        secret()
      )
      .update(
        `${type}:${String(value || "")}`
      )
      .digest(
        "hex"
      );


  return `${type}:${digest}`;
}


function clientIp(
  request
) {
  const forwarded =
    request.headers.get(
      "x-forwarded-for"
    );


  const value =
    request.headers.get(
      "cf-connecting-ip"
    ) ||
    request.headers.get(
      "x-real-ip"
    ) ||
    (
      forwarded
        ? forwarded
            .split(",")[0]
            .trim()
        : ""
    ) ||
    "unknown";


  return String(
    value
  )
    .trim()
    .slice(
      0,
      128
    ) ||
    "unknown";
}


async function ensureTable() {
  if (
    initialized
  ) {
    return;
  }


  await db.query(`
    CREATE TABLE IF NOT EXISTS
      vector_login_rate_limits
    (
      bucket
        TEXT
        PRIMARY KEY,

      attempt_count
        INTEGER
        NOT NULL
        DEFAULT 0,

      window_started_at
        TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW(),

      updated_at
        TIMESTAMPTZ
        NOT NULL
        DEFAULT NOW()
    )
  `);


  initialized =
    true;
}


async function bucketState(
  key,
  limit
) {
  const result =
    await db.query(
      `
        SELECT
          attempt_count,

          GREATEST(
            0,
            CEIL(
              EXTRACT(
                EPOCH FROM (
                  window_started_at
                  + INTERVAL '15 minutes'
                  - NOW()
                )
              )
            )
          )::int
            AS retry_after

        FROM vector_login_rate_limits

        WHERE
          bucket = $1
          AND window_started_at >
            NOW()
            - INTERVAL '15 minutes'
      `,
      [
        key
      ]
    );


  if (
    result.rowCount === 0
  ) {
    return {
      blocked:
        false,

      retryAfter:
        0
    };
  }


  const row =
    result.rows[0];


  const attempts =
    Number(
      row.attempt_count ||
      0
    );


  return {
    blocked:
      attempts >=
      limit,

    retryAfter:
      Number(
        row.retry_after ||
        1
      )
  };
}


async function increment(
  key
) {
  await db.query(
    `
      INSERT INTO
        vector_login_rate_limits
      (
        bucket,
        attempt_count,
        window_started_at,
        updated_at
      )

      VALUES
      (
        $1,
        1,
        NOW(),
        NOW()
      )

      ON CONFLICT
        (bucket)

      DO UPDATE SET

        attempt_count =
          CASE

            WHEN
              vector_login_rate_limits
                .window_started_at
              <=
              NOW()
              - INTERVAL '15 minutes'

            THEN
              1

            ELSE
              vector_login_rate_limits
                .attempt_count
              + 1

          END,

        window_started_at =
          CASE

            WHEN
              vector_login_rate_limits
                .window_started_at
              <=
              NOW()
              - INTERVAL '15 minutes'

            THEN
              NOW()

            ELSE
              vector_login_rate_limits
                .window_started_at

          END,

        updated_at =
          NOW()
    `,
    [
      key
    ]
  );
}


export function loginRequestAllowed(
  request
) {
  const fetchSite =
    request.headers.get(
      "sec-fetch-site"
    );


  if (
    fetchSite ===
    "cross-site"
  ) {
    return false;
  }


  const origin =
    request.headers.get(
      "origin"
    );


  /*
   * Non-browser/API clients may legitimately omit Origin.
   * Browser requests with Origin must match the effective host.
   */
  if (
    !origin
  ) {
    return true;
  }


  try {
    const parsed =
      new URL(
        origin
      );


    const host =
      request.headers.get(
        "host"
      );


    const forwardedHost =
      request.headers
        .get(
          "x-forwarded-host"
        )
        ?.split(",")[0]
        ?.trim();


    const allowedHosts =
      new Set(
        [
          host,
          forwardedHost
        ]
          .filter(
            Boolean
          )
      );


    return (
      allowedHosts.has(
        parsed.host
      ) &&
      (
        parsed.protocol ===
          "https:" ||
        process.env.NODE_ENV !==
          "production"
      )
    );

  } catch {
    return false;
  }
}


export async function checkLoginRateLimit({
  request,
  username
}) {
  await ensureTable();


  /*
   * Opportunistic bounded cleanup.
   */
  await db.query(`
    DELETE FROM
      vector_login_rate_limits

    WHERE
      updated_at <
      NOW()
      - INTERVAL '2 days'
  `);


  const ip =
    clientIp(
      request
    );


  const userKey =
    bucket(
      "user",
      String(
        username ||
        "<empty>"
      )
        .trim()
        .toLowerCase()
    );


  const ipKey =
    bucket(
      "ip",
      ip
    );


  const [
    userState,
    ipState
  ] =
    await Promise.all([
      bucketState(
        userKey,
        USER_LIMIT
      ),

      bucketState(
        ipKey,
        ip === "unknown"
          ? UNKNOWN_IP_LIMIT
          : IP_LIMIT
      )
    ]);


  return {
    blocked:
      userState.blocked ||
      ipState.blocked,

    retryAfter:
      Math.max(
        userState.retryAfter,
        ipState.retryAfter,
        1
      ),

    userKey,
    ipKey
  };
}


export async function recordLoginFailure({
  userKey,
  ipKey
}) {
  await ensureTable();


  await Promise.all([
    increment(
      userKey
    ),

    increment(
      ipKey
    )
  ]);
}


export async function recordLoginSuccess({
  userKey
}) {
  await ensureTable();


  /*
   * A successful authentication clears only the account bucket.
   *
   * The IP bucket remains so one source cannot brute-force
   * multiple accounts and reset itself with one valid login.
   */
  await db.query(
    `
      DELETE FROM
        vector_login_rate_limits

      WHERE
        bucket = $1
    `,
    [
      userKey
    ]
  );
}


export const LOGIN_RATE_WINDOW_SECONDS =
  WINDOW_SECONDS;
