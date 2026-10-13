/*
 * VECTOR_ARTIFACT_INTELLIGENCE_TOOL_575
 */
import {
  buildArtifactPlan,
  summarizeArtifactPlan
} from "./artifact-intelligence";

import crypto
  from "node:crypto";

import {
  db
} from "./db";

import { hostSnapshot,
  hostInspect
} from "./host-agent";

import {
  readEncryptedFile
} from "./project-files";

import {
  createChatArtifact
} from "./artifact-runtime";

import {
  searchProjectChunks
} from "./project-index";

import {
  sandboxList,
  sandboxRead,
  sandboxRun,
  sandboxWrite
} from "./runner";

const MAX_PROJECT_READ =
  180000;


/* ==========================================================
   Helpers
   ========================================================== */

function shellQuote(
  value
) {
  return (
    "'" +
    String(value)
      .replace(
        /'/g,
        "'\"'\"'"
      ) +
    "'"
  );
}

function cleanHostname(
  value
) {
  let text =
    String(
      value ||
      ""
    )
      .trim()
      .toLowerCase();

  try {
    if (
      /^https?:\/\//i.test(
        text
      )
    ) {
      text =
        new URL(
          text
        ).hostname;
    }
  } catch {
    // handled below
  }

  text =
    text
      .replace(
        /^\[/,
        ""
      )
      .replace(
        /\]$/,
        ""
      )
      .replace(
        /\.$/,
        ""
      );

  return text;
}

function validIPv4(
  value
) {
  const parts =
    String(value)
      .split(".");

  return (
    parts.length ===
      4 &&
    parts.every(
      (
        part
      ) => {
        if (
          !/^\d{1,3}$/
            .test(
              part
            )
        ) {
          return false;
        }

        const number =
          Number(part);

        return (
          number >= 0 &&
          number <= 255
        );
      }
    )
  );
}

function validHostname(
  value
) {
  const hostname =
    cleanHostname(
      value
    );

  if (
    validIPv4(
      hostname
    )
  ) {
    return true;
  }

  return (
    hostname.length <=
      253 &&
    /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/
      .test(
        hostname
      )
  );
}

function targetAllowed({
  requestedTarget,
  authorizedTargets
}) {
  const requested =
    cleanHostname(
      requestedTarget
    );

  return authorizedTargets.some(
    (
      target
    ) =>
      cleanHostname(
        target
      ) ===
      requested
  );
}

function requireAuthorizedTarget({
  target,
  context
}) {
  if (
    !validHostname(
      target
    )
  ) {
    throw new Error(
      "Invalid network target."
    );
  }

  if (
    !targetAllowed({
      requestedTarget:
        target,

      authorizedTargets:
        context.authorizedTargets ||
        []
    })
  ) {
    throw new Error(
      "Network target was not explicitly authorized in the user's current request."
    );
  }

  return cleanHostname(
    target
  );
}


/* ==========================================================
   Tool definitions
   ========================================================== */

const SERVER_TOOLS = [{
  type: "function",
  name: "server_snapshot",
  description: "Inspect the user's own Hetzner server using Vector's trusted local Host Agent. Use this when the user says my server, asks about FEGCraft on their server, Docker/service status, ports, memory, disk or uptime. No IP address is required.",
  strict: true,
  parameters: { type: "object", properties: {}, required: [], additionalProperties: false }
},
  {
    type:
      "function",

    name:
      "artifact_create_from_server_json",

    description:
      "Create a real XLSX directly from a complete JSON dataset on the user's trusted local server without sending the raw JSON dataset through the AI model. Use this for large server-backed JSON datasets such as player statistics after the exact dataset path is known. Vector reads, verifies, parses and exports every matching JSON file locally. identity_map_path may point to a JSON file that maps IDs/UUIDs to names; use an empty string when none exists.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        path: {
          type:
            "string"
        },

        pattern: {
          type:
            "string"
        },

        recursive: {
          type:
            "boolean"
        },

        max_files: {
          type:
            "integer",

          minimum:
            1,

          maximum:
            120
        },

        identity_map_path: {
          type:
            "string"
        },

        filename: {
          type:
            "string"
        },

        title: {
          type:
            "string"
        }
      },

      required: [
        "path",
        "pattern",
        "recursive",
        "max_files",
        "identity_map_path",
        "filename",
        "title"
      ],

      additionalProperties:
        false
    }
  }];

const PROJECT_TOOLS = [
  {
    type:
      "function",

    name:
      "project_list_files",

    description:
      "List files already uploaded to the current Vector project. IMPORTANT: use this when the user refers to project files, uploaded files, logs, crash reports, source code or documents instead of asking them to upload the file again.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {},

      required: [],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "project_search",

    description:
      "Search locally indexed project files for relevant text, errors, stack traces, configuration, source code, identifiers or documentation. Use this proactively when project files may answer the user's question.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        query: {
          type:
            "string"
        },

        limit: {
          type:
            "integer",

          minimum:
            1,

          maximum:
            15
        }
      },

      required: [
        "query",
        "limit"
      ],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "project_read_file",

    description:
      "Read a text, log, configuration or source-code file from the current Vector project. Use after listing or searching files when more context is needed.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        file_id: {
          type:
            "string"
        }
      },

      required: [
        "file_id"
      ],

      additionalProperties:
        false
    }
  }
];


/*
 * VECTOR_ARTIFACT_TOOL_5742
 */
const ARTIFACT_TOOLS = [
  {
    type:
      "function",

    name:
      "artifact_create",

    description:
      "Create a polished real downloadable PDF, DOCX or XLSX for the current user. Use this whenever the user explicitly asks Vector to create, generate, export or deliver one of these file types. Do not replace a requested file with only Markdown or a code block. For PDF/DOCX provide polished document content using Markdown headings, paragraphs, bullet or numbered lists, **bold**, *italic*, `inline code`, > callouts and --- dividers when useful. Do not repeat the document title as the first Markdown heading when title is already supplied separately. For XLSX use structured sheets with the first row as column headers, use separate sheets when they improve organization, and keep numbers and booleans as native values instead of formatting them as text. Always provide every parameter; use empty strings/arrays when unused.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        format: {
          type:
            "string",

          enum: [
            "pdf",
            "docx",
            "xlsx"
          ]
        },

        filename: {
          type:
            "string"
        },

        title: {
          type:
            "string"
        },

        content: {
          type:
            "string"
        },

        sheets: {
          type:
            "array",

          items: {
            type:
              "object",

            properties: {
              name: {
                type:
                  "string"
              },

              rows: {
                type:
                  "array",

                items: {
                  type:
                    "array",

                  items: {
                    type: [
                      "string",
                      "number",
                      "boolean",
                      "null"
                    ]
                  }
                }
              }
            },

            required: [
              "name",
              "rows"
            ],

            additionalProperties:
              false
          }
        }
      },

      required: [
        "format",
        "filename",
        "title",
        "content",
        "sheets"
      ],

      additionalProperties:
        false
    }
  }
];


const SANDBOX_TOOLS = [
  {
    type:
      "function",

    name:
      "sandbox_write_file",

    description:
      "Create or modify a temporary file in the isolated Vector task workspace. Use this for code, scripts, configuration, tests or generated artifacts before validation.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        path: {
          type:
            "string"
        },

        content: {
          type:
            "string"
        }
      },

      required: [
        "path",
        "content"
      ],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "sandbox_read_file",

    description:
      "Read a file created inside the current temporary Vector sandbox.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        path: {
          type:
            "string"
        }
      },

      required: [
        "path"
      ],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "sandbox_list_files",

    description:
      "List files currently present in the temporary task sandbox.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {},

      required: [],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "sandbox_run",

    description:
      "Run a development command inside Vector's isolated temporary runner. Use for compiling, linting, tests, parsing data or validating generated code. This is not the production host.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        command: {
          type:
            "string"
        },

        timeout_ms: {
          type:
            "integer",

          minimum:
            1000,

          maximum:
            120000
        }
      },

      required: [
        "command",
        "timeout_ms"
      ],

      additionalProperties:
        false
    }
  }
];


const NETWORK_TOOLS = [
  {
    type:
      "function",

    name:
      "network_ping",

    description:
      "Perform a short ICMP reachability check against a host explicitly supplied by the user in the current request.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        target: {
          type:
            "string"
        }
      },

      required: [
        "target"
      ],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "network_scan",

    description:
      "Run an authorized TCP service discovery scan against a host explicitly supplied by the user in the current request. Use when the user asks Vector to inspect, scan, enumerate or identify services on their server or host. Never choose unrelated targets.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        target: {
          type:
            "string"
        },

        profile: {
          type:
            "string",

          enum: [
            "common",
            "full",
            "web"
          ]
        }
      },

      required: [
        "target",
        "profile"
      ],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "network_http_probe",

    description:
      "Inspect an HTTP or HTTPS service on a target explicitly supplied by the user. Retrieves headers and a small amount of page content to identify the service.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        url: {
          type:
            "string"
        }
      },

      required: [
        "url"
      ],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "network_dns_lookup",

    description:
      "Perform DNS resolution for a hostname explicitly supplied by the user.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        target: {
          type:
            "string"
        }
      },

      required: [
        "target"
      ],

      additionalProperties:
        false
    }
  },

  {
    type:
      "function",

    name:
      "network_tcp_check",

    description:
      "Check whether a specific TCP port is reachable on a host explicitly supplied by the user.",

    strict:
      true,

    parameters: {
      type:
        "object",

      properties: {
        target: {
          type:
            "string"
        },

        port: {
          type:
            "integer",

          minimum:
            1,

          maximum:
            65535
        }
      },

      required: [
        "target",
        "port"
      ],

      additionalProperties:
        false
    }
  }
];



/*
 * VECTOR_SERVER_JSON_ARTIFACT_57459
 *
 * Large JSON datasets must not be pushed through the model merely
 * to produce a spreadsheet.
 *
 * This path:
 *   Host Agent read_many
 *       -> local JSON parse
 *       -> local flatten/normalization
 *       -> local XLSX generator
 *
 * The model only receives compact artifact metadata.
 */
function jsonIdentityMap(
  value
) {
  const result =
    new Map();


  if (
    Array.isArray(
      value
    )
  ) {
    for (
      const item
      of value
    ) {
      if (
        !item ||
        typeof item !==
          "object"
      ) {
        continue;
      }


      const id =
        item.uuid ||
        item.id ||
        item.key ||
        null;

      const name =
        item.name ||
        item.username ||
        item.display_name ||
        item.displayName ||
        null;


      if (
        id &&
        name
      ) {
        result.set(
          String(
            id
          ).toLowerCase(),
          String(
            name
          )
        );
      }
    }


    return result;
  }


  if (
    value &&
    typeof value ===
      "object"
  ) {
    for (
      const [
        key,
        item
      ]
      of Object.entries(
        value
      )
    ) {
      if (
        typeof item ===
        "string"
      ) {
        result.set(
          String(
            key
          ).toLowerCase(),
          item
        );

        continue;
      }


      if (
        item &&
        typeof item ===
          "object"
      ) {
        const name =
          item.name ||
          item.username ||
          item.display_name ||
          item.displayName ||
          null;


        if (name) {
          result.set(
            String(
              key
            ).toLowerCase(),
            String(
              name
            )
          );
        }
      }
    }
  }


  return result;
}


function walkJsonLeaves(
  value,
  prefix,
  emit
) {
  if (
    value === null ||
    typeof value !==
      "object"
  ) {
    emit(
      prefix ||
        "value",
      value
    );

    return;
  }


  if (
    Array.isArray(
      value
    )
  ) {
    for (
      let index = 0;
      index < value.length;
      index += 1
    ) {
      walkJsonLeaves(
        value[index],
        prefix
          ? `${prefix}.${index}`
          : String(
              index
            ),
        emit
      );
    }

    return;
  }


  for (
    const [
      key,
      child
    ]
    of Object.entries(
      value
    )
  ) {
    walkJsonLeaves(
      child,
      prefix
        ? `${prefix}.${key}`
        : key,
      emit
    );
  }
}


function serverJsonWorkbookSheets({
  bulk,
  identityMap
}) {
  const MAX_ROWS =
    Math.max(
      1,
      Math.min(
        1000000,
        Number(
          process.env
            .VECTOR_SERVER_JSON_EXPORT_MAX_ROWS ||
          250000
        )
      )
    );


  const statisticRows = [
    [
      "Player",
      "Source ID",
      "Category",
      "Statistic",
      "Value"
    ]
  ];


  const metadataRows = [
    [
      "Player",
      "Source ID",
      "Field",
      "Value"
    ]
  ];


  const playerRows = [
    [
      "Player",
      "Source ID",
      "Statistics"
    ]
  ];


  let mappedPlayers =
    0;

  let totalStatistics =
    0;


  for (
    const item
    of bulk.items || []
  ) {
    if (
      item?.truncated
    ) {
      throw new Error(
        `Server JSON dataset contains a truncated source file: ${
          item.relative_path ||
          item.path ||
          "unknown"
        }`
      );
    }


    let document;

    try {
      document =
        JSON.parse(
          String(
            item.content ||
            ""
          )
        );

    } catch (
      error
    ) {
      throw new Error(
        `Server JSON dataset contains invalid JSON in ${
          item.relative_path ||
          item.path ||
          "unknown"
        }: ${error.message}`
      );
    }


    const sourceName =
      String(
        item.relative_path ||
        item.path ||
        ""
      )
        .split("/")
        .pop() ||
      "source.json";


    const sourceId =
      sourceName.replace(
        /\.json$/i,
        ""
      );


    const mapped =
      identityMap.get(
        sourceId.toLowerCase()
      );


    const player =
      mapped ||
      sourceId;


    if (mapped) {
      mappedPlayers +=
        1;
    }


    let playerStatistics =
      0;


    if (
      document?.stats &&
      typeof document.stats ===
        "object" &&
      !Array.isArray(
        document.stats
      )
    ) {
      for (
        const [
          category,
          values
        ]
        of Object.entries(
          document.stats
        )
      ) {
        walkJsonLeaves(
          values,
          "",
          (
            statistic,
            value
          ) => {
            statisticRows.push([
              player,
              sourceId,
              category,
              statistic,
              value
            ]);

            playerStatistics +=
              1;

            totalStatistics +=
              1;
          }
        );
      }


      for (
        const [
          key,
          value
        ]
        of Object.entries(
          document
        )
      ) {
        if (
          key ===
          "stats"
        ) {
          continue;
        }


        walkJsonLeaves(
          value,
          key,
          (
            field,
            child
          ) => {
            metadataRows.push([
              player,
              sourceId,
              field,
              child
            ]);
          }
        );
      }

    } else {
      walkJsonLeaves(
        document,
        "",
        (
          statistic,
          value
        ) => {
          statisticRows.push([
            player,
            sourceId,
            "root",
            statistic,
            value
          ]);

          playerStatistics +=
            1;

          totalStatistics +=
            1;
        }
      );
    }


    playerRows.push([
      player,
      sourceId,
      playerStatistics
    ]);


    if (
      statisticRows.length >
        MAX_ROWS ||
      metadataRows.length >
        MAX_ROWS
    ) {
      throw new Error(
        `Server JSON export exceeds Vector's configured ${
          MAX_ROWS
        } rows-per-sheet safety limit.`
      );
    }
  }


  return {
    mappedPlayers,
    totalStatistics,

    sheets: [
      {
        name:
          "Overview",

        rows: [
          [
            "Metric",
            "Value"
          ],
          [
            "Source path",
            bulk.path ||
              ""
          ],
          [
            "Pattern",
            bulk.pattern ||
              "*.json"
          ],
          [
            "Files discovered",
            Number(
              bulk.files_discovered ||
              0
            )
          ],
          [
            "Files processed",
            Number(
              bulk.files_returned ||
              0
            )
          ],
          [
            "Dataset complete",
            Boolean(
              bulk.complete
            )
          ],
          [
            "Dataset truncated",
            Boolean(
              bulk.truncated
            )
          ],
          [
            "Names mapped",
            mappedPlayers
          ],
          [
            "Statistic values exported",
            totalStatistics
          ]
        ]
      },

      {
        name:
          "Players",

        rows:
          playerRows
      },

      {
        name:
          "All Statistics",

        rows:
          statisticRows
      },

      {
        name:
          "Metadata",

        rows:
          metadataRows
      }
    ]
  };
}


/* ==========================================================
   Public functions
   ========================================================== */

export function getVectorTools({
  projectId = null,
  allowServer = false
} = {}) {
  return [
    ...(allowServer ? SERVER_TOOLS : []),
    ...(projectId
      ? PROJECT_TOOLS
      : []),

    ...ARTIFACT_TOOLS,

    ...SANDBOX_TOOLS,

    ...NETWORK_TOOLS
  ];
}


export function createToolContext({
  projectId = null,
  userId = null,
  conversationId = null,
  jobId = null,
  authorizedTargets = []
}) {
  return {
    projectId:
      projectId ||
      "global",

    /* VECTOR_ARTIFACT_CONTEXT_5742 */
    userId,
    conversationId,
    jobId,

    runId:
      crypto
        .randomUUID(),

    authorizedTargets:
      Array.from(
        new Set(
          authorizedTargets
            .map(
              cleanHostname
            )
            .filter(
              Boolean
            )
        )
      )
  };
}


/* ==========================================================
   Tool execution
   ========================================================== */


/*
 * VECTOR_BULK_COMPLETENESS_STATE_57453
 *
 * Track bounded bulk evidence inside one shared Vector job.
 *
 * A later read_many call for the same path/pattern replaces the
 * previous status, allowing an incomplete first attempt to be
 * repaired with a larger max_files value.
 */
function bulkEvidenceKey(
  args = {}
) {
  const path =
    String(
      args?.path ||
      ""
    ).trim();

  const pattern =
    String(
      args?.pattern ||
      "*"
    ).trim() ||
    "*";

  const recursive =
    args?.recursive ===
      false
      ? "flat"
      : "recursive";

  return [
    path,
    pattern,
    recursive
  ].join(
    "\n"
  );
}


function recordBulkEvidence(
  context,
  args,
  result
) {
  if (
    !context ||
    args?.action !==
      "read_many"
  ) {
    return;
  }


  if (
    !context.bulkEvidence ||
    typeof context.bulkEvidence !==
      "object"
  ) {
    context.bulkEvidence =
      {};
  }


  const filesDiscovered =
    Math.max(
      0,
      Number(
        result?.files_discovered ||
        0
      )
    );


  const filesReturned =
    Math.max(
      0,
      Number(
        result?.files_returned ||
        0
      )
    );


  const complete =
    result?.complete ===
      true &&
    result?.truncated !==
      true &&
    filesReturned >=
      filesDiscovered;


  const evidence = {
    path:
      String(
        args?.path ||
        ""
      ),

    pattern:
      String(
        args?.pattern ||
        "*"
      ) ||
      "*",

    recursive:
      args?.recursive !==
        false,

    filesDiscovered,

    filesReturned,

    complete,

    truncated:
      result?.truncated ===
      true,

    recordedAt:
      new Date()
        .toISOString()
  };


  context.bulkEvidence[
    bulkEvidenceKey(
      args
    )
  ] =
    evidence;


  context.lastBulkEvidence =
    evidence;
}


function incompleteBulkEvidence(
  context
) {
  const evidence =
    context?.bulkEvidence;

  if (
    !evidence ||
    typeof evidence !==
      "object"
  ) {
    return [];
  }


  return Object.values(
    evidence
  ).filter(
    (
      item
    ) =>
      item &&
      item.complete !==
        true
  );
}


export async function executeVectorTool({
  name,
  arguments:
    args,
  context
}) {
  const {
    projectId,
    runId
  } =
    context;

  switch (
    name
  ) {

    /*
     * VECTOR_SERVER_CONTAINER_TOOL_EXECUTION_582C
     */
    /*
     * VECTOR_MINECRAFT_TOOL_EXECUTION_582D1
     */
    case "server_minecraft_advancements": {
      const container =
        String(
          args?.container ||
          ""
        ).trim();

      const player =
        String(
          args?.player ||
          ""
        ).trim();

      if (
        !container ||
        !player
      ) {
        throw new Error(
          "Minecraft container and player are required."
        );
      }

      return await hostInspect({
        action:
          "minecraft_player_advancements",

        name:
          container,

        player
      });
    }


    case "server_container_stats":
      return await hostInspect({
        action:
          "docker_stats"
      });


    case "server_container_logs": {
      const requestedName =
        String(
          args?.name ||
          ""
        ).trim();

      if (!requestedName) {
        throw new Error(
          "Container name is required."
        );
      }

      return await hostInspect({
        action:
          "docker_logs",

        name:
          requestedName,

        tail:
          Math.max(
            10,
            Math.min(
              500,
              Number(
                args?.tail ||
                100
              )
            )
          )
      });
    }


    case "server_inspect": {
      /*
       * VECTOR_BULK_COMPLETENESS_CAPTURE_57453
       */
      const result =
        await hostInspect(
          args || {}
        );

      if (
        args?.action ===
        "read_many"
      ) {
        recordBulkEvidence(
          context,
          args,
          result
        );
      }

      return result;
    }

    case "server_snapshot":
      return await hostSnapshot();

    /* --------------------------------------------------------
       Project tools
       -------------------------------------------------------- */

      case "artifact_create_from_server_json": {
        if (
          !context.userId ||
          !context.conversationId ||
          !context.jobId
        ) {
          throw new Error(
            "Artifact generation is unavailable because the AI job context is incomplete."
          );
        }


        if (
          context.artifactCreated &&
          context.lastArtifact
        ) {
          return {
            ...context.lastArtifact,

            reused:
              true
          };
        }


        const bulk =
          await hostInspect({
            action:
              "read_many",

            path:
              args?.path,

            pattern:
              args?.pattern ||
              "*.json",

            recursive:
              Boolean(
                args?.recursive
              ),

            max_files:
              Math.max(
                1,
                Math.min(
                  120,
                  Number(
                    args?.max_files ||
                    120
                  )
                )
              )
          });


        const discovered =
          Number(
            bulk
              ?.files_discovered ||
            0
          );

        const returned =
          Number(
            bulk
              ?.files_returned ||
            0
          );


        if (
          bulk?.complete !==
            true ||
          bulk?.truncated ===
            true ||
          bulk?.scan_truncated ===
            true ||
          discovered !==
            returned
        ) {
          throw new Error(
            [
              "Server JSON XLSX export blocked because the dataset is incomplete.",
              `Files returned: ${returned}/${discovered}.`,
              "Vector will not create a partial workbook."
            ].join(
              " "
            )
          );
        }


        let identityMap =
          new Map();


        const identityPath =
          String(
            args?.identity_map_path ||
            ""
          ).trim();


        if (
          identityPath
        ) {
          const slash =
            identityPath.lastIndexOf(
              "/"
            );


          const identityDirectory =
            slash > 0
              ? identityPath.slice(
                  0,
                  slash
                )
              : "/";

          const identityFilename =
            identityPath.slice(
              slash + 1
            );


          const identityBulk =
            await hostInspect({
              action:
                "read_many",

              path:
                identityDirectory,

              pattern:
                identityFilename,

              recursive:
                false,

              max_files:
                1
            });


          if (
            identityBulk
              ?.complete !==
              true ||
            identityBulk
              ?.truncated ===
              true ||
            Number(
              identityBulk
                ?.files_returned ||
              0
            ) !==
              1
          ) {
            throw new Error(
              "Identity-map JSON could not be read completely."
            );
          }


          try {
            identityMap =
              jsonIdentityMap(
                JSON.parse(
                  String(
                    identityBulk
                      ?.items
                      ?.[0]
                      ?.content ||
                    ""
                  )
                )
              );

          } catch (
            error
          ) {
            throw new Error(
              `Identity-map JSON is invalid: ${error.message}`
            );
          }
        }


        const workbook =
          serverJsonWorkbookSheets({
            bulk,
            identityMap
          });


        const artifact =
          await createChatArtifact({
            ownerUserId:
              context.userId,

            conversationId:
              context.conversationId,

            jobId:
              context.jobId,

            format:
              "xlsx",

            filename:
              args?.filename,

            title:
              args?.title ||
              "Server JSON dataset",

            content:
              "",

            sheets:
              workbook.sheets
          });


        context.artifactCreated =
          true;

        context.lastArtifact =
          artifact;


        return {
          ...artifact,

          sourceComplete:
            true,

          filesProcessed:
            returned,

          namesMapped:
            workbook.mappedPlayers,

          statisticValues:
            workbook.totalStatistics,

          localProcessing:
            true
        };
      }



      case "artifact_create": {
        if (
          !context.userId ||
          !context.conversationId ||
          !context.jobId
        ) {
          throw new Error(
            "Artifact generation is unavailable because the AI job context is incomplete."
          );
        }

        /*
         * VECTOR_ARTIFACT_RUN_DEDUP_5743
         *
         * A reviewer/repair turn can reuse the same tool context.
         * Never create the same requested artifact twice inside
         * one Vector job. Return the already generated artifact.
         */
        if (
          context.artifactCreated &&
          context.lastArtifact
        ) {
          return {
            ...context.lastArtifact,
            reused:
              true
          };
        }

        /*
         * VECTOR_ARTIFACT_COMPLETENESS_GUARD_57453
         *
         * Never create a finished artifact from a bulk source that
         * explicitly reported incomplete or truncated evidence.
         */
        const incompleteEvidence =
          incompleteBulkEvidence(
            context
          );


        if (
          incompleteEvidence.length >
          0
        ) {
          const evidence =
            incompleteEvidence[
              0
            ];


          const discovered =
            Number(
              evidence
                ?.filesDiscovered ||
              0
            );


          const returned =
            Number(
              evidence
                ?.filesReturned ||
              0
            );


          const source =
            evidence?.path ||
            "bulk data source";


          const pattern =
            evidence?.pattern ||
            "*";


          throw new Error(
            [
              "Artifact creation blocked because bulk source data is incomplete.",
              `Source: ${source}`,
              `Pattern: ${pattern}`,
              `Files returned: ${returned}/${discovered}.`,
              "Retry server_inspect with action=read_many for the same path and pattern using a sufficiently large max_files value. Artifact creation is allowed only after complete=true and truncated=false."
            ].join(
              " "
            )
          );
        }

        /*
         * VECTOR_ARTIFACT_SEMANTIC_PLAN_575
         *
         * Plan the document before rendering it.
         */
        const artifactPlan =
          buildArtifactPlan({
            requestText:
              context
                ?.artifactRequestText ||
              "",

            format:
              args?.format,

            title:
              args?.title ||
              "",

            content:
              args?.content ||
              "",

            sheets:
              Array.isArray(
                args?.sheets
              )
                ? args.sheets
                : []
          });


        context.lastArtifactPlan =
          artifactPlan;


        const artifact =
          await createChatArtifact({
          ownerUserId:
            context.userId,

          conversationId:
            context.conversationId,

          jobId:
            context.jobId,

          artifactPlan:
            artifactPlan,

          format:
            args?.format,

          filename:
            args?.filename,

          title:
            args?.title ||
            "",

          content:
            args?.content ||
            "",

          sheets:
            Array.isArray(
              args?.sheets
            )
              ? args.sheets
              : []
        });

        /* VECTOR_ARTIFACT_CREATED_STATE_57422 */
        context.artifactCreated = true;

          context.lastArtifact =
            artifact;

        return {
          ...artifact,

          artifactPlan:
            summarizeArtifactPlan(
              artifactPlan
            )
        };
      }


    case "project_list_files": {
      if (
        !context.projectId ||
        context.projectId ===
        "global"
      ) {
        throw new Error(
          "No project is attached to this conversation."
        );
      }

      const result =
        await db.query(
          `
            SELECT
              id,
              original_name,
              mime_type,
              extension,
              size_bytes,
              previewable,
              created_at

            FROM project_files

            WHERE
              project_id = $1

            ORDER BY
              created_at DESC

            LIMIT 500
          `,
          [
            context.projectId
          ]
        );

      return {
        files:
          result.rows.map(
            (
              file
            ) => ({
              id:
                file.id,

              name:
                file.original_name,

              mimeType:
                file.mime_type,

              extension:
                file.extension,

              size:
                Number(
                  file.size_bytes
                ),

              readableAsText:
                file.previewable
            })
          )
      };
    }


    case "project_search": {
      if (
        !context.projectId ||
        context.projectId ===
        "global"
      ) {
        throw new Error(
          "No project is attached to this conversation."
        );
      }

      const rows =
        await searchProjectChunks({
          projectId:
            context.projectId,

          query:
            args.query,

          limit:
            args.limit
        });

      return {
        results:
          rows.map(
            (
              row
            ) => ({
              fileId:
                row.file_id,

              file:
                row.original_name,

              startLine:
                row.start_line,

              endLine:
                row.end_line,

              content:
                row.content
            })
          )
      };
    }


    case "project_read_file": {
      if (
        !context.projectId ||
        context.projectId ===
        "global"
      ) {
        throw new Error(
          "No project is attached to this conversation."
        );
      }

      const result =
        await db.query(
          `
            SELECT *

            FROM project_files

            WHERE
              id = $1
              AND
              project_id = $2
          `,
          [
            args.file_id,
            context.projectId
          ]
        );

      if (
        result.rowCount ===
        0
      ) {
        throw new Error(
          "Project file not found."
        );
      }

      const file =
        result.rows[0];

      if (
        !file.previewable
      ) {
        return {
          id:
            file.id,

          name:
            file.original_name,

          mimeType:
            file.mime_type,

          readable:
            false,

          message:
            "Binary/multimodal parsing for this file type is handled by a later specialist tool."
        };
      }

      const buffer =
        await readEncryptedFile(
          file
        );

      const text =
        buffer.toString(
          "utf8"
        );

      return {
        id:
          file.id,

        name:
          file.original_name,

        content:
          text.slice(
            0,
            MAX_PROJECT_READ
          ),

        truncated:
          text.length >
          MAX_PROJECT_READ
      };
    }


    /* --------------------------------------------------------
       Sandbox
       -------------------------------------------------------- */

    case "sandbox_write_file":
      return sandboxWrite({
        projectId,
        runId,

        path:
          args.path,

        content:
          args.content
      });


    case "sandbox_read_file":
      return sandboxRead({
        projectId,
        runId,

        path:
          args.path
      });


    case "sandbox_list_files":
      return sandboxList({
        projectId,
        runId
      });


    case "sandbox_run":
      return sandboxRun({
        projectId,
        runId,

        command:
          args.command,

        timeoutMs:
          args.timeout_ms
      });


    /* --------------------------------------------------------
       Network inspection
       -------------------------------------------------------- */

    case "network_ping": {
      const target =
        requireAuthorizedTarget({
          target:
            args.target,

          context
        });

      return sandboxRun({
        projectId,
        runId,

        command:
          `ping -c 3 -W 2 ${shellQuote(
            target
          )}`,

        timeoutMs:
          12000
      });
    }


    case "network_scan": {
      const target =
        requireAuthorizedTarget({
          target:
            args.target,

          context
        });

      let command;

      if (
        args.profile ===
        "full"
      ) {
        command = [
          "nmap",
          "-Pn",
          "-n",
          "-sT",
          "-sV",
          "--version-light",
          "--open",
          "-T3",
          "--max-retries",
          "1",
          "--host-timeout",
          "110s",
          "-p-",
          shellQuote(
            target
          )
        ].join(" ");

      } else if (
        args.profile ===
        "web"
      ) {
        command = [
          "nmap",
          "-Pn",
          "-n",
          "-sT",
          "-sV",
          "--version-light",
          "--open",
          "-T3",
          "-p",
          "80,81,443,3000,3001,5000,5601,8000,8008,8080,8081,8088,8443,8888,9000,9090,9091,9443",
          shellQuote(
            target
          )
        ].join(" ");

      } else {
        command = [
          "nmap",
          "-Pn",
          "-n",
          "-sT",
          "-sV",
          "--version-light",
          "--open",
          "-T3",
          "--top-ports",
          "1000",
          "--host-timeout",
          "110s",
          shellQuote(
            target
          )
        ].join(" ");
      }

      return sandboxRun({
        projectId,
        runId,

        command,

        timeoutMs:
          120000
      });
    }


    case "network_dns_lookup": {
      const target =
        requireAuthorizedTarget({
          target:
            args.target,

          context
        });

      return sandboxRun({
        projectId,
        runId,

        command:
          `dig +noall +answer A AAAA ${shellQuote(
            target
          )}; echo "--- PTR ---"; dig +short -x ${shellQuote(
            target
          )}`,

        timeoutMs:
          15000
      });
    }


    case "network_tcp_check": {
      const target =
        requireAuthorizedTarget({
          target:
            args.target,

          context
        });

      const port =
        Number(
          args.port
        );

      if (
        !Number.isInteger(
          port
        ) ||
        port < 1 ||
        port > 65535
      ) {
        throw new Error(
          "Invalid TCP port."
        );
      }

      return sandboxRun({
        projectId,
        runId,

        command:
          `nc -vz -w 5 ${shellQuote(
            target
          )} ${port}`,

        timeoutMs:
          10000
      });
    }


    case "network_http_probe": {
      let url;

      try {
        url =
          new URL(
            String(
              args.url
            )
          );
      } catch {
        throw new Error(
          "Invalid URL."
        );
      }

      if (
        url.protocol !==
          "http:" &&
        url.protocol !==
          "https:"
      ) {
        throw new Error(
          "Only HTTP and HTTPS probes are allowed."
        );
      }

      requireAuthorizedTarget({
        target:
          url.hostname,

        context
      });

      return sandboxRun({
        projectId,
        runId,

        command: [
          "echo '--- HEADERS ---';",
          "curl",
          "-k",
          "-L",
          "--max-time",
          "15",
          "--connect-timeout",
          "5",
          "-sS",
          "-D",
          "-",
          "-o",
          "/tmp/vector-http-body",
          "--max-filesize",
          "262144",
          shellQuote(
            url.toString()
          ),
          ";",
          "echo;",
          "echo '--- BODY SAMPLE ---';",
          "head -c 20000 /tmp/vector-http-body",
          "2>/dev/null || true"
        ].join(" "),

        timeoutMs:
          25000
      });
    }


    default:
      throw new Error(
        `Unknown Vector tool: ${name}`
      );
  }
}
