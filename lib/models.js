export const MODEL_PRICING = {
  "gpt-6-luna": {
    provider: "openai",

    inputPerMillionUsd: 0.10,

    cachedInputPerMillionUsd: 0.01,

    outputPerMillionUsd: 0.50
  },

  "gpt-6-sol": {
    provider: "openai",

    inputPerMillionUsd: 2.00,

    cachedInputPerMillionUsd: 0.20,

    outputPerMillionUsd: 10.00
  }
};

function envNumber(
  name,
  fallback
) {
  const value =
    Number(process.env[name]);

  return Number.isFinite(value)
    ? value
    : fallback;
}

export function usdToChf(
  usd
) {
  return (
    Number(usd) *
    envNumber(
      "USD_TO_CHF_RATE",
      0.85
    )
  );
}

export function calculateModelCost({
  model,
  inputTokens = 0,
  outputTokens = 0,
  cachedTokens = 0
}) {
  const pricing =
    MODEL_PRICING[model];

  if (!pricing) {
    return {
      usd: 0,
      chf: 0
    };
  }

  const uncachedInput =
    Math.max(
      0,
      Number(inputTokens) -
      Number(cachedTokens)
    );

  const inputUsd =
    (
      uncachedInput /
      1_000_000
    ) *
    pricing.inputPerMillionUsd;

  const cachedUsd =
    (
      Number(cachedTokens) /
      1_000_000
    ) *
    pricing.cachedInputPerMillionUsd;

  const outputUsd =
    (
      Number(outputTokens) /
      1_000_000
    ) *
    pricing.outputPerMillionUsd;

  const usd =
    inputUsd +
    cachedUsd +
    outputUsd;

  return {
    usd,
    chf: usdToChf(usd)
  };
}

export function estimateTokens(
  text
) {
  return Math.max(
    1,
    Math.ceil(
      String(text || "").length /
      4
    )
  );
}

export function estimateRequestCost({
  model,
  text,
  maxOutputTokens
}) {
  return calculateModelCost({
    model,

    inputTokens:
      estimateTokens(text),

    outputTokens:
      Number(maxOutputTokens || 0),

    cachedTokens: 0
  });
}
