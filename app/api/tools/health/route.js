import {
  getSession
} from "../../../../lib/auth";

export const runtime =
  "nodejs";

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
    const response =
      await fetch(
        `${
          process.env
            .VECTOR_RUNNER_URL ||
          "http://runner:3100"
        }/health`
      );

    const body =
      await response.json();

    return Response.json({
      tools:
        "ok",

      runner:
        body.runner
    });

  } catch (
    error
  ) {
    return Response.json(
      {
        tools:
          "error",

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
