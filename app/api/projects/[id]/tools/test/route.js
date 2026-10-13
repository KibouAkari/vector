import {
  getSession
} from "../../../../../../lib/auth";

import {
  createToolContext,
  executeVectorTool
} from "../../../../../../lib/tool-runtime";

export const runtime =
  "nodejs";

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
        status:
          401
      }
    );
  }

  const {
    id:
      projectId
  } =
    await context.params;

  const toolContext =
    createToolContext({
      projectId
    });

  const write =
    await executeVectorTool({
      name:
        "sandbox_write_file",

      arguments: {
        path:
          "vector-test.js",

        content:
          "console.log('Vector sandbox OK')"
      },

      context:
        toolContext
    });

  const run =
    await executeVectorTool({
      name:
        "sandbox_run",

      arguments: {
        command:
          "node vector-test.js",

        timeout_ms:
          10000
      },

      context:
        toolContext
    });

  return Response.json({
    ok:
      run.code ===
      0,

    write,

    run
  });
}
