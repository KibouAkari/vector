const RUNNER_URL =
  process.env
    .VECTOR_RUNNER_URL ||
  "http://runner:3100";


function runnerToken() {
  return (
    process.env
      .VECTOR_RUNNER_TOKEN ||
    process.env
      .INTERNAL_API_SECRET
  );
}


async function requestRunner(
  endpoint,
  body
) {
  const token =
    runnerToken();

  if (!token) {
    throw new Error(
      "Vector Runner authentication token is missing."
    );
  }

  const response =
    await fetch(
      `${RUNNER_URL}${endpoint}`,
      {
        method:
          "POST",

        headers: {
          "Content-Type":
            "application/json",

          Authorization:
            `Bearer ${token}`
        },

        body:
          JSON.stringify(
            body
          )
      }
    );

  let data;

  try {
    data =
      await response.json();
  } catch {
    data = {};
  }

  if (
    !response.ok
  ) {
    throw new Error(
      data.error ||
      `Runner returned HTTP ${response.status}`
    );
  }

  return data;
}


export async function runnerAuthenticatedHealth() {
  const token =
    runnerToken();

  const response =
    await fetch(
      `${RUNNER_URL}/auth-health`,
      {
        method:
          "POST",

        headers: {
          Authorization:
            `Bearer ${token}`
        }
      }
    );

  if (
    !response.ok
  ) {
    throw new Error(
      `Runner authentication failed with HTTP ${response.status}`
    );
  }

  return response.json();
}


export async function sandboxRun({
  projectId,
  runId,
  command,
  timeoutMs = 60000
}) {
  return requestRunner(
    "/run",
    {
      projectId,
      runId,
      command,
      timeoutMs
    }
  );
}


export async function sandboxWrite({
  projectId,
  runId,
  path,
  content
}) {
  return requestRunner(
    "/write",
    {
      projectId,
      runId,
      path,
      content
    }
  );
}


export async function sandboxRead({
  projectId,
  runId,
  path
}) {
  return requestRunner(
    "/read",
    {
      projectId,
      runId,
      path
    }
  );
}


export async function sandboxList({
  projectId,
  runId
}) {
  return requestRunner(
    "/list",
    {
      projectId,
      runId
    }
  );
}


export async function sandboxCleanup({
  projectId,
  runId
}) {
  return requestRunner(
    "/cleanup",
    {
      projectId,
      runId
    }
  );
}
