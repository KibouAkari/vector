import { compareProviderCandidates } from "./model-broker-shadow.mjs";
import crypto from "node:crypto";

import {
  db,
  initializeDatabase
} from "./db";

import {
  MODEL_CATALOG,
  MODEL_CATALOG_VERSION,
  automaticPricingFor,
  chooseCatalogModel,
  classifyVectorTask,
  routingExplanation,
  scoreCatalogModel,
  getCatalogModel
} from "./model-intelligence";


const PROVIDERS = {
  openai: {
    label: "OpenAI",
    apiBase: "https://api.openai.com/v1",
    adapter: "openai-responses",
    priority: 10,
    supportsTools: true,
    supportsSearch: true
  },
  google: {
    label: "Google Gemini",
    apiBase: "https://generativelanguage.googleapis.com/v1beta/openai",
    adapter: "openai-chat",
    priority: 20,
    supportsTools: true,
    supportsSearch: false
  },
  anthropic: {
    label: "Anthropic",
    apiBase: "https://api.anthropic.com",
    adapter: "anthropic",
    priority: 20,
    supportsTools: true,
    supportsSearch: false
  },
  perplexity: {
    label: "Perplexity",
    apiBase: "https://api.perplexity.ai",
    adapter: "openai-chat",
    priority: 20,
    supportsTools: false,
    supportsSearch: true
  },
  xai: {
    label: "xAI",
    apiBase: "https://api.x.ai/v1",
    adapter: "openai-chat",
    priority: 20,
    supportsTools: true,
    supportsSearch: false
  },
  openrouter: {
    label: "OpenRouter",
    apiBase: "https://openrouter.ai/api/v1",
    adapter: "openai-chat",
    priority: 40,
    supportsTools: true,
    supportsSearch: false
  },
  local: {
    label: "Local / self-hosted",
    apiBase: process.env.VECTOR_LOCAL_MODEL_URL || "",
    adapter: "openai-chat",
    priority: 30,
    supportsTools: true,
    supportsSearch: false
  },
  custom: {
    label: "Custom OpenAI-compatible",
    apiBase: "",
    adapter: "openai-chat",
    priority: 50,
    supportsTools: true,
    supportsSearch: false
  }
};

const AUTO_PROVIDERS = new Set([
  "openai",
  "google",
  "anthropic",
  "perplexity",
  "xai"
]);

export function providerDefaults(provider) {
  return PROVIDERS[String(provider || "").toLowerCase()] || PROVIDERS.custom;
}

export function providerSupportsAutomaticModel(provider) {
  return AUTO_PROVIDERS.has(String(provider || "").toLowerCase());
}

function key() {
  const raw = process.env.FILE_ENCRYPTION_KEY;
  if (!raw) throw new Error("FILE_ENCRYPTION_KEY missing.");

  const result = Buffer.from(raw, "hex");
  if (result.length !== 32) throw new Error("Invalid encryption key.");
  return result;
}

export function encryptSecret(value) {
  if (!value) return null;

  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key(), iv);
  const encrypted = Buffer.concat([
    cipher.update(String(value), "utf8"),
    cipher.final()
  ]);
  const tag = cipher.getAuthTag();

  return Buffer.concat([iv, tag, encrypted]).toString("base64");
}

export function decryptSecret(value) {
  if (!value) return null;

  const buffer = Buffer.from(value, "base64");
  const iv = buffer.subarray(0, 12);
  const tag = buffer.subarray(12, 28);
  const encrypted = buffer.subarray(28);
  const decipher = crypto.createDecipheriv("aes-256-gcm", key(), iv);
  decipher.setAuthTag(tag);

  return Buffer.concat([
    decipher.update(encrypted),
    decipher.final()
  ]).toString("utf8");
}

async function seedModelBenchmarks() {
  await db.query(`
    CREATE TABLE IF NOT EXISTS model_benchmarks (
      provider TEXT NOT NULL,
      model TEXT NOT NULL,
      label TEXT NOT NULL,
      benchmark_version TEXT NOT NULL,
      benchmark_date DATE NOT NULL,
      scores JSONB NOT NULL DEFAULT '{}'::jsonb,
      speed_score NUMERIC NOT NULL DEFAULT 0,
      cost_score NUMERIC NOT NULL DEFAULT 0,
      reliability_score NUMERIC NOT NULL DEFAULT 0,
      input_price_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
      cached_input_price_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
      output_price_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
      request_fee_usd NUMERIC(12,6) NOT NULL DEFAULT 0,
      source TEXT,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (provider, model)
    );
  `);

  for (const item of MODEL_CATALOG) {
    await db.query(
      `
        INSERT INTO model_benchmarks (
          provider, model, label, benchmark_version, benchmark_date,
          scores, speed_score, cost_score, reliability_score,
          input_price_usd, cached_input_price_usd, output_price_usd,
          request_fee_usd, source, updated_at
        )
        VALUES (
          $1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10,$11,$12,$13,$14,NOW()
        )
        ON CONFLICT (provider, model)
        DO UPDATE SET
          label = EXCLUDED.label,
          benchmark_version = EXCLUDED.benchmark_version,
          benchmark_date = EXCLUDED.benchmark_date,
          scores = EXCLUDED.scores,
          speed_score = EXCLUDED.speed_score,
          cost_score = EXCLUDED.cost_score,
          reliability_score = EXCLUDED.reliability_score,
          input_price_usd = EXCLUDED.input_price_usd,
          cached_input_price_usd = EXCLUDED.cached_input_price_usd,
          output_price_usd = EXCLUDED.output_price_usd,
          request_fee_usd = EXCLUDED.request_fee_usd,
          source = EXCLUDED.source,
          updated_at = NOW()
      `,
      [
        item.provider,
        item.model,
        item.label,
        MODEL_CATALOG_VERSION,
        MODEL_CATALOG_VERSION,
        JSON.stringify(item.scores || {}),
        item.speed || 0,
        item.cost || 0,
        item.reliability || 0,
        item.input || 0,
        item.cached || 0,
        item.output || 0,
        item.requestFee || 0,
        item.source || null
      ]
    );
  }
}

export async function initializeModelConfigs() {
  await initializeDatabase();

  await db.query(`
    CREATE TABLE IF NOT EXISTS model_providers (
      id TEXT PRIMARY KEY,
      provider TEXT NOT NULL,
      label TEXT NOT NULL,
      api_base TEXT,
      api_key_encrypted TEXT,
      default_model TEXT,
      enabled BOOLEAN NOT NULL DEFAULT TRUE,
      shared_data BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS priority INTEGER NOT NULL DEFAULT 100;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS quick_enabled BOOLEAN NOT NULL DEFAULT TRUE;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS normal_enabled BOOLEAN NOT NULL DEFAULT TRUE;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS deep_enabled BOOLEAN NOT NULL DEFAULT TRUE;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS research_enabled BOOLEAN NOT NULL DEFAULT TRUE;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS supports_tools BOOLEAN NOT NULL DEFAULT TRUE;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS supports_search BOOLEAN NOT NULL DEFAULT FALSE;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS input_price_usd NUMERIC(12,6) NOT NULL DEFAULT 0;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS cached_input_price_usd NUMERIC(12,6) NOT NULL DEFAULT 0;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS output_price_usd NUMERIC(12,6) NOT NULL DEFAULT 0;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS auto_model BOOLEAN NOT NULL DEFAULT TRUE;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS owner_user_id TEXT;
    ALTER TABLE model_providers ADD COLUMN IF NOT EXISTS shared_with_users BOOLEAN NOT NULL DEFAULT FALSE;

    CREATE INDEX IF NOT EXISTS idx_model_providers_owner_user
      ON model_providers (owner_user_id);

    CREATE INDEX IF NOT EXISTS idx_model_providers_shared
      ON model_providers (shared_with_users)
      WHERE shared_with_users = TRUE;
  `);

  /*
   * Before 5.6.3 providers were global. Assign every legacy provider to the
   * first owner account so existing credentials never become visible to,
   * or implicitly owned by, another user.
   */
  const ownerResult = await db.query(`
    SELECT id
    FROM vector_users
    WHERE role = 'owner'
    ORDER BY created_at ASC
    LIMIT 1
  `);

  const ownerUserId = ownerResult.rows[0]?.id || null;

  if (ownerUserId) {
    await db.query(
      `
        UPDATE model_providers
        SET owner_user_id = $1
        WHERE owner_user_id IS NULL
      `,
      [ownerUserId]
    );
  }

  if (process.env.OPENAI_API_KEY && ownerUserId) {
    const existing = await db.query(
      `
        SELECT id
        FROM model_providers
        WHERE
          provider = 'openai'
          AND owner_user_id = $1
        LIMIT 1
      `,
      [ownerUserId]
    );

    if (existing.rowCount === 0) {
      await db.query(
        `
          INSERT INTO model_providers (
            id, provider, label, api_base, api_key_encrypted,
            default_model, enabled, shared_data, priority,
            quick_enabled, normal_enabled, deep_enabled, research_enabled,
            supports_tools, supports_search, auto_model,
            owner_user_id, shared_with_users
          )
          VALUES (
            $1,'openai','OpenAI · Vector default','https://api.openai.com/v1',$2,
            NULL,TRUE,FALSE,10,TRUE,TRUE,TRUE,TRUE,TRUE,TRUE,TRUE,
            $3,FALSE
          )
        `,
        [
          crypto.randomUUID(),
          encryptSecret(process.env.OPENAI_API_KEY),
          ownerUserId
        ]
      );
    }
  }

  // Built-in providers use benchmark-aware automatic model selection by default.
  await db.query(`
    UPDATE model_providers
    SET
      quick_enabled = TRUE,
      normal_enabled = TRUE,
      deep_enabled = TRUE,
      research_enabled = TRUE,
      auto_model = TRUE
    WHERE provider IN ('openai','google','anthropic','perplexity','xai');
  `);

  await seedModelBenchmarks();
}

function runtimeModelForRow(row, task, mode) {
  const auto = Boolean(row.auto_model) && providerSupportsAutomaticModel(row.provider);

  if (!auto && row.default_model) {
    return {
      model: row.default_model,
      profile: getCatalogModel(row.provider, row.default_model),
      automatic: false
    };
  }

  const profile = chooseCatalogModel({
    provider: row.provider,
    task,
    mode
  });

  if (profile) {
    return {
      model: profile.model,
      profile,
      automatic: true
    };
  }

  if (row.default_model) {
    return {
      model: row.default_model,
      profile: null,
      automatic: false
    };
  }

  throw new Error(`${row.label} needs a Model ID because Vector has no automatic catalog for this provider.`);
}

function rowToRuntime(row, {
  mode = "normal",
  task = null
} = {}) {
  const defaults = providerDefaults(row.provider);
  const selected = runtimeModelForRow(row, task, mode);
  const apiKey = row.api_key_encrypted ? decryptSecret(row.api_key_encrypted) : null;

  if (row.provider !== "local" && !apiKey) {
    throw new Error(`${row.label} has no API key configured.`);
  }

  const automaticPricing = automaticPricingFor(row.provider, selected.model);
  const manualPricing = {
    inputPerMillionUsd: Number(row.input_price_usd || 0),
    cachedInputPerMillionUsd: Number(row.cached_input_price_usd || 0),
    outputPerMillionUsd: Number(row.output_price_usd || 0),
    requestFeeUsd: 0
  };

  const hasManualPricing =
    manualPricing.inputPerMillionUsd > 0 ||
    manualPricing.cachedInputPerMillionUsd > 0 ||
    manualPricing.outputPerMillionUsd > 0;

  return {
    id: row.id,
    provider: row.provider,
    label: row.label,
    adapter: defaults.adapter,
    apiBase: row.api_base || defaults.apiBase,
    apiKey,
    model: selected.model,
    automaticModel: selected.automatic,
    mode,
    priority: Number(row.priority || defaults.priority || 100),
    supportsTools: Boolean(row.supports_tools),
    supportsSearch: Boolean(row.supports_search),
    benchmarkProfile: selected.profile || null,
    taskType: task?.primary || "general",
    routingReason: routingExplanation(task),
    pricing: hasManualPricing
      ? manualPricing
      : (automaticPricing || manualPricing),
    credentialOwnerUserId: row.owner_user_id || null,
    sharedCredential: Boolean(row.shared_with_users)
  };
}

async function getAccountContext(userId) {
  if (!userId) {
    return {
      userId: null,
      role: null
    };
  }

  const result = await db.query(
    `
      SELECT id, role
      FROM vector_users
      WHERE id = $1
      LIMIT 1
    `,
    [userId]
  );

  return {
    userId,
    role: result.rows[0]?.role || null
  };
}

export async function getProviderRuntimeById(id, options = {}) {
  await initializeModelConfigs();

  const userId =
    options.userId ||
    null;

  if (!userId) {
    throw new Error("User identity is required for provider access.");
  }

  const account =
    await getAccountContext(
      userId
    );

  const result = await db.query(
    `
      SELECT
        p.*,
        owner.role AS owner_role
      FROM model_providers p
      LEFT JOIN vector_users owner
        ON owner.id = p.owner_user_id
      WHERE
        p.id = $1
        AND (
          p.owner_user_id = $2
          OR (
            $3 = TRUE
            AND p.shared_with_users = TRUE
            AND owner.role = 'owner'
          )
        )
      LIMIT 1
    `,
    [
      id,
      userId,
      Boolean(options.allowShared)
    ]
  );

  if (result.rowCount === 0) {
    throw new Error("Provider not found or not available to this account.");
  }

  const task = classifyVectorTask({
    message: options.taskText || "General capability test",
    mode: options.mode || "normal",
    requireSearch: Boolean(options.requireSearch),
    requireTools: Boolean(options.requireTools)
  });

  const runtime = rowToRuntime(result.rows[0], {
    mode: options.mode || "normal",
    task
  });

  return {
    ...runtime,
    credentialScope:
      result.rows[0].owner_user_id === userId
        ? "personal"
        : "workspace",
    accountRole:
      account.role
  };
}

function scoreRuntime(runtime, task, mode) {
  let score = 70;

  if (runtime.benchmarkProfile) {
    score = scoreCatalogModel(runtime.benchmarkProfile, task, mode);
  }

  // Manual priority remains only a tiny tie-breaker for legacy/custom rows.
  score -= Math.min(5, Math.max(0, Number(runtime.priority || 100) / 100));
  return score;
}

export async function resolveProviderForTask({
  mode = "normal",
  requireSearch = false,
  requireTools = false,
  requireVision = false,
  preferredProviderId = null,
  shadowComparison = false,
  excludeProviderIds = [],
  excludeProviders = [],
  taskText = "",
  userId = null
}) {
  await initializeModelConfigs();

  if (!userId) {
    throw new Error(
      "Vector cannot route a model request without an authenticated user."
    );
  }

  const account =
    await getAccountContext(
      userId
    );

  if (!account.role) {
    throw new Error(
      "The requesting Vector account no longer exists."
    );
  }

  /*
   * Tenant boundary:
   *
   * - Owners only use their own provider credentials.
   * - Members use their own credentials plus provider credentials that an
   *   owner explicitly marked "Share with users".
   * - A member can never see or use another member's key.
   */
  const result = await db.query(
    `
      SELECT
        p.*,
        owner.role AS owner_role
      FROM model_providers p
      LEFT JOIN vector_users owner
        ON owner.id = p.owner_user_id
      WHERE
        p.enabled = TRUE
        AND (
          p.owner_user_id = $1
          OR (
            $2 <> 'owner'
            AND p.shared_with_users = TRUE
            AND owner.role = 'owner'
          )
        )
      ORDER BY
        p.created_at ASC
    `,
    [
      userId,
      account.role
    ]
  );

  let rows = result.rows;

  /*
   * VECTOR_PROVIDER_EXCLUSION_57713
   * VECTOR_PROVIDER_FAMILY_EXCLUSION_57716
   *
   * Bounded Auto failover may exclude both:
   *
   *   - one exact provider configuration ID
   *   - the entire provider family
   *
   * Example:
   *   Google credential A fails with transient 503.
   *   Credential A and family "google" are excluded.
   *   The next routing pass must therefore select a
   *   different provider family such as Anthropic/OpenAI.
   *
   * Tenant/provider visibility filtering remains authoritative
   * and has already happened before this block.
   */
  const excludedProviderIds =
    new Set(
      (
        Array.isArray(
          excludeProviderIds
        )
          ? excludeProviderIds
          : []
      )
        .map(
          (id) =>
            String(
              id ||
              ""
            )
        )
        .filter(
          Boolean
        )
    );

  const excludedProviders =
    new Set(
      (
        Array.isArray(
          excludeProviders
        )
          ? excludeProviders
          : []
      )
        .map(
          (provider) =>
            String(
              provider ||
              ""
            )
              .trim()
              .toLowerCase()
        )
        .filter(
          Boolean
        )
    );

  if (
    excludedProviderIds.size >
      0 ||
    excludedProviders.size >
      0
  ) {
    rows =
      rows.filter(
        (row) => {
          const rowId =
            String(
              row.id ||
              ""
            );

          const rowProvider =
            String(
              row.provider ||
              ""
            )
              .trim()
              .toLowerCase();

          return (
            !excludedProviderIds.has(
              rowId
            ) &&
            !excludedProviders.has(
              rowProvider
            )
          );
        }
      );
  }

    /*
     * VECTOR_VISION_ROUTING_572
     * Phase 5.7.2 uses the native OpenAI Responses path for images.
     */
    if (requireVision) {
      rows =
        rows.filter(
          (row) =>
            String(
              row.provider ||
              ""
            ).toLowerCase() ===
            "openai"
        );

      if (rows.length === 0) {
        throw new Error(
          "Image understanding currently requires an enabled OpenAI provider available to this Vector account."
        );
      }
    }


  if (requireTools) {
    rows = rows.filter(
      (row) =>
        row.supports_tools
    );
  }

  if (requireSearch) {
    const searchCapable =
      rows.filter(
        (row) =>
          row.supports_search
      );

    if (searchCapable.length > 0) {
      rows = searchCapable;
    }
  }

  const task = classifyVectorTask({
    message: taskText,
    mode,
    requireSearch,
    requireTools
  });

  const candidates = [];
  const errors = [];

  for (const row of rows) {
    try {
      const runtime =
        rowToRuntime(
          row,
          {
            mode,
            task
          }
        );

      let score =
        scoreRuntime(
          runtime,
          task,
          mode
        );

      /*
       * Prefer a user's own credential when two candidates are otherwise
       * close. Benchmark quality still wins when a shared provider is
       * materially better for the requested task.
       */
      const personal =
        row.owner_user_id ===
        userId;

      if (personal) {
        score += 1.5;
      }

      if (
        preferredProviderId &&
        runtime.id ===
          preferredProviderId
      ) {
        score += 100;
      }

      candidates.push({
        runtime: {
          ...runtime,
          credentialScope:
            personal
              ? "personal"
              : "workspace"
        },
        score
      });

    } catch (error) {
      errors.push(
        error.message
      );
    }
  }

  candidates.sort(
    (a, b) =>
      b.score -
      a.score
  );

  // Shadow comparison after existing tenant and capability filters.
  // An exception must never affect normal provider selection.
  if (
    process.env.VECTOR_MODEL_BROKER_SHADOW === "1" &&
    shadowComparison === true &&
    candidates.length > 0
  ) {
    try {
      const comparison = compareProviderCandidates({
        candidates,
        mode,
        task,
        preferredProviderId
      });

      if (comparison.status === "compared") {
        console.info(
          "[vector-broker-shadow]",
          JSON.stringify(comparison)
        );
      }
    } catch {
      console.warn(
        "[vector-broker-shadow] Comparison unavailable"
      );
    }
  }

  if (!candidates.length) {
    throw new Error(
      errors[0] ||
      (
        account.role === "owner"
          ? "No enabled model provider is available. Add an API in Models & APIs."
          : "No model API is available for your account. Add your own API key in Models & APIs or ask the owner to share a provider."
      )
    );
  }

  return {
    ...candidates[0].runtime,
    routingScore:
      candidates[0].score,
    routingCandidates:
      candidates
        .slice(
          0,
          3
        )
        .map(
          (candidate) => ({
            provider:
              candidate.runtime
                .provider,
            label:
              candidate.runtime
                .label,
            model:
              candidate.runtime
                .model,
            credentialScope:
              candidate.runtime
                .credentialScope,
            score:
              Number(
                candidate.score
                  .toFixed(
                    2
                  )
              )
          })
        )
  };
}

export function calculateConfiguredProviderCost({
  providerRuntime,
  inputTokens = 0,
  outputTokens = 0,
  cachedTokens = 0,
  usdToChfRate = 0.85
}) {
  const pricing = providerRuntime?.pricing || {};
  const cached = Math.max(0, Number(cachedTokens || 0));
  const uncached = Math.max(0, Number(inputTokens || 0) - cached);

  const usd =
    (uncached / 1_000_000) * Number(pricing.inputPerMillionUsd || 0) +
    (cached / 1_000_000) * Number(pricing.cachedInputPerMillionUsd || 0) +
    (Number(outputTokens || 0) / 1_000_000) * Number(pricing.outputPerMillionUsd || 0) +
    Number(pricing.requestFeeUsd || 0);

  return {
    usd,
    chf: usd * Number(usdToChfRate || 0.85)
  };
}
