import crypto from "node:crypto";

import {
  getSession,
  hasFeature
} from "../../../lib/auth";

import {
  db
} from "../../../lib/db";

import {
  encryptSecret,
  getProviderRuntimeById,
  initializeModelConfigs,
  providerDefaults,
  providerSupportsAutomaticModel,
  resolveProviderForTask
} from "../../../lib/model-config";


const ALLOWED = new Set([
  "openai",
  "google",
  "anthropic",
  "perplexity",
  "xai",
  "openrouter",
  "local",
  "custom"
]);


function cleanApiBase(
  value,
  provider,
  fallback
) {
  const base =
    String(
      value ||
      fallback ||
      ""
    ).trim();

  if (!base) {
    return null;
  }

  let parsed;

  try {
    parsed =
      new URL(
        base
      );
  } catch {
    throw new Error(
      "API endpoint must be a valid URL."
    );
  }

  if (
    ![
      "http:",
      "https:"
    ].includes(
      parsed.protocol
    )
  ) {
    throw new Error(
      "API endpoint must use HTTP or HTTPS."
    );
  }

  if (
    parsed.username ||
    parsed.password
  ) {
    throw new Error(
      "Do not put credentials in the API endpoint."
    );
  }

  if (
    ![
      "local",
      "custom"
    ].includes(
      provider
    ) &&
    parsed.protocol !==
      "https:"
  ) {
    throw new Error(
      "External providers must use HTTPS."
    );
  }

  return base.replace(
    /\/+$/,
    ""
  );
}


const PREVIEW_TASKS = [
  {
    id: "everyday",
    label: "Everyday",
    mode: "quick",
    text:
      "Answer a short everyday question clearly and accurately."
  },
  {
    id: "coding",
    label: "Coding",
    mode: "normal",
    text:
      "Implement and debug production code in a software project.",
    tools: true
  },
  {
    id: "deep",
    label: "Complex work",
    mode: "deep",
    text:
      "Perform a difficult architecture analysis with careful reasoning.",
    tools: true
  },
  {
    id: "research",
    label: "Live research",
    mode: "research",
    text:
      "Research the latest information online and cite reliable sources.",
    search: true
  },
  {
    id: "humanities",
    label: "Human / philosophy",
    mode: "normal",
    text:
      "Discuss a philosophical, religious and human question thoughtfully."
  }
];


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
        status: 401
      }
    );
  }

  if (!hasFeature(session, "models")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  await initializeModelConfigs();

  const result =
    await db.query(
      `
        SELECT
          p.id,
          p.provider,
          p.label,
          CASE
            WHEN p.owner_user_id = $1
              THEN p.api_base
            ELSE NULL
          END AS api_base,
          p.default_model,
          p.auto_model,
          p.enabled,
          p.supports_tools,
          p.supports_search,
          p.shared_with_users,
          p.owner_user_id,
          p.api_key_encrypted IS NOT NULL
            AS has_api_key,
          owner.role
            AS owner_role,
          p.created_at,
          p.updated_at

        FROM model_providers p

        LEFT JOIN vector_users owner
          ON owner.id =
            p.owner_user_id

        WHERE
          p.owner_user_id = $1
          OR (
            $2 <> 'owner'
            AND
            p.shared_with_users = TRUE
            AND
            owner.role = 'owner'
          )

        ORDER BY
          CASE
            WHEN p.owner_user_id = $1
              THEN 0
            ELSE 1
          END,
          p.created_at ASC
      `,
      [
        session.userId,
        session.role
      ]
    );

  const providers = [];

  for (
    const row
    of result.rows
  ) {
    const personal =
      row.owner_user_id ===
      session.userId;

    let recommendedModel =
      row.default_model ||
      null;

    if (
      row.auto_model
    ) {
      try {
        const runtime =
          await getProviderRuntimeById(
            row.id,
            {
              userId:
                session.userId,
              allowShared:
                !personal,
              mode:
                "normal",
              taskText:
                "General professional work"
            }
          );

        recommendedModel =
          runtime.model;

      } catch {
        // Provider cards must still render when a credential/model is invalid.
      }
    }

    const automaticSupported =
      providerSupportsAutomaticModel(
        row.provider
      );

    providers.push({
      id:
        row.id,
      provider:
        row.provider,
      label:
        row.label,
      api_base:
        personal
          ? row.api_base
          : null,
      default_model:
        row.default_model,
      auto_model:
        Boolean(
          row.auto_model
        ) &&
        automaticSupported,
      enabled:
        row.enabled,
      supports_tools:
        row.supports_tools,
      supports_search:
        row.supports_search,
      has_api_key:
        personal
          ? row.has_api_key
          : true,
      shared_with_users:
        Boolean(
          row.shared_with_users
        ),
      recommended_model:
        recommendedModel,
      automatic_supported:
        automaticSupported,
      credential_scope:
        personal
          ? "personal"
          : "workspace",
      editable:
        personal,
      created_at:
        row.created_at,
      updated_at:
        row.updated_at
    });
  }

  const recommendations = [];

  for (
    const task
    of PREVIEW_TASKS
  ) {
    try {
      const runtime =
        await resolveProviderForTask({
          userId:
            session.userId,
          mode:
            task.mode,
          taskText:
            task.text,
          requireSearch:
            Boolean(
              task.search
            ),
          requireTools:
            Boolean(
              task.tools
            )
        });

      recommendations.push({
        id:
          task.id,
        label:
          task.label,
        provider:
          runtime.label,
        model:
          runtime.model,
        taskType:
          runtime.taskType,
        credentialScope:
          runtime.credentialScope
      });

    } catch (
      error
    ) {
      recommendations.push({
        id:
          task.id,
        label:
          task.label,
        error:
          error.message
      });
    }
  }

  return Response.json({
    role:
      session.role,
    providers,
    recommendations
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

  if (!hasFeature(session, "models")) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  await initializeModelConfigs();

  const body =
    await request.json();

  const provider =
    String(
      body.provider ||
      ""
    )
      .trim()
      .toLowerCase();

  if (
    !ALLOWED.has(
      provider
    )
  ) {
    return Response.json(
      {
        error:
          "Unsupported provider."
      },
      {
        status: 400
      }
    );
  }

  const defaults =
    providerDefaults(
      provider
    );

  const autoSupported =
    providerSupportsAutomaticModel(
      provider
    );

  const model =
    String(
      body.defaultModel ||
      ""
    )
      .trim()
      .slice(
        0,
        160
      );

  const autoModel =
    autoSupported &&
    !model;

  if (
    !autoSupported &&
    !model
  ) {
    return Response.json(
      {
        error:
          "Model ID is required for OpenRouter, local and custom providers."
      },
      {
        status: 400
      }
    );
  }

  if (
    provider !==
      "local" &&
    !String(
      body.apiKey ||
      ""
    ).trim()
  ) {
    return Response.json(
      {
        error:
          "API key is required."
      },
      {
        status: 400
      }
    );
  }

  let apiBase;

  try {
    apiBase =
      cleanApiBase(
        body.apiBase,
        provider,
        defaults.apiBase
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
        status: 400
      }
    );
  }

  const label =
    String(
      body.label ||
      defaults.label
    )
      .trim()
      .slice(
        0,
        100
      ) ||
    defaults.label;

  const id =
    crypto.randomUUID();

  await db.query(
    `
      INSERT INTO model_providers (
        id,
        provider,
        label,
        api_base,
        api_key_encrypted,
        default_model,
        auto_model,
        enabled,
        shared_data,
        priority,
        quick_enabled,
        normal_enabled,
        deep_enabled,
        research_enabled,
        supports_tools,
        supports_search,
        input_price_usd,
        cached_input_price_usd,
        output_price_usd,
        owner_user_id,
        shared_with_users
      )
      VALUES (
        $1,$2,$3,$4,$5,$6,$7,$8,FALSE,$9,
        TRUE,TRUE,TRUE,TRUE,$10,$11,0,0,0,
        $12,$13
      )
    `,
    [
      id,
      provider,
      label,
      apiBase,
      body.apiKey
        ? encryptSecret(
            body.apiKey
          )
        : null,
      model ||
        null,
      autoModel,
      body.enabled !==
        false,
      defaults.priority ||
        100,
      defaults.supportsTools,
      defaults.supportsSearch,
      session.userId,
      session.role ===
        "owner"
        ? Boolean(
            body.sharedWithUsers
          )
        : false
    ]
  );

  return Response.json({
    ok: true,
    id
  });
}
