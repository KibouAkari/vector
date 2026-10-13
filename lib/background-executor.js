import crypto from "node:crypto";

import {
  db
} from "./db";

import {
  runAutonomousWorkflow
} from "./workflow-runtime";

import {
  runVectorAgent
} from "./agent-runtime";

import {
  classifyExecution
} from "./execution-router";

import {
  calculateModelCost,
  usdToChf
} from "./models";

import {
  calculateConfiguredProviderCost,
  resolveProviderForTask
} from "./model-config";

import {
  recordUsage
} from "./usage";

import {
  writeAudit
} from "./audit";

import {
  completeAgentJob,
  getAgentJob,
  failAgentJob,
  heartbeatAgentJob
} from "./background-jobs";

import {
  buildVisionInputs
} from "./chat-attachments";


import {
  bindGeneratedArtifactsToMessage
} from "./artifact-runtime";

/*
 * VECTOR_ARTIFACT_INTENT_5742
 */
function wantsGeneratedArtifact(
  value
) {
  const text =
    String(
      value ||
      ""
    ).toLowerCase();

  const action =
    /\b(create|generate|make|build|produce|export|prepare|draft|erstell|generier|mach|bau|exportier)\w*/i.test(
      text
    );

  const format =
    /\b(pdf|docx|xlsx|word document|word file|word datei|excel file|excel datei|excel workbook|spreadsheet|dokument|arbeitsmappe|tabelle als datei)\b/i.test(
      text
    );

  return (
    action &&
    format
  );
}



/*
 * VECTOR_ARTIFACT_PROVIDER_FAILOVER_57713
 *
 * 5.7.7 keeps provider failover deliberately narrow:
 *
 *   - Auto-routed artifact jobs only
 *   - transient provider HTTP failures only
 *   - at most two provider configurations
 *   - never after an artifact has already been persisted
 *
 * General workflow/provider brokering belongs to the later
 * Model Broker phase.
 */
function transientProviderStatus(
  error
) {
  const message =
    String(
      error?.message ||
      error ||
      ""
    );

  const match =
    message.match(
      /\bProvider returned HTTP (429|500|502|503|504)\b/
    );

  return match
    ? Number(
        match[1]
      )
    : null;
}


async function generatedArtifactExists(
  jobId
) {
  const result =
    await db.query(
      `
        SELECT 1
        FROM chat_attachments
        WHERE
          job_id = $1
          AND generated_by_assistant = TRUE
        LIMIT 1
      `,
      [
        jobId
      ]
    );

  return (
    result.rowCount >
    0
  );
}


export async function executeAgentJob(
  job
) {
  const payload =
    typeof job.payload === "string"
      ? JSON.parse(
          job.payload
        )
      : job.payload;

  let heartbeat = null;
  let providerRuntime = null;

  try {
    heartbeat =
      setInterval(
        () => {
          heartbeatAgentJob({
            id:
              job.id
          }).catch(
            () => {}
          );
        },
        15000
      );

    await heartbeatAgentJob({
      id:
        job.id,
      progress: {
        stage:
          "routing",
        message:
          "Selecting the best available model"
      }
    });

      /*
       * VECTOR_JOB_VISION_INPUT_572
       *
       * Only IDs are stored in the durable job.
       * Image bytes are decrypted here and stay in memory.
       */
      const attachmentIds =
        Array.isArray(
          payload.attachmentIds
        )
          ? payload.attachmentIds
          : [];

      const visionInputs =
        await buildVisionInputs({
          ownerUserId:
            payload.userId ||
            job.user_id,

          attachmentIds
        });

      let executionMessages =
        Array.isArray(
          payload.messages
        )
          ? payload.messages.map(
              (message) => ({
                ...message
              })
            )
          : [];

      if (visionInputs.length > 0) {
        let userMessageIndex = -1;

        for (
          let index =
            executionMessages.length - 1;
          index >= 0;
          index -= 1
        ) {
          if (
            executionMessages[index]
              ?.role === "user"
          ) {
            userMessageIndex = index;
            break;
          }
        }

        if (userMessageIndex < 0) {
          throw new Error(
            "Vector could not locate the user message for image analysis."
          );
        }

        const existing =
          executionMessages[
            userMessageIndex
          ]?.content;

        const content =
          Array.isArray(existing)
            ? [
                ...existing
              ]
            : [
                {
                  type:
                    "input_text",

                  text:
                    String(
                      existing ||
                      payload
                        .safeOriginalMessage ||
                      "Analyze the attached image."
                    )
                }
              ];

        for (const image of visionInputs) {
          content.push({
            type:
              "input_text",

            text:
              `Attached image: ${
                image.name ||
                "image"
              }`
          });

          content.push({
            type:
              "input_image",

            image_url:
              image.dataUrl,

            detail:
              image.detail ||
              "auto"
          });
        }

        executionMessages[
          userMessageIndex
        ] = {
          ...executionMessages[
            userMessageIndex
          ],

          content
        };

        await heartbeatAgentJob({
          id:
            job.id,

          progress: {
            stage:
              "vision",

            message:
              visionInputs.length === 1
                ? "Analyzing image"
                : `Analyzing ${visionInputs.length} images`
          }
        });
      }

    const routingTaskText =
      payload.safeOriginalMessage ||
      payload.originalUserMessage ||
      payload.messages?.at(-1)?.content ||
      "";

    /*
     * VECTOR_CONVERSATION_CONTEXT_INPUT_582C
     *
     * Only a short recent text window is supplied to the deterministic
     * execution classifier. The full conversation still goes to the
     * selected runtime as before.
     */
    const routingRecentMessages =
      executionMessages
        .slice(
          0,
          Math.max(
            0,
            executionMessages.length - 1
          )
        )
        .slice(-6)
        .map(
          (message) => ({
            role:
              message?.role,

            content:
              Array.isArray(
                message?.content
              )
                ? message.content
                    .map(
                      (part) => (
                        typeof part ===
                          "string"
                          ? part
                          : part?.text ||
                            part?.content ||
                            ""
                      )
                    )
                    .filter(Boolean)
                    .join("\n")
                : String(
                    message?.content ||
                    ""
                  )
          })
        );

    /*
     * VECTOR_EXECUTION_ROUTER_INTEGRATION_582
     *
     * Execution routing is deterministic/local and costs no model call.
     *
     * IMPORTANT:
     * allowServer is a permission, not evidence that this request needs
     * the server. Previously every owner request effectively required a
     * tool-capable provider because allowServer is normally true.
     */
    const execution =
      classifyExecution({
        taskText:
          routingTaskText,

        mode:
          payload.mode,

        webSearch:
          Boolean(
            payload.webSearch
          ),

        projectId:
          payload.projectId ||
          null,

        attachmentIds:
          payload.attachmentIds ||
          [],

        allowServer:
          Boolean(
            payload.allowServer
          ),

        recentMessages:
          routingRecentMessages
      });

    const effectiveWebSearch =
      Boolean(
        payload.webSearch ||
        execution.requirements
          ?.web
      );

    const routingRequireSearch =
      effectiveWebSearch;

    const routingRequireTools =
      Boolean(
        execution.requirements
          ?.functionTools
      );

    await heartbeatAgentJob({
      id:
        job.id,

      progress: {
        stage:
          "routing",

        message:
          execution.progress
      }
    });

    /*
     * Explicit provider/model selections are never silently changed.
     *
     * Current Auto jobs have neither providerId nor modelId.
     */
    const explicitProviderSelection =
      Boolean(
        payload.providerId ||
        payload.modelId
      );

    const artifactFailoverEligible =
      !explicitProviderSelection &&
      execution.class ===
        "artifact";

    /*
     * VECTOR_PROVIDER_FAMILY_FAILOVER_57716
     *
     * Do not spend the second bounded attempt on another
     * credential/configuration of the same provider family.
     */
    const attemptedProviderIds =
      [];

    const attemptedProviderFamilies =
      [];

    const maxProviderAttempts =
      artifactFailoverEligible
        ? 2
        : 1;

    let aiResult =
      null;

    let lastProviderError =
      null;

    for (
      let providerAttempt = 0;
      providerAttempt <
        maxProviderAttempts;
      providerAttempt += 1
    ) {
      providerRuntime =
        await resolveProviderForTask({
          mode:
            payload.mode,

          /*
           * VECTOR_PROVIDER_USER_SCOPE_563
           * Provider credentials remain scoped to the requesting account.
           */
          userId:
            payload.userId ||
            job.user_id,

          shadowComparison:
            true,

          taskText:
            routingTaskText,

          requireSearch:
            routingRequireSearch,

          requireTools:
            routingRequireTools,

          preferredProviderId:
            payload.providerId ||
            null,

          excludeProviderIds:
            attemptedProviderIds,

          excludeProviders:
            attemptedProviderFamilies
        });

      attemptedProviderIds.push(
        providerRuntime.id
      );

      const selectedProviderFamily =
        String(
          providerRuntime.provider ||
          ""
        )
          .trim()
          .toLowerCase();

      if (
        selectedProviderFamily &&
        !attemptedProviderFamilies.includes(
          selectedProviderFamily
        )
      ) {
        attemptedProviderFamilies.push(
          selectedProviderFamily
        );
      }

      await heartbeatAgentJob({
        id:
          job.id,

        progress: {
          stage:
            providerAttempt === 0
              ? "running"
              : "provider-failover",

          message:
            providerAttempt === 0
              ? `Using ${providerRuntime.label} · ${providerRuntime.model}`
              : `Trying ${providerRuntime.label} · ${providerRuntime.model}`
        }
      });

      try {
        const progressHandler =
          async (progress) => {
            await heartbeatAgentJob({
              id:
                job.id,

              progress: {
                stage:
                  progress?.stage ||
                  execution.class,

                message:
                  progress?.message ||
                  execution.progress
              }
            });
          };

        const runtimeArgs = {
          model:
            providerRuntime.model,

          providerRuntime,

          mode:
            payload.mode,

          messages:
            executionMessages,

          maxOutputTokens:
            payload.maxOutputTokens,

          webSearch:
            effectiveWebSearch,

          projectId:
            payload.projectId ||
            null,

          userId:
            payload.userId ||
            job.user_id,

          conversationId:
            payload.conversationId,

          jobId:
            job.id,

          originalUserMessage:
            payload.safeOriginalMessage ||
            routingTaskText,

          allowServer:
            Boolean(
              payload.allowServer
            ),

          onProgress:
            progressHandler
        };

        if (
          execution.class ===
          "deep"
        ) {
          aiResult =
            await runAutonomousWorkflow(
              runtimeArgs
            );

        } else {
          aiResult =
            await runVectorAgent({
              ...runtimeArgs,

              executionClass:
                execution.class,

              toolDomains:
                execution.requirements,

              roundLimit:
                execution.limits
                  ?.rounds,

              artifactRecoveryLimit:
                execution.limits
                  ?.artifactRecovery
            });
        }

        break;

      } catch (
        error
      ) {
        lastProviderError =
          error;

        const transientStatus =
          transientProviderStatus(
            error
          );

        const providerAttemptsRemain =
          providerAttempt + 1 <
          maxProviderAttempts;

        let artifactAlreadyCreated =
          false;

        if (
          artifactFailoverEligible &&
          transientStatus &&
          providerAttemptsRemain
        ) {
          artifactAlreadyCreated =
            await generatedArtifactExists(
              job.id
            );
        }

        const canFailover =
          artifactFailoverEligible &&
          Boolean(
            transientStatus
          ) &&
          providerAttemptsRemain &&
          !artifactAlreadyCreated;

        if (
          !canFailover
        ) {
          throw error;
        }

        /*
         * This audit entry contains no credentials or request content.
         */
        try {
          await writeAudit({
            actor:
              payload?.username ||
              "vector",

            action:
              "ai.provider.failover",

            resource:
              payload?.conversationId ||
              job.id,

            details: {
              jobId:
                job.id,

              fromProvider:
                providerRuntime.provider,

              fromLabel:
                providerRuntime.label,

              fromModel:
                providerRuntime.model,

              transientHttpStatus:
                transientStatus,

              nextAttempt:
                providerAttempt + 2,

              maxAttempts:
                maxProviderAttempts
            },

            source:
              "background-worker"
          });

        } catch {
          // Audit logging must not break failover.
        }

        await heartbeatAgentJob({
          id:
            job.id,

          progress: {
            stage:
              "provider-failover",

            message:
              `${providerRuntime.label} is temporarily unavailable. Trying another provider`
          }
        });
      }
    }

    if (
      !aiResult
    ) {
      throw (
        lastProviderError ||
        new Error(
          "Vector could not complete the provider failover."
        )
      );
    }

    const answerText =
      String(
        aiResult.text ||
        ""
      ).trim();

    if (!answerText) {
      throw new Error(
        `${providerRuntime.label} returned an empty response.`
      );
    }

    const currentJob =
      await getAgentJob(
        job.id
      );

    if (
      currentJob?.status ===
      "cancelled"
    ) {
      return {
        cancelled:
          true
      };
    }

    await heartbeatAgentJob({
      id:
        job.id,
      progress: {
        stage:
          "saving",
        message:
          "Saving result"
      }
    });

    let modelCost;

    if (
      providerRuntime.provider ===
      "openai"
    ) {
      modelCost =
        calculateModelCost({
          model:
            providerRuntime.model,
          inputTokens:
            aiResult.inputTokens,
          outputTokens:
            aiResult.outputTokens,
          cachedTokens:
            aiResult.cachedTokens
        });
    } else {
      modelCost =
        calculateConfiguredProviderCost({
          providerRuntime,
          inputTokens:
            aiResult.inputTokens,
          outputTokens:
            aiResult.outputTokens,
          cachedTokens:
            aiResult.cachedTokens,
          usdToChfRate:
            Number(
              process.env
                .USD_TO_CHF_RATE ||
              0.85
            )
        });
    }

    const searchCost =
      providerRuntime.provider ===
        "openai"
        ? usdToChf(
            Number(
              aiResult.webSearchCalls ||
              0
            ) *
            0.01
          )
        : 0;

    const costChf =
      Number(
        modelCost.chf ||
        0
      ) +
      searchCost;

    /*
     * VECTOR_JOB_ARTIFACT_SUCCESS_GUARD_57459
     *
     * Defense in depth:
     *
     * Even if a provider returns plausible final text, an explicit
     * PDF/DOCX/XLSX request is not complete until an artifact tool
     * actually succeeded.
     *
     * Usage is recorded before failing this guard so provider spend
     * remains visible instead of disappearing from Vector accounting.
     */
    const artifactRequestedForJob =
      wantsGeneratedArtifact(
        payload.safeOriginalMessage ||
        payload.originalUserMessage ||
        payload.messages
          ?.at(
            -1
          )
          ?.content ||
        ""
      );


    const artifactSucceededForJob =
      Boolean(
        aiResult
          ?.artifactCreated
      ) ||
      (
        aiResult
          ?.toolTrace ||
        []
      ).some(
        (
          item
        ) =>
          (
            item?.tool ===
              "artifact_create" ||
            item?.tool ===
              "artifact_create_from_server_json"
          ) &&
          item?.success ===
            true
      );


    if (
      artifactRequestedForJob &&
      !artifactSucceededForJob
    ) {
      await recordUsage({
        provider:
          providerRuntime.provider,

        model:
          providerRuntime.model,

        inputTokens:
          aiResult.inputTokens,

        outputTokens:
          aiResult.outputTokens,

        cachedTokens:
          aiResult.cachedTokens,

        costChf,

        userId:
          payload.userId ||
          job.user_id ||
          null
      });


      throw new Error(
        "The user explicitly requested a downloadable artifact, but no artifact tool completed successfully. Vector refused to mark the job completed without the requested file."
      );
    }


    const assistantMessageId =
      crypto.randomUUID();

    await db.query(
      `
        INSERT INTO messages (
          id,
          conversation_id,
          role,
          content,
          model,
          cost_chf
        )
        VALUES (
          $1,
          $2,
          'assistant',
          $3,
          $4,
          $5
        )
      `,
      [
        assistantMessageId,
        payload.conversationId,
        answerText,
        providerRuntime.model,
        costChf
      ]
    );

    await db.query(
      `
        UPDATE conversations
        SET updated_at = NOW()
        WHERE id = $1
      `,
      [
        payload.conversationId
      ]
    );

    if (
      payload.projectId
    ) {
      await db.query(
        `
          UPDATE projects
          SET updated_at = NOW()
          WHERE id = $1
        `,
        [
          payload.projectId
        ]
      );
    }

    const artifacts =
      await bindGeneratedArtifactsToMessage({
        ownerUserId:
          payload.userId ||
          job.user_id,

        conversationId:
          payload.conversationId,

        jobId:
          job.id,

        messageId:
          assistantMessageId
      });

    await recordUsage({
      provider:
        providerRuntime.provider,

      model:
        providerRuntime.model,

      inputTokens:
        aiResult.inputTokens,

      outputTokens:
        aiResult.outputTokens,

      cachedTokens:
        aiResult.cachedTokens,

      costChf,

      userId:
        payload.userId ||
        job.user_id ||
        null
    });

    await writeAudit({
      actor:
        payload.username ||
        "vector",

      action:
        payload.projectId
          ? "project.ai.completed"
          : "ai.request.completed",

      resource:
        payload.projectId ||
        payload.conversationId,

      details: {
        conversationId:
          payload.conversationId,

        jobId:
          job.id,

        provider:
          providerRuntime.provider,

        providerLabel:
          providerRuntime.label,

        model:
          providerRuntime.model,

        mode:
          payload.mode,

        executionClass:
          execution.class,

        executionReason:
          execution.reason,

        webSearchCalls:
          aiResult.webSearchCalls ||
          0,

        protectedValues:
          payload.protectedValues ||
          0,

        filesRetrieved:
          payload.filesRetrieved ||
          0,

        inputTokens:
          aiResult.inputTokens,

        outputTokens:
          aiResult.outputTokens,

        costChf
      },

      source:
        payload.projectId
          ? "project-worker"
          : "chat-worker"
    });

    const result = {
      assistantMessageId,

      artifacts,

      text:
        answerText,

      privacy:
        payload.privacy || {
          protected:
            false,
          count:
            0,
          types:
            []
        },

      retrieval:
        payload.retrieval ||
        [],

      meta: {
        provider:
          providerRuntime.provider,

        providerLabel:
          providerRuntime.label,

        model:
          providerRuntime.model,

        mode:
          payload.mode,

        executionClass:
          execution.class,

        executionReason:
          execution.reason,

        webSearch:
          payload.webSearch,

        webSearchCalls:
          aiResult.webSearchCalls ||
          0,

        citations:
          aiResult.citations ||
          [],

        toolTrace:
          aiResult.toolTrace ||
          [],

        costChf
      }
    };

    await completeAgentJob({
      id:
        job.id,
      assistantMessageId,
      result
    });

    return result;

  } catch (
    error
  ) {
    try {
      await writeAudit({
        actor:
          payload?.username ||
          "vector",

        action:
          "ai.request.failed",

        resource:
          payload?.conversationId ||
          job.id,

        details: {
          jobId:
            job.id,

          provider:
            providerRuntime
              ?.provider ||
            null,

          model:
            providerRuntime
              ?.model ||
            payload?.model,

          error:
            String(
              error?.message ||
              error
            )
        },

        source:
          "background-worker"
      });
    } catch {
      // Keep original failure.
    }

    await failAgentJob({
      id:
        job.id,
      error
    });

    throw error;

  } finally {
    if (
      heartbeat
    ) {
      clearInterval(
        heartbeat
      );
    }
  }
}
