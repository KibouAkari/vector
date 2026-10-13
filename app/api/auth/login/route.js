import {
  authenticateUser,
  createSession,
  setSessionCookie
} from "../../../../lib/auth";


import {
  writeAudit
} from "../../../../lib/audit";


import {
  checkLoginRateLimit,
  loginRequestAllowed,
  recordLoginFailure,
  recordLoginSuccess
} from "../../../../lib/login-security";


export const runtime =
  "nodejs";


const MAX_BODY_BYTES =
  16 * 1024;


const MAX_USERNAME_LENGTH =
  128;


const MAX_PASSWORD_LENGTH =
  1024;


function denied(
  status,
  headers = undefined
) {
  return Response.json(
    {
      ok:
        false
    },
    {
      status,
      headers
    }
  );
}


export async function POST(
  request
) {
  try {

    /*
     * VECTOR_AUTH_HARDENING_584C1
     *
     * Reject browser requests coming from another site/origin.
     */
    if (
      !loginRequestAllowed(
        request
      )
    ) {
      return denied(
        403
      );
    }


    const contentLength =
      Number(
        request.headers.get(
          "content-length"
        ) ||
        0
      );


    if (
      Number.isFinite(
        contentLength
      ) &&
      contentLength >
        MAX_BODY_BYTES
    ) {
      return denied(
        413
      );
    }


    let body;


    try {
      body =
        await request.json();
    } catch {
      return denied(
        400
      );
    }


    const username =
      String(
        body?.username ||
        ""
      )
        .trim()
        .slice(
          0,
          MAX_USERNAME_LENGTH
        );


    const password =
      String(
        body?.password ||
        ""
      );


    if (
      password.length >
      MAX_PASSWORD_LENGTH
    ) {
      return denied(
        401
      );
    }


    const rate =
      await checkLoginRateLimit({
        request,
        username
      });


    if (
      rate.blocked
    ) {
      await writeAudit({
        actor:
          username ||
          "unknown",

        action:
          "auth.login.rate_limited",

        source:
          "web"
      });


      return denied(
        429,
        {
          "Retry-After":
            String(
              rate.retryAfter
            ),

          "Cache-Control":
            "no-store"
        }
      );
    }


    const user =
      await authenticateUser(
        username,
        password
      );


    if (
      !user
    ) {
      await recordLoginFailure({
        userKey:
          rate.userKey,

        ipKey:
          rate.ipKey
      });


      await writeAudit({
        actor:
          username ||
          "unknown",

        action:
          "auth.login.failed",

        source:
          "web"
      });


      return denied(
        401,
        {
          "Cache-Control":
            "no-store"
        }
      );
    }


    await recordLoginSuccess({
      userKey:
        rate.userKey
    });


    await setSessionCookie(
      createSession(
        user
      )
    );


    await writeAudit({
      actor:
        user.username,

      action:
        "auth.login.success",

      source:
        "web"
    });


    return Response.json(
      {
        ok:
          true,

        user
      },
      {
        headers: {
          "Cache-Control":
            "no-store"
        }
      }
    );

  } catch (
    error
  ) {
    console.error(
      "Login error:",
      error
    );


    return denied(
      500,
      {
        "Cache-Control":
          "no-store"
      }
    );
  }
}
