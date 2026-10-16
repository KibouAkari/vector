import {requestDestination} from '../../../lib/chat-controls.mjs';
import {reviewPrivacyRequest} from '../../../lib/privacy-review';
import crypto from "node:crypto";

import {
  getSession,
  hasFeature
} from "../../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../../lib/db";

import {
  sanitizeForExternal
} from "../../../lib/privacy";

import {
  savePrivacyMappings,
  restorePrivateValues
} from "../../../lib/privacy-vault";

import {
  checkCost
} from "../../../lib/cost";

import {
  estimateRequestCost,
  usdToChf
} from "../../../lib/models";

import {
  determineTaskMode,
  getMaximumOutputTokens,
  getModelForMode,
  shouldUseWebSearch
} from "../../../lib/router";

import {
  assertUserBudget
} from "../../../lib/identity";

import {
  enqueueAgentJob,
  findRecentDuplicate,
  makeRequestHash,
  waitForAgentJob
} from "../../../lib/background-jobs";

import {
  bindChatAttachments,
  CHAT_ATTACHMENT_CONTEXT_MARKER,
  initializeChatAttachmentDatabase,
  prepareChatAttachmentContext
} from "../../../lib/chat-attachments";

export const runtime =
  "nodejs";


function cleanTitle(
  text
) {
  const clean =
    String(
      text || ""
    )
      .replace(
        /<[A-Z0-9_]+>/g,
        ""
      )
      .replace(
        /\s+/g,
        " "
      )
      .trim();

  if (
    clean.length <= 55
  ) {
    return (
      clean ||
      "New conversation"
    );
  }

  return (
    clean.slice(
      0,
      52
    ) +
    "..."
  );
}


async function responseFromJob({
  job,
  conversationId,
  userMessageId,
  safeMessage
}) {
  if (
    [
      "queued",
      "running"
    ].includes(
      job.status
    )
  ) {
    return Response.json(
      {
        ok: true,
        background: true,
        jobId: job.id,
        conversationId,

        userMessage: {
          id:
            userMessageId,

          content:
            await restorePrivateValues({
              conversationId,
              text:
                safeMessage
            })
        },

        message: null,
        progress:
          job.progress
      },
      {
        status: 202
      }
    );
  }

  if (
    job.status !==
      "completed"
  ) {
    return Response.json(
      {
        error:
          "PROVIDER_ERROR",

        message:
          job.error ||
          "Vector could not complete this task.",

        jobId:
          job.id
      },
      {
        status: 502
      }
    );
  }

  const result =
    job.result || {};

  return Response.json({
    ok: true,
    background: false,
    jobId: job.id,
    conversationId,

    userMessage: {
      id:
        userMessageId,

      content:
        await restorePrivateValues({
          conversationId,
          text:
            safeMessage
        })
    },

    message: {
      id:
        result.assistantMessageId,

      role:
        "assistant",

      content:
        await restorePrivateValues({
          conversationId,
          text:
            result.text || ""
        })
    },

    privacy:
      result.privacy,

    meta:
      result.meta
  });
}


export async function POST(
  request
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

  if (!hasFeature(session, "chat")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  const body =
    await request.json();

  if (body.privacyEnabled !== undefined && typeof body.privacyEnabled !== 'boolean') {
    return Response.json({error:'Ungültige Datenschutzeinstellung.'},{status:400});
  }

  const originalMessage =
    String(
      body.message || ""
    ).trim();

  const requestedMode =
    String(
      body.mode || "auto"
    );

  const userBudget =
    await assertUserBudget(
      session
    );

  let conversationId =
    body.conversationId
      ? String(
          body.conversationId
        )
      : null;

    const attachmentIds =
      Array.isArray(
        body.attachmentIds
      )
        ? [
            ...new Set(
              body.attachmentIds
                .map(
                  (id) =>
                    String(
                      id ||
                      ""
                    ).trim()
                )
                .filter(
                  Boolean
                )
            )
          ].slice(
            0,
            6
          )
        : [];

  if (
    !originalMessage
  ) {
    return Response.json(
      {
        error:
          "Message is required"
      },
      {
        status: 400
      }
    );
  }

  if (
    originalMessage.length >
    100000
  ) {
    return Response.json(
      {
        error:
          "This message is too large for direct chat. Vector Files will handle large content."
      },
      {
        status: 413
      }
    );
  }

    await initializeDatabase();
    await initializeChatAttachmentDatabase();

    let attachmentBundle;

    try {
      attachmentBundle =
        await prepareChatAttachmentContext({
          ownerUserId:
            session.userId,

          attachmentIds,
          conversationId
        });

    } catch (error) {
      return Response.json(
        {
          error:
            "ATTACHMENT_ERROR",

          message:
            error.message ||
            "Could not prepare attachments."
        },
        {
          status: 400
        }
      );
    }

    const rawAgentMessage =
      attachmentBundle.context
        ? [
            originalMessage,
            CHAT_ATTACHMENT_CONTEXT_MARKER,
            attachmentBundle.context
          ].join("")
        : originalMessage;

    // Authorize before reading history or disclosing any privacy finding.
    if (conversationId) {
      const owned = await db.query(`SELECT id FROM conversations WHERE id=$1 AND user_id=$2 AND project_id IS NULL LIMIT 1`,
        [conversationId, session.userId]);
      if (!owned.rowCount) return Response.json({error:'Conversation not found'}, {status:404});
    }
    const configuredHistory=Number(process.env.VECTOR_CHAT_HISTORY_MESSAGES || 24);
    const historyLimit=Number.isFinite(configuredHistory)?Math.max(2,Math.min(40,configuredHistory)):24;
    const priorHistory = conversationId ? (await db.query(`SELECT id,role,content FROM messages
      WHERE conversation_id=$1 ORDER BY created_at DESC LIMIT $2`,[conversationId,historyLimit-1])).rows.reverse() : [];
    let destination;
    try {
      destination=requestDestination({mode:requestedMode,text:rawAgentMessage,recentMessages:priorHistory,
        allowServer:session.role==='owner'||Boolean(session.features?.server),
        localEnabled:process.env.VECTOR_LOCAL_WORKERS==='1',hasAttachments:attachmentIds.length>0});
    } catch { return Response.json({error:'Unbekannter Chatmodus.'},{status:400}); }
    if (!userBudget.allowed && destination !== 'local') {
      return Response.json({error:'USER_BUDGET_BLOCKED',message:userBudget.reason},{status:402});
    }
    let privacy;
    try {
      privacy = await reviewPrivacyRequest({text:[rawAgentMessage,...priorHistory.map(m=>m.content)].join('\n\n'),
        scanSegments:[rawAgentMessage,...priorHistory.map(m=>m.content)],previewText:originalMessage,
        body,session,scope:'chat',conversationId,destination,
        uninspectable:attachmentBundle.attachments.some(a=>String(a.mimeType).startsWith('image/'))});
    } catch {
      return Response.json({error:'PRIVACY_REVIEW_FAILED',message:'Die lokale Datenschutzprüfung konnte nicht abgeschlossen werden. Es wurde nichts extern versendet. Bitte erneut prüfen oder den lokalen Textmodus wählen.'},
        {status:503,headers:{'Cache-Control':'no-store'}});
    }
    if (privacy.response) return privacy.response;
    const safeAgentMessage = privacy.apply(rawAgentMessage);

    const markerIndex =
      safeAgentMessage.indexOf(
        CHAT_ATTACHMENT_CONTEXT_MARKER
      );

    const safeMessage =
      markerIndex >= 0
        ? safeAgentMessage
            .slice(
              0,
              markerIndex
            )
            .trim()
        : safeAgentMessage;

  const mode = privacy.destination === 'local' ? 'local' : determineTaskMode({message:safeAgentMessage,requestedMode});

  const useWebSearch = privacy.destination !== 'local' && shouldUseWebSearch({
      message:
        safeAgentMessage,
      requestedMode:
        mode
    });

  const model = privacy.destination === 'local' ? 'vector-qwen3:1.7b-q8' : getModelForMode(mode);

  const maxOutputTokens =
    getMaximumOutputTokens(
      mode
    );

  let budget =
    Number(
      process.env
        .DEFAULT_NORMAL_TASK_BUDGET_CHF ||
      0.10
    );

  if (
    mode === "quick"
  ) {
    budget =
      Number(
        process.env
          .DEFAULT_QUICK_TASK_BUDGET_CHF ||
        0.03
      );
  }

  if (
    mode === "deep"
  ) {
    budget =
      Number(
        process.env
          .DEFAULT_DEEP_TASK_BUDGET_CHF ||
        0.40
      );
  }

  if (
    mode === "research"
  ) {
    budget =
      Number(
        process.env
          .DEFAULT_RESEARCH_TASK_BUDGET_CHF ||
        0.25
      );
  }

  const estimate =
    estimateRequestCost({
      model,
      text:
        safeAgentMessage,
      maxOutputTokens
    });

  const searchReserve =
    useWebSearch
      ? usdToChf(
          mode === "research"
            ? 0.10
            : 0.04
        )
      : 0;

  const costDecision =
    await checkCost({
      estimatedCost:
        estimate.chf +
        searchReserve,

      taskBudget:
        budget,

      taskSpent:
        0
    });

  if (privacy.destination !== 'local' && !costDecision.allowed) {
    return Response.json(
      {
        error:
          "COST_BLOCKED",

        reason:
          costDecision.reason,

        estimatedCostChf:
          estimate.chf +
          searchReserve
      },
      {
        status: 402
      }
    );
  }

  /*
   * VECTOR_ACCOUNT_ISOLATION_563
   *
   * A conversation belongs to exactly one authenticated user.
   * Return 404 instead of revealing whether another user's chat exists.
   */
  if (
    conversationId
  ) {
    const ownedConversation =
      await db.query(
        `
          SELECT id
          FROM conversations
          WHERE
            id = $1
            AND
            user_id = $2
            AND
            project_id IS NULL
          LIMIT 1
        `,
        [
          conversationId,
          session.userId
        ]
      );

    if (
      ownedConversation.rowCount ===
      0
    ) {
      return Response.json(
        {
          error:
            "Conversation not found"
        },
        {
          status:
            404
        }
      );
    }
  }

  if (
    !conversationId
  ) {
    conversationId =
      crypto.randomUUID();

    await db.query(
      `
        INSERT INTO conversations (
          id,
          title,
          owner_user_id,
          user_id
        )
        VALUES (
          $1,
          $2,
          $3,
          $4
        )
      `,
      [
        conversationId,
        cleanTitle(
          safeMessage
        ),
        session.userId,
        session.userId
      ]
    );
  }

  const requestHash =
    makeRequestHash({
      userId:
        session.userId,
      conversationId,
      message:
        safeAgentMessage + '\nprivacy:' + privacy.destination + ':' + (body.privacyEnabled===false?'off':body.privacyDecision || 'replace')
    });

    const duplicate =
      attachmentIds.length === 0
        ? await findRecentDuplicate({
            userId:
              session.userId,

            conversationId,
            requestHash
          })
        : null;

  if (
    duplicate
  ) {
    return responseFromJob({
      job:
        duplicate,
      conversationId,
      userMessageId:
        duplicate.user_message_id,
      safeMessage
    });
  }

  await savePrivacyMappings({
    conversationId,
    mappings:
      privacy.mappings
  });

  const userMessageId =
    crypto.randomUUID();

  await db.query(
    `
      INSERT INTO messages (
        id,
        conversation_id,
        role,
        content
      )
      VALUES (
        $1,
        $2,
        'user',
        $3
      )
    `,
    [
      userMessageId,
      conversationId,
      safeMessage
    ]
  );

    try {
      await bindChatAttachments({
        ownerUserId:
          session.userId,

        attachmentIds,
        conversationId,

        messageId:
          userMessageId
      });

    } catch (error) {
      await db.query(
        `
          DELETE FROM messages
          WHERE
            id = $1
            AND conversation_id = $2
        `,
        [
          userMessageId,
          conversationId
        ]
      );

      return Response.json(
        {
          error:
            "ATTACHMENT_BIND_ERROR",

          message:
            error.message ||
            "Could not bind attachments."
        },
        {
          status: 400
        }
      );
    }

  // Use exactly the reviewed snapshot; never re-read unreviewed concurrent history.
  const history = [...priorHistory.map(row=>({role:row.role==='assistant'?'assistant':'user',
    content:privacy.apply(row.content)})),{role:'user',content:safeAgentMessage}];

  const jobId =
    await enqueueAgentJob({
      userId:
        session.userId,

      conversationId,
      userMessageId,
      requestHash,

      payload: {
        privacyPolicy:privacy.policy,
        privacyDestination:privacy.destination,
        userId:
          session.userId,

        username:
          session.username,

        conversationId,
        projectId: null,
        model,
        mode,

        attachmentIds,
        messages:
          history,
        maxOutputTokens,
        webSearch:
          useWebSearch,

        safeOriginalMessage:
          safeAgentMessage,

        allowServer:
          session.role ===
            "owner" ||
          Boolean(
            session.features
              ?.server
          ),

        protectedValues:
          privacy.totalFindings,

        privacy: {
          disabled:privacy.disabled === true,
          protected:
            privacy.wasSanitized,

          count:
            privacy.totalFindings,

          types:
            privacy.findings.map(
              (item) =>
                item.type
            )
        }
      }
    });

  /*
   * Keep today's UI behavior while the page stays open.
   * The crucial difference is that execution is already owned
   * by the worker, so browser disconnects no longer cancel it.
   */
  return Response.json(
    {
      ok: true,
      background: true,
      jobId,
      conversationId,
      userMessage: {
        id: userMessageId,
        content: await restorePrivateValues({
          conversationId,
          text: safeMessage
        })
      },
      message: null,
      progress: {
        stage: "queued",
        message: "Vector is working in the background"
      }
    },
    {
      status: 202
    }
  );
}

