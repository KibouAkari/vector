import {
  getSession,
  hasFeature
} from "../../../../../lib/auth";

import {
  getProviderRuntimeById
} from "../../../../../lib/model-config";

import {
  testProviderConnection
} from "../../../../../lib/provider-runtime";


export async function POST(
  request,
  context
) {
  const session =
    await getSession();

  if (!session) {
    return Response.json(
      {
        error:
          "Unauthorized"
      },
      {
        status: 401
      }
    );
  }

  if (!hasFeature(session, "models")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  const {
    id
  } =
    await context.params;

  try {
    /*
     * Users may test only credentials they own.
     * Shared workspace credentials are never exposed through this endpoint.
     */
    const runtime =
      await getProviderRuntimeById(
        id,
        {
          userId:
            session.userId,
          allowShared:
            false,
          mode:
            "normal",
          taskText:
            "Connection test"
        }
      );

    const result =
      await testProviderConnection(
        runtime
      );

    return Response.json(
      result
    );

  } catch (
    error
  ) {
    return Response.json(
      {
        ok:
          false,
        error:
          String(
            error?.message ||
            error
          )
      },
      {
        status:
          400
      }
    );
  }
}
