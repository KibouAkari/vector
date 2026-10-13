import {
  getSession
} from "../../../../lib/auth";

import {
  getPermissionPolicy
} from "../../../../lib/permissions";

export const runtime = "nodejs";

export async function POST(request) {
  const session =
    await getSession();

  if (!session) {
    return Response.json(
      {
        error: "Unauthorized"
      },
      {
        status: 401
      }
    );
  }

  const body =
    await request.json();

  const permission =
    String(
      body.permission || ""
    );

  if (!permission) {
    return Response.json(
      {
        error:
          "Permission required"
      },
      {
        status: 400
      }
    );
  }

  const policy =
    await getPermissionPolicy(
      permission
    );

  return Response.json(
    policy
  );
}
