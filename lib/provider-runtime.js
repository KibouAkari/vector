import { observeProviderRequest } from "./provider-telemetry.js";
function baseUrl(
  value
) {
  return String(
    value ||
    ""
  )
    .trim()
    .replace(
      /\/+$/,
      ""
    );
}


function sleep(
  ms
) {
  return new Promise(
    (
      resolve
    ) =>
      setTimeout(
        resolve,
        ms
      )
  );
}


async function fetchJson(
  url,
  options,
  {
    retries = 2
  } = {}
) {
  let lastError = null;

  for (
    let attempt = 0;
    attempt <= retries;
    attempt += 1
  ) {
    let response;

    try {
      response =
        await fetch(
          url,
          options
        );
    } catch (
      error
    ) {
      lastError =
        error;

      if (
        attempt >= retries
      ) {
        throw error;
      }

      await sleep(
        700 *
        (
          attempt +
          1
        )
      );

      continue;
    }

    /*
     * VECTOR_PROVIDER_PAYLOAD_DIAGNOSTICS_57454
     *
     * Always retain the raw provider response so malformed/non-JSON
     * error pages do not collapse into an unhelpful HTTP 400 message.
     * Never log or expose the outgoing request body itself.
     */
    const rawResponse =
      await response.text();

    let body = {};

    try {
      body =
        rawResponse
          ? JSON.parse(
              rawResponse
            )
          : {};
    } catch {
      body = {};
    }


    if (
      response.ok
    ) {
      return body;
    }


    const requestBytes =
      typeof options?.body ===
        "string"
        ? Buffer.byteLength(
            options.body,
            "utf8"
          )
        : Buffer.isBuffer(
            options?.body
          )
          ? options.body.length
          : Number(
              options?.body
                ?.byteLength ||
              0
            );


    const requestMiB =
      requestBytes >
        0
        ? (
            requestBytes /
            1024 /
            1024
          ).toFixed(
            2
          )
        : null;


    const rawDetail =
      String(
        rawResponse ||
        ""
      )
        .replace(
          /\s+/g,
          " "
        )
        .trim()
        .slice(
          0,
          800
        );


    const providerMessage =
      body?.error?.message ||
      body?.message ||
      rawDetail ||
      `Provider returned HTTP ${response.status}`;


    const message = [
      `Provider returned HTTP ${response.status}`,
      requestMiB
        ? `(request ${requestMiB} MiB)`
        : null,
      providerMessage !==
        `Provider returned HTTP ${response.status}`
        ? `- ${providerMessage}`
        : null
    ]
      .filter(
        Boolean
      )
      .join(
        " "
      );

    if (
      ![
        429,
        500,
        502,
        503,
        504
      ].includes(
        response.status
      ) ||
      attempt >= retries
    ) {
      throw Object.assign(new Error(message), {
        status: response.status
      });
    }

    lastError = Object.assign(new Error(message), {
      status: response.status
    });

    const retryAfter =
      Number(
        response.headers.get(
          "retry-after"
        )
      );

    const delay =
      Number.isFinite(
        retryAfter
      ) &&
      retryAfter > 0
        ? Math.min(
            retryAfter *
              1000,
            15000
          )
        : Math.min(
            800 *
              Math.pow(
                2,
                attempt
              ),
            8000
          );

    await sleep(
      delay
    );
  }

  throw (
    lastError ||
    new Error(
      "Provider request failed."
    )
  );
}


function legacyRuntime(
  payload
) {
  return {
    provider:
      "openai",

    label:
      "OpenAI",

    adapter:
      "openai-responses",

    apiBase:
      "https://api.openai.com/v1",

    apiKey:
      process.env.OPENAI_API_KEY,

    model:
      payload.model,

    mode:
      "normal",

    supportsTools:
      true,

    supportsSearch:
      true
  };
}


function outputText(
  value
) {
  if (
    typeof value ===
    "string"
  ) {
    return value;
  }

  if (
    Array.isArray(
      value
    )
  ) {
    return value
      .map(
        (
          part
        ) => {
          if (
            typeof part ===
            "string"
          ) {
            return part;
          }

          return (
            part?.text ||
            part?.content ||
            ""
          );
        }
      )
      .filter(
        Boolean
      )
      .join(
        "\n"
      );
  }

  return "";
}


/*
 * VECTOR_PROVIDER_NEUTRAL_CONTENT_57459
 *
 * Vector internally uses Responses-style content:
 *
 *   input_text
 *   input_image
 *   function_call
 *   function_call_output
 *
 * This adapter converts that neutral representation into
 * OpenAI-compatible Chat Completions while preserving:
 *
 *   - multimodal images
 *   - function call IDs
 *   - function names
 *   - provider metadata
 *   - Gemini thought signatures
 */
function responseContentToChat(
  content
) {
  if (
    typeof content ===
    "string"
  ) {
    return content;
  }


  if (
    !Array.isArray(
      content
    )
  ) {
    return outputText(
      content
    );
  }


  const blocks = [];


  for (
    const part
    of content
  ) {
    if (
      typeof part ===
      "string"
    ) {
      blocks.push({
        type:
          "text",

        text:
          part
      });

      continue;
    }


    if (
      !part ||
      typeof part !==
        "object"
    ) {
      continue;
    }


    if (
      [
        "input_text",
        "output_text",
        "text"
      ].includes(
        part.type
      )
    ) {
      const value =
        String(
          part.text ||
          part.content ||
          ""
        );

      if (value) {
        blocks.push({
          type:
            "text",

          text:
            value
        });
      }

      continue;
    }


    if (
      part.type ===
        "input_image" ||
      part.type ===
        "image_url"
    ) {
      const imageUrl =
        typeof part.image_url ===
          "string"
          ? part.image_url
          : (
              part.image_url
                ?.url ||
              part.url ||
              ""
            );


      if (imageUrl) {
        blocks.push({
          type:
            "image_url",

          image_url: {
            url:
              imageUrl,

            ...(
              part.detail
                ? {
                    detail:
                      part.detail
                  }
                : {}
            )
          }
        });
      }

      continue;
    }


    const fallback =
      String(
        part.text ||
        part.content ||
        ""
      );


    if (fallback) {
      blocks.push({
        type:
          "text",

        text:
          fallback
      });
    }
  }


  if (
    blocks.length ===
    0
  ) {
    return outputText(
      content
    );
  }


  if (
    blocks.every(
      (
        block
      ) =>
        block.type ===
        "text"
    )
  ) {
    return blocks
      .map(
        (
          block
        ) =>
          block.text
      )
      .join(
        "\n"
      );
  }


  return blocks;
}


function responseInputToChat(
  input
) {
  const messages = [];

  /*
   * Keep tool names associated with call IDs so OpenAI-compatible
   * tool results can include both tool_call_id and name.
   */
  const functionNamesByCallId =
    new Map();


  for (
    const item
    of input || []
  ) {
    if (
      item?.role &&
      item?.type !==
        "message"
    ) {
      messages.push({
        role:
          item.role,

        content:
          responseContentToChat(
            item.content
          )
      });

      continue;
    }


    if (
      item?.type ===
      "message"
    ) {
      messages.push({
        role:
          item.role ||
          "assistant",

        content:
          responseContentToChat(
            item.content
          )
      });

      continue;
    }


    if (
      item?.type ===
      "function_call"
    ) {
      let assistant =
        messages[
          messages.length - 1
        ];


      if (
        !assistant ||
        assistant.role !==
          "assistant" ||
        assistant.__toolResultBoundary
      ) {
        assistant = {
          role:
            "assistant",

          content:
            null,

          tool_calls:
            []
        };

        messages.push(
          assistant
        );
      }


      if (
        !assistant.tool_calls
      ) {
        assistant.tool_calls = [];
      }


      /*
       * VECTOR_PROVIDER_TOOL_METADATA_REPLAY_57457
       * Preserved by the provider-neutral adapter.
       */
      const replayedToolCall = {
        id:
          item.call_id,

        type:
          "function",

        function: {
          name:
            item.name,

          arguments:
            item.arguments ||
            "{}"
        }
      };


      /*
       * Gemini 3/OpenAI-compatible APIs attach the thought
       * signature here. It must survive every replay unchanged.
       */
      if (
        item?.extra_content &&
        typeof item.extra_content ===
          "object"
      ) {
        replayedToolCall.extra_content =
          item.extra_content;
      }


      assistant.tool_calls.push(
        replayedToolCall
      );


      if (
        item?.call_id &&
        item?.name
      ) {
        functionNamesByCallId.set(
          String(
            item.call_id
          ),
          String(
            item.name
          )
        );
      }

      continue;
    }


    if (
      item?.type ===
      "function_call_output"
    ) {
      /*
       * VECTOR_TOOL_RESULT_NAME_REPLAY_57457
       * Preserve function name association for replayed tool results.
       */
      messages.push({
        role:
          "tool",

        tool_call_id:
          item.call_id,

        name:
          functionNamesByCallId.get(
            String(
              item.call_id ||
              ""
            )
          ) ||
          undefined,

        content:
          String(
            item.output ||
            ""
          ),

        __toolResultBoundary:
          true
      });
    }
  }


  return messages.map(
    (
      message
    ) => {
      const {
        __toolResultBoundary,
        ...clean
      } = message;

      return clean;
    }
  );
}


function functionTools(
  tools
) {
  return (
    tools || []
  )
    .filter(
      (
        tool
      ) =>
        tool?.type ===
        "function"
    )
    .map(
      (
        tool
      ) => ({
        type:
          "function",

        function: {
          name:
            tool.name,

          description:
            tool.description ||
            "",

          parameters:
            tool.parameters ||
            {
              type:
                "object",
              properties: {}
            }
        }
      })
    );
}


function markUsagePresence(normalized, usage) {
  const supplied = (value) =>
    value !== undefined && value !== null;

  Object.defineProperty(normalized, '__vectorTelemetryPresence', {
    value: {
      inputTokens:
        supplied(usage?.prompt_tokens) ||
        supplied(usage?.input_tokens),
      outputTokens:
        supplied(usage?.completion_tokens) ||
        supplied(usage?.output_tokens),
      cachedTokens:
        supplied(usage?.prompt_tokens_details?.cached_tokens) ||
        supplied(usage?.cache_read_input_tokens) ||
        supplied(usage?.cached_tokens)
    },
    enumerable: false
  });

  return normalized;
}

function normalizedUsage(
  usage
) {
  return markUsagePresence({
    input_tokens:
      Number(
        usage?.prompt_tokens ||
        usage?.input_tokens ||
        0
      ),

    output_tokens:
      Number(
        usage?.completion_tokens ||
        usage?.output_tokens ||
        0
      ),

    input_tokens_details: {
      cached_tokens:
        Number(
          usage?.prompt_tokens_details
            ?.cached_tokens ||
          usage?.cache_read_input_tokens ||
          usage?.cached_tokens ||
          0
        )
    }
  }, usage);
}


function citationSources(
  body
) {
  const result = [];

  const add =
    (
      value
    ) => {
      if (!value) {
        return;
      }

      if (
        typeof value ===
        "string"
      ) {
        if (
          !result.some(
            (
              item
            ) =>
              item.url ===
              value
          )
        ) {
          result.push({
            url:
              value,
            title:
              value
          });
        }

        return;
      }

      const url =
        value.url ||
        value.link;

      if (
        url &&
        !result.some(
          (
            item
          ) =>
            item.url ===
            url
        )
      ) {
        result.push({
          url,
          title:
            value.title ||
            url
        });
      }
    };

  for (
    const citation
    of body?.citations || []
  ) {
    add(
      citation
    );
  }

  for (
    const item
    of body?.search_results ||
    body?.searchResults ||
    []
  ) {
    add(
      item
    );
  }

  return result;
}


function normalizeChatResponse(
  body,
  runtime
) {
  const message =
    body?.choices?.[0]
      ?.message ||
    {};

  const output = [];

  const text =
    outputText(
      message.content
    );

  if (text) {
    output.push({
      type:
        "message",

      role:
        "assistant",

      content: [
        {
          type:
            "output_text",
          text
        }
      ]
    });
  }

  for (
    const call
    of message.tool_calls || []
  ) {
    /*
     * VECTOR_PROVIDER_TOOL_METADATA_57457
     *
     * Preserve provider-specific metadata attached to tool calls.
     *
     * Gemini 3 uses:
     *
     *   extra_content.google.thought_signature
     *
     * The value must survive normalization and be replayed
     * unchanged on subsequent tool turns.
     */
    const providerExtraContent =
      call?.extra_content ||
      call?.extraContent ||
      undefined;

    output.push({
      type:
        "function_call",

      name:
        call?.function?.name,

      arguments:
        call?.function?.arguments ||
        "{}",

      call_id:
        call.id,

      extra_content:
        providerExtraContent
    });
  }

  const sources =
    citationSources(
      body
    );

  if (
    sources.length > 0
  ) {
    output.push({
      type:
        "web_search_call",

      action: {
        sources
      }
    });
  }

  return {
    id:
      body.id ||
      cryptoId(),

    output,

    usage:
      normalizedUsage(
        body.usage
      ),

    __vector_provider:
      runtime.provider,

    __vector_model:
      runtime.model
  };
}


function cryptoId() {
  return (
    `vector_${Date.now()}_${Math.random()
      .toString(36)
      .slice(2, 9)}`
  );
}


async function openAiResponses(
  runtime,
  payload
) {
  if (!runtime.apiKey) {
    throw new Error(
      `${runtime.label} has no API key configured.`
    );
  }

  const body = {
    ...payload,
    model:
      runtime.model
  };

  return fetchJson(
    `${baseUrl(
      runtime.apiBase
    )}/responses`,
    {
      method:
        "POST",

      headers: {
        Authorization:
          `Bearer ${runtime.apiKey}`,

        "Content-Type":
          "application/json"
      },

      body:
        JSON.stringify(
          body
        )
    },
    {
      retries:
        Math.max(
          0,
          Math.min(
            Number(
              process.env
                .VECTOR_OPENAI_MAX_RETRIES ||
              3
            ),
            5
          )
        )
    }
  );
}


async function openAiCompatibleChat(
  runtime,
  payload
) {
  const messages =
    responseInputToChat(
      payload.input
    );

  if (
    payload.instructions
  ) {
    messages.unshift({
      role:
        "system",
      content:
        payload.instructions
    });
  }

  const tools =
    runtime.supportsTools
      ? functionTools(
          payload.tools
        )
      : [];

  const body = {
    model:
      runtime.model,

    messages,

    max_tokens:
      payload.max_output_tokens
  };

  if (
    tools.length > 0
  ) {
    body.tools =
      tools;

    /* VECTOR_REQUIRED_TOOL_CHOICE_57422 */
    /* VECTOR_PROVIDER_TOOL_CHOICE_57459 */
    body.tool_choice =
      payload.tool_choice ===
        "required"
        ? "required"
        : "auto";
  }

  /*
   * Gemini's OpenAI compatibility explicitly supports reasoning_effort.
   * For other providers we avoid sending a provider-specific field that
   * could break otherwise compatible APIs.
   */
  if (
    runtime.provider ===
    "google"
  ) {
    body.reasoning_effort =
      runtime.mode ===
      "deep"
        ? "high"
        : runtime.mode ===
          "quick"
          ? "low"
          : "medium";
  }

  const headers = {
    "Content-Type":
      "application/json"
  };

  if (
    runtime.apiKey
  ) {
    headers.Authorization =
      `Bearer ${runtime.apiKey}`;
  }

  if (
    runtime.provider ===
    "openrouter"
  ) {
    headers["X-Title"] =
      "Vector";
  }

  const bodyResult =
    await fetchJson(
      `${baseUrl(
        runtime.apiBase
      )}/chat/completions`,
      {
        method:
          "POST",
        headers,
        body:
          JSON.stringify(
            body
          )
      }
    );

  return normalizeChatResponse(
    bodyResult,
    runtime
  );
}


/*
 * VECTOR_ANTHROPIC_MULTIMODAL_57459
 *
 * Translate Vector/OpenAI-compatible message content into
 * Anthropic Messages content blocks.
 */
function anthropicContentFromChat(
  content
) {
  if (
    typeof content ===
    "string"
  ) {
    return content;
  }


  if (
    !Array.isArray(
      content
    )
  ) {
    return String(
      content ||
      ""
    );
  }


  const blocks = [];


  for (
    const part
    of content
  ) {
    if (
      typeof part ===
      "string"
    ) {
      blocks.push({
        type:
          "text",

        text:
          part
      });

      continue;
    }


    if (
      !part ||
      typeof part !==
        "object"
    ) {
      continue;
    }


    if (
      part.type ===
        "text"
    ) {
      if (part.text) {
        blocks.push({
          type:
            "text",

          text:
            String(
              part.text
            )
        });
      }

      continue;
    }


    if (
      part.type ===
      "image_url"
    ) {
      const url =
        typeof part.image_url ===
          "string"
          ? part.image_url
          : (
              part.image_url
                ?.url ||
              ""
            );


      const dataMatch =
        /^data:([^;,]+);base64,(.*)$/s
          .exec(
            url
          );


      if (dataMatch) {
        blocks.push({
          type:
            "image",

          source: {
            type:
              "base64",

            media_type:
              dataMatch[1],

            data:
              dataMatch[2]
          }
        });

        continue;
      }


      if (
        /^https?:\/\//i.test(
          url
        )
      ) {
        blocks.push({
          type:
            "image",

          source: {
            type:
              "url",

            url
          }
        });
      }
    }
  }


  return (
    blocks.length > 0
      ? blocks
      : ""
  );
}


function anthropicMessages(
  input
) {
  const chat =
    responseInputToChat(
      input
    );

  const result = [];


  for (
    const message
    of chat
  ) {
    if (
      message.role ===
      "system"
    ) {
      continue;
    }


    if (
      message.role ===
      "tool"
    ) {
      result.push({
        role:
          "user",

        content: [
          {
            type:
              "tool_result",

            tool_use_id:
              message.tool_call_id,

            content:
              String(
                message.content ||
                ""
              )
          }
        ]
      });

      continue;
    }


    if (
      message.role ===
        "assistant" &&
      message.tool_calls
        ?.length
    ) {
      const content = [];

      const translated =
        anthropicContentFromChat(
          message.content
        );


      if (
        Array.isArray(
          translated
        )
      ) {
        content.push(
          ...translated
        );

      } else if (
        String(
          translated ||
          ""
        ).trim()
      ) {
        content.push({
          type:
            "text",

          text:
            String(
              translated
            )
        });
      }


      for (
        const call
        of message.tool_calls
      ) {
        let inputObject = {};

        try {
          inputObject =
            JSON.parse(
              call.function
                ?.arguments ||
              "{}"
            );

        } catch {
          inputObject = {};
        }


        content.push({
          type:
            "tool_use",

          id:
            call.id,

          name:
            call.function
              ?.name,

          input:
            inputObject
        });
      }


      result.push({
        role:
          "assistant",

        content
      });

      continue;
    }


    result.push({
      role:
        message.role ===
        "assistant"
          ? "assistant"
          : "user",

      content:
        anthropicContentFromChat(
          message.content
        )
    });
  }


  return result;
}


async function anthropicRequest(
  runtime,
  payload
) {
  if (!runtime.apiKey) {
    throw new Error(
      `${runtime.label} has no API key configured.`
    );
  }

  const tools =
    runtime.supportsTools
      ? (
          payload.tools || []
        )
          .filter(
            (
              tool
            ) =>
              tool.type ===
              "function"
          )
          .map(
            (
              tool
            ) => ({
              name:
                tool.name,
              description:
                tool.description ||
                "",
              input_schema:
                tool.parameters ||
                {
                  type:
                    "object",
                  properties: {}
                }
            })
          )
      : [];

  const body = {
    model:
      runtime.model,

    max_tokens:
      payload.max_output_tokens ||
      1400,

    system:
      payload.instructions ||
      undefined,

    messages:
      anthropicMessages(
        payload.input
      )
  };

  if (
    tools.length > 0
  ) {
    body.tools =
      tools;

    if (
      payload.tool_choice ===
        "required"
    ) {
      body.tool_choice = {
        type: "any"
      };
    }
  }

  const response =
    await fetchJson(
      `${baseUrl(
        runtime.apiBase
      )}/v1/messages`,
      {
        method:
          "POST",

        headers: {
          "x-api-key":
            runtime.apiKey,

          "anthropic-version":
            "2023-06-01",

          "Content-Type":
            "application/json"
        },

        body:
          JSON.stringify(
            body
          )
      }
    );

  const output = [];

  const text =
    (
      response.content || []
    )
      .filter(
        (
          part
        ) =>
          part.type ===
          "text"
      )
      .map(
        (
          part
        ) =>
          part.text ||
          ""
      )
      .filter(
        Boolean
      )
      .join(
        "\n"
      );

  if (text) {
    output.push({
      type:
        "message",
      role:
        "assistant",
      content: [
        {
          type:
            "output_text",
          text
        }
      ]
    });
  }

  for (
    const part
    of response.content || []
  ) {
    if (
      part.type ===
      "tool_use"
    ) {
      output.push({
        type:
          "function_call",
        name:
          part.name,
        arguments:
          JSON.stringify(
            part.input ||
            {}
          ),
        call_id:
          part.id
      });
    }
  }

  return {
    id:
      response.id ||
      cryptoId(),

    output,

    usage: markUsagePresence({
      input_tokens:
        Number(
          response.usage
            ?.input_tokens ||
          0
        ),

      output_tokens:
        Number(
          response.usage
            ?.output_tokens ||
          0
        ),

      input_tokens_details: {
        cached_tokens:
          Number(
            response.usage
              ?.cache_read_input_tokens ||
            0
          )
      }
    }, response.usage),

    __vector_provider:
      runtime.provider,

    __vector_model:
      runtime.model
  };
}



/*
 * VECTOR_PROVIDER_CONTRACT_SELF_TEST_57459
 *
 * Pure local contract test. No network calls and no API keys.
 */
export function runProviderContractSelfTest() {
  const image =
    "data:image/png;base64,iVBORw0KGgo=";

  const signature =
    "vector-test-thought-signature";

  const fixture = [
    {
      role:
        "user",

      content: [
        {
          type:
            "input_text",

          text:
            "Inspect this image."
        },
        {
          type:
            "input_image",

          image_url:
            image,

          detail:
            "auto"
        }
      ]
    },

    {
      type:
        "function_call",

      name:
        "server_snapshot",

      arguments:
        "{}",

      call_id:
        "call-vector-test",

      extra_content: {
        google: {
          thought_signature:
            signature
        }
      }
    },

    {
      type:
        "function_call_output",

      call_id:
        "call-vector-test",

      output:
        "{\"ok\":true}"
    }
  ];


  const chat =
    responseInputToChat(
      fixture
    );


  const user =
    chat.find(
      (
        message
      ) =>
        message.role ===
        "user"
    );


  if (
    !Array.isArray(
      user?.content
    ) ||
    !user.content.some(
      (
        part
      ) =>
        part?.type ===
          "image_url" &&
        part?.image_url
          ?.url ===
          image
    )
  ) {
    throw new Error(
      "Provider contract failed: OpenAI-compatible image conversion."
    );
  }


  const assistant =
    chat.find(
      (
        message
      ) =>
        message.role ===
          "assistant" &&
        message.tool_calls
          ?.length
    );


  const call =
    assistant
      ?.tool_calls
      ?.[0];


  if (
    call
      ?.extra_content
      ?.google
      ?.thought_signature !==
    signature
  ) {
    throw new Error(
      "Provider contract failed: Gemini thought signature replay."
    );
  }


  const toolResult =
    chat.find(
      (
        message
      ) =>
        message.role ===
        "tool"
    );


  if (
    toolResult?.name !==
    "server_snapshot"
  ) {
    throw new Error(
      "Provider contract failed: function name replay."
    );
  }


  const anthropic =
    anthropicMessages(
      fixture
    );


  const anthropicSerialized =
    JSON.stringify(
      anthropic
    );


  if (
    !anthropicSerialized.includes(
      '"type":"image"'
    ) ||
    !anthropicSerialized.includes(
      '"type":"base64"'
    )
  ) {
    throw new Error(
      "Provider contract failed: Anthropic image conversion."
    );
  }


  if (
    !anthropicSerialized.includes(
      '"type":"tool_use"'
    ) ||
    !anthropicSerialized.includes(
      '"type":"tool_result"'
    )
  ) {
    throw new Error(
      "Provider contract failed: Anthropic tool lifecycle."
    );
  }


  return {
    ok:
      true,

    checks: [
      "OpenAI Responses internal format",
      "OpenAI-compatible multimodal conversion",
      "Gemini thought-signature preservation",
      "OpenAI-compatible tool result naming",
      "Anthropic image conversion",
      "Anthropic tool_use/tool_result conversion"
    ]
  };
}


async function requestProviderResponseDirect({
  providerRuntime,
  payload
}) {
  const runtime =
    providerRuntime ||
    legacyRuntime(
      payload
    );

  if (
    runtime.adapter ===
    "anthropic"
  ) {
    return anthropicRequest(
      runtime,
      payload
    );
  }

  if (
    runtime.adapter ===
    "openai-chat"
  ) {
    return openAiCompatibleChat(
      runtime,
      payload
    );
  }

  return openAiResponses(
    runtime,
    payload
  );
}


export async function requestProviderResponse({
  providerRuntime,
  payload
}) {
  const runtime =
    providerRuntime || legacyRuntime(payload);

  return observeProviderRequest({
    runtime,
    execute: () =>
      requestProviderResponseDirect({
        providerRuntime: runtime,
        payload
      })
  });
}

function textFromNormalized(
  response
) {
  const parts = [];

  for (
    const item
    of response.output || []
  ) {
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
        parts.push(
          content.text
        );
      }
    }
  }

  return parts.join(
    "\n"
  );
}


export async function requestSimpleProviderText({
  providerRuntime,
  model = null,
  input,
  instructions,
  maxOutputTokens = 450
}) {
  const runtime = {
    ...providerRuntime,
    model:
      model ||
      providerRuntime?.model
  };

  const response =
    await requestProviderResponse({
      providerRuntime:
        runtime,

      payload: {
        model:
          runtime.model,
        store:
          false,
        max_output_tokens:
          maxOutputTokens,
        instructions,
        input: [
          {
            role:
              "user",
            content:
              input
          }
        ],
        tools: []
      }
    });

  return {
    text:
      textFromNormalized(
        response
      ),

    inputTokens:
      Number(
        response.usage
          ?.input_tokens ||
        0
      ),

    outputTokens:
      Number(
        response.usage
          ?.output_tokens ||
        0
      ),

    cachedTokens:
      Number(
        response.usage
          ?.input_tokens_details
          ?.cached_tokens ||
        0
      )
  };
}


export async function testProviderConnection(
  runtime
) {
  const result =
    await requestSimpleProviderText({
      providerRuntime:
        runtime,
      input:
        "Reply with exactly OK.",
      instructions:
        "Connection test. Return only OK.",
      maxOutputTokens:
        256
    });

  if (
    !String(
      result.text ||
      ""
    ).trim()
  ) {
    throw new Error(
      "Provider returned an empty response."
    );
  }

  return {
    ok:
      true,
    provider:
      runtime.provider,
    model:
      runtime.model,
    response:
      result.text.trim()
  };
}
