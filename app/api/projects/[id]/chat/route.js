import {reviewPrivacyRequest} from '../../../../../lib/privacy-review';
import crypto from "node:crypto";

import {
  getSession
} from "../../../../../lib/auth";

import {
  db,
  initializeDatabase
} from "../../../../../lib/db";

import {
  sanitizeForExternal
} from "../../../../../lib/privacy";

import {
  savePrivacyMappings,
  restorePrivateValues
} from "../../../../../lib/privacy-vault";

import {
  searchProjectChunks
} from "../../../../../lib/project-index";

import {
  determineTaskMode,
  getMaximumOutputTokens,
  getModelForMode,
  shouldUseWebSearch
} from "../../../../../lib/router";

import {
  estimateRequestCost,
  usdToChf
} from "../../../../../lib/models";

import {
  checkCost
} from "../../../../../lib/cost";

import {
  assertUserBudget,
  canAccessProject
} from "../../../../../lib/identity";

import {
  enqueueAgentJob,
  findRecentDuplicate,
  makeRequestHash,
  waitForAgentJob
} from "../../../../../lib/background-jobs";

export const runtime =
  "nodejs";


function titleFromMessage(
  text
) {
  const clean =
    String(
      text || ""
    )
      .replace(
        /\s+/g,
        " "
      )
      .trim();

  return (
    clean.slice(
      0,
      55
    ) ||
    "Project chat"
  );
}


function privacyDisplay(mappings) {
  // Consent findings are displayed locally before submission. Durable job
  // metadata must never carry those originals or credential prefixes/suffixes.
  return mappings.map(mapping => ({
    type: mapping.type,
    placeholder: mapping.placeholder,
    displayValue: /PASSWORD|TOKEN|KEY/.test(mapping.type)
      ? '••••••••' : mapping.placeholder
  }));
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

      content:
        await restorePrivateValues({
          conversationId,
          text:
            result.text || ""
        })
    },

    retrieval:
      result.retrieval || [],

    privacy:
      result.privacy,

    meta:
      result.meta
  });
}


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

  const {
    id:
      projectId
  } = await context.params;

  if (
    !await canAccessProject(
      session,
      projectId
    )
  ) {
    return Response.json(
      {
        error:
          "Project not found."
      },
      {
        status: 404
      }
    );
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

  let conversationId =
    body.conversationId
      ? String(
          body.conversationId
        )
      : null;

  if (!originalMessage || originalMessage.length > 100000) {
    return Response.json(
      {
        error:
          "Message required."
      },
      {
        status: 400
      }
    );
  }

  await initializeDatabase();

  const projectResult =
    await db.query(
      `
        SELECT *
        FROM projects
        WHERE id = $1
      `,
      [
        projectId
      ]
    );

  if (
    projectResult.rowCount === 0
  ) {
    return Response.json(
      {
        error:
          "Project not found."
      },
      {
        status: 404
      }
    );
  }

  const project =
    projectResult.rows[0];

  const userBudget =
    await assertUserBudget(
      session
    );

  if (
    !userBudget.allowed && requestedMode !== 'local' && project.privacy_level !== 'local_only'
  ) {
    return Response.json(
      {
        error:
          "USER_BUDGET_BLOCKED",

        message:
          userBudget.reason
      },
      {
        status: 402
      }
    );
  }

  /*
   * VECTOR_PROJECT_CHAT_ISOLATION_563
   *
   * Sharing a project never shares chat transcripts.
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
            project_id = $2
            AND
            user_id = $3
          LIMIT 1
        `,
        [
          conversationId,
          projectId,
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
            "Conversation not found."
        },
        {
          status:
            404
        }
      );
    }
  }

  const chunks =
    await searchProjectChunks({
      projectId,
      query:
        originalMessage,
      limit: 10
    });

  const rawContext =
    chunks
      .map(
        (
          chunk,
          index
        ) =>
          `SOURCE ${index + 1}: ${chunk.original_name} lines ${chunk.start_line}-${chunk.end_line}\n${chunk.content}`
      )
      .join(
        "\n\n---\n\n"
      );

  const priorHistory = conversationId ? (await db.query(`SELECT role,content FROM messages
    WHERE conversation_id=$1 ORDER BY created_at DESC LIMIT 24`,[conversationId])).rows.reverse() : [];
  let privacy;
  try {
    privacy = await reviewPrivacyRequest({text:[originalMessage,rawContext,...priorHistory.map(m=>m.content)].join('\n\n'),
      scanSegments:[originalMessage,rawContext,...priorHistory.map(m=>m.content)],previewText:originalMessage,
      body,session,scope:'project:'+projectId,conversationId,
      destination:project.privacy_level==='local_only'||requestedMode==='local'?'local':'cloud'});
  } catch {
    return Response.json({error:'PRIVACY_REVIEW_FAILED',message:'Die lokale Datenschutzprüfung konnte nicht abgeschlossen werden. Es wurde nichts extern versendet. Bitte erneut prüfen oder den lokalen Textmodus wählen.'},
      {status:503,headers:{'Cache-Control':'no-store'}});
  }
  if (privacy.response) return privacy.response;
  const mappings = privacy.mappings;
  const safeMessage = privacy.apply(originalMessage);
  const safeContext = privacy.apply(rawContext);

  const mode = privacy.destination === 'local' ? 'local' : determineTaskMode({message:safeMessage,requestedMode});

  const model = privacy.destination === 'local' ? 'vector-qwen3:1.7b-q8' : getModelForMode(mode);

  const useWebSearch = privacy.destination !== 'local' && shouldUseWebSearch({
      message:
        safeMessage,
      requestedMode:
        mode
    });

  const maxOutputTokens =
    getMaximumOutputTokens(
      mode
    );

  const estimate =
    estimateRequestCost({
      model,
      text:
        safeMessage +
        safeContext,
      maxOutputTokens
    });

  const searchReserve =
    useWebSearch
      ? usdToChf(0.06)
      : 0;

  const taskBudget =
    mode === "deep"
      ? 0.40
      : mode === "research"
        ? 0.30
        : mode === "quick"
          ? 0.03
          : 0.10;

  const costDecision =
    await checkCost({
      estimatedCost:
        estimate.chf +
        searchReserve,
      taskBudget,
      taskSpent: 0
    });

  if (privacy.destination !== 'local' && !costDecision.allowed) {
    return Response.json(
      {
        error:
          "COST_BLOCKED",

        message:
          costDecision.reason
      },
      {
        status: 402
      }
    );
  }

  if (!conversationId) {
    conversationId = crypto.randomUUID();
    await db.query(`INSERT INTO conversations (id,project_id,owner_user_id,user_id,title)
      VALUES ($1,$2,$3,$3,$4)`,[conversationId,projectId,session.userId,titleFromMessage(safeMessage)]);
  }
  await savePrivacyMappings({conversationId,mappings});

  const requestHash =
    makeRequestHash({
      userId:
        session.userId,
      conversationId,
      message:safeMessage+'\nprivacy:'+privacy.destination+':'+(body.privacyEnabled===false?'off':body.privacyDecision||'replace')
    });

  const duplicate =
    await findRecentDuplicate({
      userId:
        session.userId,
      conversationId,
      requestHash
    });

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

  const history = [...priorHistory.map(row=>({role:row.role==='assistant'?'assistant':'user',
    content:privacy.apply(row.content)})),{role:'user',content:safeMessage}];

  if (
    safeContext
  ) {
    const lastIndex =
      history.length - 1;

    history[lastIndex] = {
      role:
        "user",

      content: [
        history[lastIndex]
          .content,
        "",
        "PROJECT CONTEXT RETRIEVED LOCALLY:",
        "Use this context when relevant.",
        "Do not claim a fact comes from a file unless it appears below.",
        "",
        safeContext
      ].join("\n")
    };
  }

  const jobId =
    await enqueueAgentJob({
      userId:
        session.userId,

      conversationId,
      projectId,
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
        projectId,
        model,
        mode,
        messages:
          history,
        maxOutputTokens,
        webSearch:
          useWebSearch,

        safeOriginalMessage:
          safeMessage,

        allowServer:
          session.role ===
            "owner" ||
          Boolean(
            session.features
              ?.server
          ),

        protectedValues:
          mappings.length,

        filesRetrieved:
          chunks.length,

        retrieval:
          chunks.map(
            (chunk) => ({
              file:
                privacy.apply(chunk.original_name),
              startLine:
                chunk.start_line,
              endLine:
                chunk.end_line
            })
          ),

        privacy: {
          protected:privacy.wasSanitized,

          values:
            privacyDisplay(
              mappings
            )
        }
      }
    });

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

