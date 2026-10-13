import {
  getSession
} from "../../../../lib/auth";

import {
  db
} from "../../../../lib/db";

import {
  encryptSecret,
  initializeModelConfigs,
  providerDefaults,
  providerSupportsAutomaticModel
} from "../../../../lib/model-config";


function cleanEndpoint(
  value,
  provider,
  fallback
) {
  const endpoint =
    String(
      value ||
      fallback ||
      ""
    ).trim();

  if (!endpoint) {
    return null;
  }

  let parsed;

  try {
    parsed =
      new URL(
        endpoint
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
    ) ||
    parsed.username ||
    parsed.password
  ) {
    throw new Error(
      "Invalid API endpoint."
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

  return endpoint.replace(
    /\/+$/,
    ""
  );
}


async function ownedProvider(
  id,
  userId
) {
  return db.query(
    `
      SELECT *
      FROM model_providers
      WHERE
        id = $1
        AND
        owner_user_id = $2
      LIMIT 1
    `,
    [
      id,
      userId
    ]
  );
}


export async function PATCH(
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
    id
  } =
    await context.params;

  const body =
    await request.json();

  await initializeModelConfigs();

  const current =
    await ownedProvider(
      id,
      session.userId
    );

  if (
    current.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "Provider not found."
      },
      {
        status: 404
      }
    );
  }

  const existing =
    current.rows[0];

  const defaults =
    providerDefaults(
      existing.provider
    );

  const autoSupported =
    providerSupportsAutomaticModel(
      existing.provider
    );

  const model =
    body.defaultModel !==
      undefined
      ? String(
          body.defaultModel ||
          ""
        )
          .trim()
          .slice(
            0,
            160
          )
      : String(
          existing.default_model ||
          ""
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

  let apiBase;

  try {
    apiBase =
      cleanEndpoint(
        body.apiBase !==
          undefined
          ? body.apiBase
          : existing.api_base,
        existing.provider,
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

  const encryptedKey =
    body.apiKey
      ? encryptSecret(
          body.apiKey
        )
      : existing.api_key_encrypted;

  await db.query(
    `
      UPDATE model_providers
      SET
        label = $3,
        api_base = $4,
        api_key_encrypted = $5,
        default_model = $6,
        auto_model = $7,
        enabled = $8,
        priority = $9,
        quick_enabled = TRUE,
        normal_enabled = TRUE,
        deep_enabled = TRUE,
        research_enabled = TRUE,
        supports_tools = $10,
        supports_search = $11,
        shared_with_users = $12,
        updated_at = NOW()

      WHERE
        id = $1
        AND
        owner_user_id = $2
    `,
    [
      id,
      session.userId,
      body.label !==
        undefined
        ? (
            String(
              body.label ||
              ""
            )
              .trim()
              .slice(
                0,
                100
              ) ||
            defaults.label
          )
        : existing.label,
      apiBase,
      encryptedKey,
      model ||
        null,
      autoModel,
      body.enabled !==
        undefined
        ? Boolean(
            body.enabled
          )
        : existing.enabled,
      defaults.priority ||
        existing.priority ||
        100,
      defaults.supportsTools,
      defaults.supportsSearch,
      session.role ===
        "owner"
        ? (
            body.sharedWithUsers !==
              undefined
              ? Boolean(
                  body.sharedWithUsers
                )
              : Boolean(
                  existing.shared_with_users
                )
          )
        : false
    ]
  );

  return Response.json({
    ok: true
  });
}


export async function DELETE(
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
    id
  } =
    await context.params;

  await initializeModelConfigs();

  const result =
    await db.query(
      `
        DELETE FROM model_providers
        WHERE
          id = $1
          AND
          owner_user_id = $2
        RETURNING id
      `,
      [
        id,
        session.userId
      ]
    );

  if (
    result.rowCount ===
    0
  ) {
    return Response.json(
      {
        error:
          "Provider not found."
      },
      {
        status: 404
      }
    );
  }

  return Response.json({
    ok: true
  });
}
