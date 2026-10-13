function sleep(
  milliseconds
) {
  return new Promise(
    (resolve) =>
      setTimeout(
        resolve,
        milliseconds
      )
  );
}

function parseRetryAfter(
  response,
  body,
  attempt
) {
  const header =
    response.headers.get(
      "retry-after"
    );

  if (header) {
    const seconds =
      Number(header);

    if (
      Number.isFinite(seconds) &&
      seconds >= 0
    ) {
      return (
        seconds *
        1000
      );
    }
  }

  const message =
    String(
      body?.error?.message ||
      ""
    );

  const match =
    message.match(
      /try again in\s+([\d.]+)s/i
    );

  if (match) {
    const seconds =
      Number(
        match[1]
      );

    if (
      Number.isFinite(seconds)
    ) {
      return (
        seconds *
        1000
      );
    }
  }

  /*
   * Exponential fallback:
   *
   * attempt 0 = 2 seconds
   * attempt 1 = 4 seconds
   * attempt 2 = 8 seconds
   */
  return (
    Math.pow(
      2,
      attempt + 1
    ) *
    1000
  );
}

async function openAIRequest({
  url,
  apiKey,
  payload
}) {
  const configuredRetries =
    Number(
      process.env
        .VECTOR_OPENAI_MAX_RETRIES ||
      3
    );

  const maxRetries =
    Number.isFinite(
      configuredRetries
    )
      ? Math.max(
          0,
          Math.min(
            configuredRetries,
            5
          )
        )
      : 3;

  for (
    let attempt = 0;
    attempt <= maxRetries;
    attempt += 1
  ) {
    const response =
      await fetch(
        url,
        {
          method:
            "POST",

          headers: {
            Authorization:
              `Bearer ${apiKey}`,

            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify(
              payload
            )
        }
      );

    let body;

    try {
      body =
        await response.json();
    } catch {
      body = {};
    }

    if (
      response.ok
    ) {
      return body;
    }

    const retryable =
      response.status === 429 ||
      response.status === 503;

    if (
      !retryable ||
      attempt >=
        maxRetries
    ) {
      throw new Error(
        body?.error?.message ||
        `OpenAI returned HTTP ${response.status}`
      );
    }

    const delay =
      parseRetryAfter(
        response,
        body,
        attempt
      );

    /*
     * Do not hold one HTTP request forever.
     *
     * Longer provider-side limits should be
     * retried by the user/task queue later.
     */
    if (
      delay >
      30000
    ) {
      throw new Error(
        `OpenAI temporarily rate limited this request. Retry-After is approximately ${Math.ceil(delay / 1000)} seconds.`
      );
    }

    const jitter =
      Math.floor(
        Math.random() *
        300
      );

    await sleep(
      delay +
      jitter
    );
  }

  throw new Error(
    "OpenAI request failed after retries."
  );
}

function collectSources(
  response
) {
  const sources = [];

  function addSource(
    source
  ) {
    if (
      !source ||
      !source.url
    ) {
      return;
    }

    if (
      sources.some(
        (existing) =>
          existing.url ===
          source.url
      )
    ) {
      return;
    }

    sources.push({
      title:
        source.title ||
        source.url,

      url:
        source.url
    });
  }

  for (
    const item
    of response.output || []
  ) {
    if (
      item.type ===
      "web_search_call"
    ) {
      const action =
        item.action;

      for (
        const source
        of action?.sources || []
      ) {
        addSource(
          source
        );
      }
    }

    if (
      item.type !==
      "message"
    ) {
      continue;
    }

    for (
      const content
      of item.content || []
    ) {
      for (
        const annotation
        of content.annotations || []
      ) {
        if (
          annotation.type !==
          "url_citation"
        ) {
          continue;
        }

        addSource({
          url:
            annotation.url,

          title:
            annotation.title
        });
      }
    }
  }

  return sources;
}

function extractResult(
  response
) {
  const textPieces = [];

  let webSearchCalls =
    0;

  const searchQueries = [];

  for (
    const item
    of response.output || []
  ) {
    if (
      item.type ===
      "web_search_call"
    ) {
      webSearchCalls += 1;

      const queries =
        item.action
          ?.queries;

      if (
        Array.isArray(
          queries
        )
      ) {
        for (
          const query
          of queries
        ) {
          if (
            query &&
            !searchQueries.includes(
              query
            )
          ) {
            searchQueries.push(
              query
            );
          }
        }
      }

      continue;
    }

    if (
      item.type !==
      "message"
    ) {
      continue;
    }

    for (
      const content
      of item.content || []
    ) {
      if (
        content.type ===
        "output_text" &&
        content.text
      ) {
        textPieces.push(
          content.text
        );
      }
    }
  }

  return {
    text:
      textPieces.join(
        "\n"
      ),

    citations:
      collectSources(
        response
      ),

    webSearchCalls,

    searchQueries
  };
}

function commonInstructions() {
  return [
    "You are Vector, a capable personal AI workspace.",
    "Your goal is to help the user complete useful real work.",
    "",
    "GENERAL STYLE:",
    "Answer naturally, professionally and directly.",
    "Do not restate the complete request.",
    "Prefer concrete information over generic AI prose.",
    "Use short sections and bullets only when they improve readability.",
    "Do not add a redundant conclusion after already answering.",
    "",
    "PRIVACY PLACEHOLDERS:",
    "Sensitive values may appear as placeholders such as <PRIVATE_IP_A1B2C3>, <EMAIL_A1B2C3>, <PASSWORD_A1B2C3>, <TOKEN_A1B2C3> or <API_KEY_A1B2C3>.",
    "These represent real locally stored values.",
    "Preserve every placeholder character-for-character whenever referring to it.",
    "Never rename or simplify a placeholder.",
    "Do not ask for the real value unless the task genuinely cannot be completed without it.",
    "Never attempt to guess the hidden value."
  ].join("\n");
}

function quickInstructions() {
  return [
    "QUICK MODE:",
    "Usually answer in 40 to 160 words.",
    "Answer immediately.",
    "Do not turn simple questions into essays."
  ].join("\n");
}

function normalInstructions() {
  return [
    "NORMAL MODE:",
    "Give a concise but substantive professional answer.",
    "Usually use roughly 180 to 450 words.",
    "Prefer two to four short sections for technical explanations.",
    "Give the practical difference before deeper technical detail.",
    "Do not pad the answer."
  ].join("\n");
}

function deepInstructions() {
  return [
    "DEEP MODE:",
    "Perform thorough reasoning and analysis.",
    "Cover important implementation details, trade-offs and edge cases.",
    "Avoid repetition.",
    "Depth is useful; padding is not."
  ].join("\n");
}

function researchInstructions() {
  return [
    "RESEARCH MODE:",
    "Perform a genuine multi-source web investigation.",
    "",
    "SEARCH PROCESS:",
    "Run multiple distinct searches where needed rather than relying on the first result.",
    "For a named project, company, person, product or community, search at least these angles when relevant:",
    "- the exact entity name",
    "- the entity name plus official",
    "- the entity name plus website",
    "- the entity name plus Discord/community/contact",
    "- the entity name plus creator/owner/operator",
    "- independent references to corroborate important facts",
    "",
    "Do not conclude that an official website or source does not exist merely because the first search did not show it.",
    "If a directory, server listing or aggregator is your only source, actively search for a primary source before answering.",
    "",
    "SOURCE PRIORITY:",
    "1. official websites and first-party documentation",
    "2. primary announcements or official social/community pages",
    "3. reputable independent sources",
    "4. directories and aggregators",
    "",
    "SYNTHESIS:",
    "Read enough context from sources to understand what they actually establish.",
    "Do not infer that two similarly named projects are unrelated merely because a source does not explicitly connect them.",
    "Instead search for evidence of the relationship.",
    "Cross-check important claims.",
    "Answer every part of the user's question.",
    "Clearly label uncertainty.",
    "Stay concise while including the important discovered details."
  ].join("\n");
}

function instructionsForMode(
  mode
) {
  if (
    mode ===
    "quick"
  ) {
    return quickInstructions();
  }

  if (
    mode ===
    "deep"
  ) {
    return deepInstructions();
  }

  if (
    mode ===
    "research"
  ) {
    return researchInstructions();
  }

  return normalInstructions();
}

export async function callOpenAI({
  model,
  mode,
  messages,
  maxOutputTokens,
  webSearch = false
}) {
  const apiKey =
    process.env
      .OPENAI_API_KEY;

  if (!apiKey) {
    throw new Error(
      "OpenAI API key is not configured."
    );
  }

  const payload = {
    model,

    store:
      false,

    max_output_tokens:
      maxOutputTokens,

    instructions: [
      commonInstructions(),
      "",
      instructionsForMode(
        mode
      )
    ].join("\n"),

    input:
      messages.map(
        (
          message
        ) => ({
          role:
            message.role,

          content:
            message.content
        })
      )
  };

  if (
    webSearch
  ) {
    payload.tools = [
      {
        type:
          "web_search",

        /*
         * Medium gives Vector useful page
         * context without generating the
         * huge TPM spikes seen with high +
         * unlimited on every research task.
         */
        search_context_size:
          "medium",

        external_web_access:
          true,

        /*
         * Keep provider default.
         * Unlimited is reserved for a future
         * explicit Deep Research workflow.
         */
        return_token_budget:
          "default"
      }
    ];

    payload.tool_choice =
      "required";

    /*
     * Return the complete list of sources
     * consulted, not just inline citations.
     */
    payload.include = [
      "web_search_call.action.sources"
    ];
  }

  const body =
    await openAIRequest({
      url:
        "https://api.openai.com/v1/responses",

      apiKey,

      payload
    });

  const result =
    extractResult(
      body
    );

  const usage =
    body.usage ||
    {};

  return {
    id:
      body.id,

    text:
      result.text,

    citations:
      result.citations,

    webSearchCalls:
      result.webSearchCalls,

    searchQueries:
      result.searchQueries,

    inputTokens:
      Number(
        usage.input_tokens ||
        0
      ),

    outputTokens:
      Number(
        usage.output_tokens ||
        0
      ),

    cachedTokens:
      Number(
        usage
          .input_tokens_details
          ?.cached_tokens ||
        0
      )
  };
}
