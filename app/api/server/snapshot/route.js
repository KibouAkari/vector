import {
  getSession
} from "../../../../lib/auth";

import {
  hostSnapshot
} from "../../../../lib/host-agent";


export async function GET() {
  const session =
    await getSession();

  if (!session) {
    return Response.json(
      {
        error:
          "Unauthorized"
      },
      {
        status:
          401
      }
    );
  }

  try {
    return Response.json(
      await hostSnapshot()
    );

  } catch (
    error
  ) {
    return Response.json(
      {
        error:
          error.message
      },
      {
        status:
          503
      }
    );
  }
}
