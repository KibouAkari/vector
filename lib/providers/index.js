import {
  callOpenAI
} from "../openai";

export function availableProviders() {
  return {
    openai: {
      configured:
        Boolean(
          process.env
            .OPENAI_API_KEY
        )
    },

    gemini: {
      configured:
        Boolean(
          process.env
            .GOOGLE_GENERATIVE_AI_API_KEY
        )
    },

    perplexity: {
      configured:
        Boolean(
          process.env
            .PERPLEXITY_API_KEY
        )
    },

    xai: {
      configured:
        Boolean(
          process.env
            .XAI_API_KEY
        )
    },

    local: {
      configured:
        Boolean(
          process.env
            .VECTOR_LOCAL_MODEL_URL
        )
    }
  };
}

export async function executeModel({
  provider = "openai",
  ...options
}) {
  if (
    provider === "openai"
  ) {
    return callOpenAI(
      options
    );
  }

  throw new Error(
    `Provider '${provider}' is not enabled yet.`
  );
}
