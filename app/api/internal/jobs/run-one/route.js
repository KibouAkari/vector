import crypto from "node:crypto";

import {
  claimNextAgentJob
} from "../../../../../lib/background-jobs";

import {
  executeAgentJob
} from "../../../../../lib/background-executor";

export const runtime =
  "nodejs";

export const dynamic =
  "force-dynamic";


function authorized(
  request
) {
  const expected =
    process.env
      .INTERNAL_API_SECRET;

  const provided =
    request.headers.get(
      "authorization"
    );

  if (
    !expected ||
    !provided
  ) {
    return false;
  }

  const left =
    Buffer.from(
      provided
    );

  const right =
    Buffer.from(
      `Bearer ${expected}`
    );

  return (
    left.length ===
      right.length &&
    crypto.timingSafeEqual(
      left,
      right
    )
  );
}


export async function POST(
  request
) {
  if (
    !authorized(request)
  ) {
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

  const workerId =
    request.headers.get(
      "x-vector-worker"
    ) ||
    "vector-worker";

  const job =
    await claimNextAgentJob(
      workerId
    );

  if (
    !job
  ) {
    return Response.json({
      ok: true,
      claimed: false
    });
  }

  try {
    await executeAgentJob(
      job
    );

    return Response.json({
      ok: true,
      claimed: true,
      jobId: job.id
    });

  } catch (error) {
    return Response.json({
      ok: false,
      claimed: true,
      jobId: job.id,
      error: error.message
    });
  }
}
