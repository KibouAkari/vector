import {
  getSession,
  hasFeature
} from "../../../../lib/auth";

import {
  hostSnapshot,
  hostInspect
} from "../../../../lib/host-agent";

import { normalizeContainerResources } from "../../../../lib/server-resources.mjs";

export const dynamic = "force-dynamic";


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

  if (!hasFeature(session, "server")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  try {
    const [snapshot, resources] = await Promise.allSettled([
      hostSnapshot(),
      hostInspect({ action: "docker_stats" })
    ]);

    if (snapshot.status !== "fulfilled") {
      throw new Error("Host snapshot unavailable.");
    }

    return Response.json({
      ...snapshot.value,
      listeningPorts: snapshot.value.listeningPorts ?? snapshot.value.ports,
      containerResources: normalizeContainerResources(
        resources.status === "fulfilled" ? resources.value : null,
        new Date().toISOString()
      )
    }, { headers: { "Cache-Control": "no-store" } });

  } catch (
    error
  ) {
    return Response.json(
      {
        error:
          "Host snapshot unavailable."
      },
      {
        status:
          503
      }
    );
  }
}

