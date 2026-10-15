import {
  runVectorAgent,
  extractAuthorizedTargets
} from "./agent-runtime";

import {
  createToolContext
} from "./tool-runtime";


import {
  requestSimpleProviderText
} from "./provider-runtime";


function needsWorkflow(
  text,
  mode
) {
  if (
    mode === "deep" ||
    mode === "research"
  ) {
    return true;
  }

  const value =
    String(
      text ||
      ""
    ).toLowerCase();

  return [
    "build",
    "create",
    "implement",
    "fix",
    "debug",
    "analyse",
    "analyze",
    "scan",
    "review",
    "inspect",
    "test",
    "compile",
    "server",
    "project",
    "crash",
    "code",
    "website",
    "application",
    "app",
    "security",
    "vulnerability"
  ].some(
    (
      signal
    ) =>
      value.includes(
        signal
      )
  );
}


async function smallModelRequest({
  input,
  instructions,
  maxOutputTokens = 450,
  providerRuntime,
  model
}) {
  return requestSimpleProviderText({
    providerRuntime,
    model,
    input,
    instructions,
    maxOutputTokens
  });
}


async function createPlan({
  userMessage,
  projectAttached,
  providerRuntime,
  model
}) {
  return smallModelRequest({
    providerRuntime,
    model,
    maxOutputTokens:
      350,

    instructions: [
      "You are Vector's internal task planner.",
      "Produce a short execution plan, not chain-of-thought.",
      "Use 2-6 concrete steps.",
      "Identify which available capabilities are likely needed.",
      "Do not answer the user.",
      "Do not invent tool results.",
      "",
      projectAttached
        ? "The agent has access to project files, project search, sandbox and authorized network tools."
        : "The agent has sandbox and authorized network tools."
    ].join("\n"),

    input:
      userMessage
  });
}


/* VECTOR_REVIEWER_PROVIDER_PROPAGATION_57426 */
async function reviewResult({
  userMessage,
  answer,
  toolTrace,
  providerRuntime,
  model
}) {
  const compactTrace =
    toolTrace
      .map(
        (
          item
        ) => (
          `${item.tool}: ${
            item.success
              ? "success"
              : "failed"
          }`
        )
      )
      .join("\n");

  return smallModelRequest({
    providerRuntime,
    model,

    maxOutputTokens:
      650,

    instructions: [
      "You are Vector's independent result reviewer.",
      "Compare the USER GOAL against the PROPOSED ANSWER requirement by requirement.",
      "Silently identify every explicit deliverable, constraint and requested follow-up in the user's request.",
      "PASS only if every explicit requested item is actually present, correct enough to use, and not contradicted elsewhere in the answer.",
      "If even one requested part is missing, return REPAIR and list every missing or incorrect requirement.",
      "A requested script plus requested cron commands are two separate deliverables; both must be present.",
      "A request to analyze and improve an existing file is incomplete if the answer only gives replacement code without addressing the requested operational steps.",
      "For technical answers, scripts, commands and configuration should use fenced Markdown code blocks when they are meant to be copied.",
      "Independently runnable commands should be separated from large scripts when that makes them easier to copy.",
      "When the user asks for fewer messages or a concise answer, require one cohesive response, but never trade away requested content.",
      "Pay special attention to whether claimed actions were verified by tool results.",
      "",
      "Return exactly one of:",
      "PASS",
      "or",
      "REPAIR: <concise actionable feedback listing every missing or incorrect requirement>",
      "",
      "Do not provide a rewritten final answer."
    ].join("\n"),

    input: [
      "USER GOAL:",
      userMessage,
      "",
      "TOOL TRACE:",
      compactTrace ||
        "No tools used",
      "",
      "PROPOSED ANSWER:",
      answer
    ].join("\n")
  });
}


/* VECTOR_ARTIFACT_CONTEXT_PROPAGATION_57427 */
/*
 * VECTOR_ARTIFACT_WORKFLOW_REQUIRED_57459
 *
 * Artifact jobs always use the shared workflow tool context so
 * artifactCreated/lastArtifact survive planner/reviewer repair passes.
 */
function artifactWorkflowRequested(
  value
) {
  return (
    /\b(pdf|docx|xlsx|spreadsheet|workbook|excel|word document|word file|arbeitsmappe|excel datei|word datei)\b/i
      .test(
        String(
          value ||
          ""
        )
      )
  );
}


export async function runAutonomousWorkflow({
  model,
  mode,
  providerRuntime = null,
  messages,
  maxOutputTokens,
  webSearch,
  projectId,
  userId = null,
  conversationId,
  jobId = null,
  originalUserMessage,
  allowServer = false,
  onProgress = null
}) {
  const workflow =
    artifactWorkflowRequested(
      originalUserMessage
    ) ||
    needsWorkflow(
      originalUserMessage,
      mode
    );

  if (!workflow) {
    return runVectorAgent({
      model,
      providerRuntime,
      mode,
      messages,
      maxOutputTokens,
      webSearch,
      projectId,
      userId,
      conversationId,
      jobId,
      originalUserMessage,
      allowServer
    });
  }

  const authorizedTargets =
    extractAuthorizedTargets(
      originalUserMessage
    );

  const toolContext =
    createToolContext({
      projectId,
      userId,
      conversationId,
      jobId,
      authorizedTargets
    });

  toolContext.onProgress =
    onProgress;

  let planner = null;

  if (
    typeof onProgress ===
    "function"
  ) {
    await Promise.resolve(
      onProgress({
        stage: "planning",
        message: "Planning approach"
      })
    ).catch(() => {});
  }

  try {
    planner =
      await createPlan({
        userMessage:
          originalUserMessage,

        projectAttached:
          Boolean(
            projectId
          ),

        providerRuntime,
        model
      });

  } catch (
    error
  ) {
    console.error(
      "Planner failed:",
      error
    );
  }


  /*
   * VECTOR_PROVIDER_SAFE_PLANNER_HANDOFF_57455
   *
   * The planner is internal execution metadata, not an assistant turn.
   *
   * Some providers, notably Gemini/OpenAI-compatible endpoints,
   * reject requests whose conversation ends with a model/assistant
   * message:
   *
   *   "Requests ending with a model turn are not supported."
   *
   * Merge the plan into the latest user turn whenever possible.
   * This keeps the conversation semantically executable and avoids
   * creating fake assistant history.
   */
  const executionMessages =
    (
      Array.isArray(
        messages
      )
        ? messages
        : []
    ).map(
      (
        message
      ) => ({
        ...message
      })
    );


  if (
    planner?.text
  ) {
    const internalPlan =
      [
        "INTERNAL VECTOR EXECUTION PLAN:",
        "This plan was generated internally by Vector and was not written by the user.",
        "Follow it silently where useful.",
        "",
        planner.text,
        "",
        "Proceed with the user's request using tools where useful."
      ].join(
        "\n"
      );


    const lastIndex =
      executionMessages.length -
      1;


    const lastMessage =
      lastIndex >=
        0
        ? executionMessages[
            lastIndex
          ]
        : null;


    /*
     * Normal path:
     * the current conversation should end with the user's request.
     *
     * Merge the internal plan into that turn instead of inventing
     * a terminal assistant/model turn.
     */
    if (
      lastMessage?.role ===
        "user" &&
      typeof lastMessage.content ===
        "string"
    ) {
      executionMessages[
        lastIndex
      ] = {
        ...lastMessage,

        content:
          [
            lastMessage.content,
            "",
            internalPlan
          ].join(
            "\n"
          )
      };

    } else {

      /*
       * Defensive fallback for unusual message representations.
       * Still terminate with an executable user turn.
       */
      executionMessages.push({
        role:
          "user",

        content:
          internalPlan
      });
    }
  }


  let result =

    await runVectorAgent({
      model,
      providerRuntime,
      mode,
      messages:
        executionMessages,
      maxOutputTokens,
      webSearch,
      projectId,
      userId,
      conversationId,
      jobId,
      originalUserMessage,
      providedToolContext:
        toolContext,

      allowServer
    });

  let reviewer = null;

  /*
   * Review tool-using or complex work.
   */
  if (
    result.toolTrace
      ?.length >
      0 ||
    mode === "deep" ||
    mode === "research"
  ) {
    if (
      typeof onProgress ===
      "function"
    ) {
      await Promise.resolve(
        onProgress({
          stage: "reviewing",
          message: "Reviewing result"
        })
      ).catch(() => {});
    }

    try {
      reviewer =
        await reviewResult({
          userMessage:
            originalUserMessage,

          answer:
            result.text,

          toolTrace:
            result.toolTrace ||
            [],

          providerRuntime,
          model
        });

    } catch (
      error
    ) {
      console.error(
        "Reviewer failed:",
        error
      );
    }
  }

  /*
   * One repair pass, using the SAME sandbox context.
   */
  if (
    reviewer
      ?.text
      ?.startsWith(
        "REPAIR:"
      )
  ) {
    if (
      typeof onProgress ===
      "function"
    ) {
      await Promise.resolve(
        onProgress({
          stage: "refining",
          message: "Refining answer"
        })
      ).catch(() => {});
    }

    const feedback =
      reviewer.text.slice(
        "REPAIR:".length
      ).trim();

    const initialResult = result;
    result =
      await runVectorAgent({
        model,
        providerRuntime,
        mode,

        messages: [
          ...executionMessages,

          {
            role:
              "assistant",

            content:
              result.text
          },

          {
            role:
              "user",

            content: [
              "Internal reviewer feedback:",
              feedback,
              "",
              "Correct the result.",
              "Return a complete replacement final answer, not an addendum.",
              "Preserve correct useful material from the previous answer while fixing every item mentioned by the reviewer.",
              "Re-check the original user request and ensure every explicit deliverable is present.",
              "Use fenced Markdown code blocks for scripts, commands and configuration.",
              "Use tools again if necessary.",
              "Do not mention this internal review process."
            ].join("\n")
          }
        ],

        maxOutputTokens,
        webSearch,
        projectId,
        userId,
        conversationId,
        jobId,
        originalUserMessage,

        providedToolContext:
          toolContext,

      allowServer,
});
    result = {...result,
      inputTokens: Number(initialResult.inputTokens || 0) + Number(result.inputTokens || 0),
      outputTokens: Number(initialResult.outputTokens || 0) + Number(result.outputTokens || 0),
      cachedTokens: Number(initialResult.cachedTokens || 0) + Number(result.cachedTokens || 0),
      providerCalls: [...(initialResult.providerCalls || []), ...(result.providerCalls || [])]};
  }

  return {
    ...result,

    /* VECTOR_WORKFLOW_ARTIFACT_STATE_57459 */
    artifactCreated:
      Boolean(
        toolContext
          ?.artifactCreated ||
        result
          ?.artifactCreated
      ),

    artifact:
      toolContext
        ?.lastArtifact ||
      result
        ?.artifact ||
      null,

    planner:
      planner?.text ||
      null,

    reviewer:
      reviewer?.text ||
      null,

    inputTokens:
      result.inputTokens +
      Number(
        planner?.inputTokens ||
        0
      ) +
      Number(
        reviewer?.inputTokens ||
        0
      ),

    outputTokens:
      result.outputTokens +
      Number(
        planner?.outputTokens ||
        0
      ) +
      Number(
        reviewer?.outputTokens ||
        0
      ),

    cachedTokens:
      result.cachedTokens +
      Number(
        planner?.cachedTokens ||
        0
      ) +
      Number(
        reviewer?.cachedTokens ||
        0
      )
  };
}

