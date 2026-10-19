/*
 * VECTOR_EXECUTION_ROUTER_582
 *
 * Execution routing and model routing are intentionally separate.
 *
 * This classifier decides HOW Vector executes a task:
 *
 *   FAST
 *   ARTIFACT
 *   TOOL
 *   DEEP
 *
 * It does not select the provider/model.
 * It performs no AI/API call.
 */


function normalizedText(
  value
) {
  return String(
    value ||
    ""
  )
    .trim()
    .toLowerCase();
}


function artifactIntent(
  text
) {
  const action =
    /\b(create|generate|make|build|produce|export|prepare|draft|erstell|generier|mach|bau|exportier|erstelle|erzeuge)\w*/i
      .test(
        text
      );

  const format =
    /\b(pdf|docx|xlsx|word document|word file|word datei|word-dokument|excel file|excel datei|excel workbook|spreadsheet|arbeitsmappe|tabelle als datei)\b/i
      .test(
        text
      );

  return (
    action &&
    format
  );
}


function webIntent(
  text,
  explicitWebSearch
) {
  if (
    explicitWebSearch
  ) {
    return true;
  }

  return (
    /\b(search|browse|look up|lookup|find online|search online|search the web|web search|internet search|recherchier|suche im internet|such im internet|online nachschauen)\b/i
      .test(
        text
      ) ||
    /\b(latest|today|currently available|current release|release notes|news|breaking|aktuellste|heute|neueste version)\b/i
      .test(
        text
      )
  );
}


/*
 * VECTOR_CONVERSATION_CONTINUITY_582C
 *
 * Server routing stays deterministic and local. Recent conversation
 * text is only used to resolve obvious follow-ups; no classifier model
 * call is introduced.
 */
function configuredServerIntent(text) {
  const aliases=(globalThis.process?.env?.VECTOR_MINECRAFT_SERVER_ALIASES || '').split(',').map(v=>v.trim()).filter(v=>v && v.length<=64).slice(0,16);
  return aliases.some(alias=>{
    const escaped=alias.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    return new RegExp('(?<![\\p{L}\\p{N}_])'+escaped+'(?![\\p{L}\\p{N}_])','iu').test(text);
  });
}

function serverIntent(
  text
) {
  /*
   * VECTOR_SERVER_INTENT_PRECISION_582C5
   *
   * Generic knowledge questions such as
   * "What is a Docker container?" remain FAST.
   * Live-state wording is handled by serverStateIntent().
   */
  return (
    configuredServerIntent(text) ||
    /\b(my server|mein(?:e|em|en|es)? servers?|auf meinem server|on my server|server status|server health|server logs?)\b/i
      .test(
        text
      ) ||
    /\b(docker logs?|systemd|service logs?|listening ports?|uptime|disk usage|memory usage|ram usage|cpu usage)\b/i
      .test(
        text
      ) ||
    /\b(check|inspect|prüf|prüfe|überprüf|status)\w*\b.{0,45}\b(server|container|docker|host)\b/i
      .test(
        text
      )
  );
}


function serverStateIntent(
  text
) {
  const subject =
    /\b(containers?|docker|server|host|services?|systemd)\b/i
      .test(
        text
      );

  const liveState =
    /\b(wie viele|how many|laufen|running|status|health|cpu|ram|memory|speicher|leistung|auslastung|verbrauch|usage|resources?|ressourcen|logs?|ports?|uptime|disk|festplatte|am meisten|most|highest|top)\b/i
      .test(
        text
      );

  return (
    subject &&
    liveState
  );
}


function serverStatsIntent(
  text
) {
  return (
    /\b(cpu|ram|memory|speicher|leistung|auslastung|verbrauch|usage|resources?|ressourcen|memperc|cpuperc|am meisten|most|highest|top)\b/i
      .test(
        text
      ) ||
    (
      /\b(containers?|docker)\b/i
        .test(
          text
        ) &&
      /\b(wie viele|how many|laufen|running)\b/i
        .test(
          text
        )
    )
  );
}


function serverLogsIntent(
  text
) {
  return (
    /\b(logs?|logdatei(?:en)?|journal|ausgabe)\b/i
      .test(
        text
      ) &&
    /\b(zeig|zeige|show|check|prüf|prüfe|lies|read|logs?|davon|dessen|deren|dem|container|service)\b/i
      .test(
        text
      )
  );
}


function messageText(
  message
) {
  const content =
    message?.content;

  if (
    typeof content ===
    "string"
  ) {
    return content;
  }

  if (
    Array.isArray(
      content
    )
  ) {
    return content
      .map(
        (part) => {
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
      .filter(Boolean)
      .join("\n");
  }

  return "";
}


function recentContextText(
  recentMessages
) {
  if (
    !Array.isArray(
      recentMessages
    )
  ) {
    return "";
  }

  const users=recentMessages.filter(message=>message?.role==='user');
  let index=users.length-1;
  const followup=/^(?:(?:und|and)\s+)?(?:für|for)\s+(?:[A-Za-z0-9_]{1,32}|<VEC_[A-Z_]+_[a-f0-9]{32}>)\s*[?!.]?$/i;
  while(index>=0&&followup.test(messageText(users[index]).trim()))index--;
  return users.slice(Math.max(0,index)).map(messageText).filter(Boolean).join('\n').toLowerCase();
}


function serverContextIntent(
  recentText
) {
  return (
    serverIntent(
      recentText
    ) ||
    serverStateIntent(
      recentText
    ) ||
    /\b(server|minecraft|docker|containers?)\b/i
      .test(
        recentText
      )
  );
}


/*
 * VECTOR_CONTINUITY_PRECISION_582C7
 *
 * Previous server context may resolve real follow-ups, but mentioning
 * "Docker" or "container" alone must not turn a normal knowledge
 * question into a live server inspection.
 */
/*
 * VECTOR_MINECRAFT_ROUTING_582D1
 *
 * Minecraft player-state lookups are deterministic server tasks.
 * A short "and for <player>" follow-up inherits the previous
 * Minecraft/advancement operation without requiring a classifier call.
 */
function minecraftAdvancementIntent(
  text
) {
  const advancement =
    /\b(achievement|achievements|achivement|achivements|advancement|advancements|erfolg|erfolge|fortschritt|fortschritte)\b/i
      .test(
        text
      );

  const minecraftContext =
    /\b(minecraft|minecraft-server|player|spieler)\b/i
      .test(
        text
      );

  return (
    advancement &&
    minecraftContext
  );
}


function minecraftAdvancementContinuationIntent(
  text,
  recentText
) {
  const previousMinecraftTask =
    /\b(minecraft|achievement|achivement|advancement|erfolg|fortschritt)\b/i
      .test(
        recentText
      );

  const playerFollowup =
    /^(?:(?:und|and)\s+)?(?:für|for)\s+(?:[A-Za-z0-9_]{1,32}|<VEC_[A-Z_]+_[a-f0-9]{32}>)\s*[?!.]?$/i
      .test(
        text
      );

  return (
    previousMinecraftTask &&
    playerFollowup
  );
}


function genericKnowledgeIntent(
  text
) {
  return (
    /\b(was ist|was sind|what is|what are|erklär|erkläre|erklären|explain|definition|wie funktioniert|how does|wofür ist|what does)\b/i
      .test(
        text
      )
  );
}


function serverContinuationIntent(
  text,
  recentText
) {
  if (
    !serverContextIntent(
      recentText
    )
  ) {
    return false;
  }


  const anaphoric =
    /\b(welche|welcher|welches|which|davon|those|them|deren|dessen|dem|dieser|diese|dieses|that one)\b/i
      .test(
        text
      );


  const operational =
    /\b(cpu|ram|memory|speicher|leistung|auslastung|verbrauch|usage|logs?|status|ports?|uptime|resources?|ressourcen|laufen|running|am meisten|most|highest|top)\b/i
      .test(
        text
      );


  if (
    genericKnowledgeIntent(
      text
    ) &&
    !operational &&
    !anaphoric
  ) {
    return false;
  }


  return (
    anaphoric ||
    operational
  );
}


function projectIntent(
  text,
  projectId
) {
  if (
    projectId
  ) {
    return true;
  }

  return (
    /\b(this project|current project|dieses projekt|meinem projekt|project files?|projektdateien)\b/i
      .test(
        text
      )
  );
}


function networkIntent(
  text
) {
  const operation =
    /\b(scan|port scan|network scan|dns|resolve|tcp|http probe|reachability|reachable|port check|netzwerk scan|port prüfen|dns lookup)\b/i
      .test(
        text
      );

  const target =
    /\b(?:\d{1,3}\.){3}\d{1,3}\b/
      .test(
        text
      ) ||
    /\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b/i
      .test(
        text
      );

  return (
    operation &&
    target
  );
}


function sandboxIntent(
  text
) {
  return (
    /\b(run|execute|compile|test|benchmark|lint)\b.{0,35}\b(code|script|command|program|project|python|javascript|typescript|java|shell|bash)\b/i
      .test(
        text
      ) ||
    /\b(code|script|python|javascript|typescript|java|shell|bash)\b.{0,35}\b(run|execute|compile|test|benchmark|lint)\b/i
      .test(
        text
      )
  );
}


function deepIntent(
  text
) {
  return (
    /\b(deep analysis|deep dive|comprehensive analysis|comprehensive comparison|thorough analysis|in-depth|research deeply)\b/i
      .test(
        text
      ) ||
    /\b(architecture|architectural design|system design)\b/i
      .test(
        text
      ) &&
    /\b(trade-?offs?|multi-agent|scalable|secure|production|design|compare|several approaches|multiple approaches)\b/i
      .test(
        text
      ) ||
    /\b(compare|evaluate)\b.{0,60}\b(several|multiple|different)\b.{0,60}\b(approaches|options|architectures|strategies)\b/i
      .test(
        text
      )
  );
}


function executionLimits(
  executionClass
) {
  switch (
    executionClass
  ) {
    case "fast":
      return {
        rounds:
          1,

        artifactRecovery:
          0
      };

    case "artifact":
      return {
        rounds:
          5,

        artifactRecovery:
          1
      };

    case "tool":
      return {
        rounds:
          6,

        artifactRecovery:
          0
      };

    case "deep":
    default:
      return {
        rounds:
          14,

        artifactRecovery:
          2
      };
  }
}


export function classifyExecution({
  taskText = "",
  mode = "normal",
  webSearch = false,
  projectId = null,
  attachmentIds = [],
  allowServer = false,
  recentMessages = []
} = {}) {
  const text =
    normalizedText(
      taskText
    );

  const recentText =
    recentContextText(
      recentMessages
    );

  const artifact =
    artifactIntent(
      text
    );

  const web =
    webIntent(
      text,
      webSearch
    );

  const directServer =
    (
      serverIntent(
        text
      ) ||
      serverStateIntent(
        text
      ) ||
      (/\b(minecraft)\b/i.test(text) && /\b(rekor[dt]e?n?|statistik\w*|statistics|records?|mobkills|spielzeit|spielerkills|tode)\b/i.test(text)
        && (/\bserver\b/i.test(text) || /\b(?:hat|has|von|für|for|of)\s+(?!(?:ein|eine|der|die|das|the|a|an)\b)[A-Za-z0-9_]{1,16}\b/i.test(text)) && !/^(?:was ist (?:ein|eine)|was sind (?:rekorde|statistiken)|what is (?:a|an)|wie (?:funktioniert|funktionieren|berechnet)|how (?:do|does)|erklär(?:e)?)\b/i.test(text))
    );

  const continuityServer =
    serverContinuationIntent(
      text,
      recentText
    );

  const minecraftServer =
    Boolean(
      allowServer &&
      (
        minecraftAdvancementIntent(
          text
        ) ||
        minecraftAdvancementContinuationIntent(
          text,
          recentText
        )
      )
    );

  const server =
    Boolean(
      allowServer &&
      (
        directServer ||
        continuityServer ||
        minecraftServer
      )
    );

  const serverMinecraft =
    Boolean(
      server &&
      minecraftServer
    );

  const serverStats =
    Boolean(
      server &&
      serverStatsIntent(
        text
      )
    );

  const serverLogs =
    Boolean(
      server &&
      serverLogsIntent(
        text
      )
    );

  const project =
    projectIntent(
      text,
      projectId
    );

  const network =
    networkIntent(
      text
    );

  const sandbox =
    sandboxIntent(
      text
    );

  const attachments =
    Array.isArray(
      attachmentIds
    )
      ? attachmentIds.length
      : 0;

  /*
   * Artifact intent wins over generic words such as
   * create/build/review.
   *
   * Deep mode still influences provider/model selection through mode,
   * but file generation uses the dedicated Artifact runtime.
   */
  if (
    artifact
  ) {
    const requirements = {
      artifact:
        true,

      web,

      server,

      serverStats,
      serverLogs,
      serverMinecraft,
      serverContinuation:
        continuityServer,

      project,

      network,

      sandbox:
        false,

      attachments,

      functionTools:
        true
    };

    return {
      class:
        "artifact",

      reason:
        "explicit-file-generation",

      progress:
        "Preparing requested file",

      requirements,

      limits:
        executionLimits(
          "artifact"
        )
    };
  }


  /*
   * An explicit Deep/Research mode is authoritative.
   */
  if (
    mode === "deep" ||
    mode === "research"
  ) {
    const requirements = {
      artifact:
        false,

      web:
        web ||
        mode === "research",

      server,

      serverStats,
      serverLogs,
      serverMinecraft,
      serverContinuation:
        continuityServer,

      project,

      network,

      sandbox,

      attachments,

      /*
       * The existing Deep workflow can use Vector tools.
       */
      functionTools:
        true
    };

    return {
      class:
        "deep",

      reason:
        `explicit-${mode}`,

      progress:
        mode === "research"
          ? "Researching request"
          : "Working through complex request",

      requirements,

      limits:
        executionLimits(
          "deep"
        )
    };
  }


  /*
   * Real-world state requires a bounded tool path.
   */
  if (
    web ||
    server ||
    project ||
    network ||
    sandbox
  ) {
    const requirements = {
      artifact:
        false,

      web,
      server,
      serverStats,
      serverLogs,
      serverMinecraft,
      serverContinuation:
        continuityServer,
      project,
      network,
      sandbox,
      attachments,

      /*
       * Native web_search does not require function tools.
       */
      functionTools:
        Boolean(
          server ||
          project ||
          network ||
          sandbox
        )
    };

    let reason =
      "tool-required";

    let progress =
      "Checking required data";

    if (server) {
      reason =
        serverMinecraft
          ? "minecraft-player-state-required"
          : continuityServer
            ? "server-continuation-required"
            : "server-state-required";

      progress =
        serverMinecraft
          ? "Checking Minecraft player progress"
          : serverStats
            ? "Checking container resources"
            : serverLogs
              ? "Checking server logs"
              : "Checking server";
    } else if (project) {
      reason =
        "project-context-required";

      progress =
        "Inspecting project";
    } else if (network) {
      reason =
        "network-state-required";

      progress =
        "Checking network target";
    } else if (sandbox) {
      reason =
        "code-execution-required";

      progress =
        "Running technical checks";
    } else if (web) {
      reason =
        "fresh-web-data-required";

      progress =
        "Searching the web";
    }

    return {
      class:
        "tool",

      reason,
      progress,
      requirements,

      limits:
        executionLimits(
          "tool"
        )
    };
  }


  /*
   * Auto-escalate only genuinely complex tasks.
   *
   * Individual words such as create/code/project/security/review do
   * NOT trigger Deep mode.
   */
  if (
    deepIntent(
      text
    )
  ) {
    return {
      class:
        "deep",

      reason:
        "complexity-signals",

      progress:
        "Working through complex request",

      requirements: {
        artifact:
          false,

        web:
          false,

        server:
          false,

        project:
          false,

        network:
          false,

        sandbox:
          false,

        attachments,

        functionTools:
          true
      },

      limits:
        executionLimits(
          "deep"
        )
    };
  }


  /*
   * Default path.
   *
   * Conversational answers, rewrites, translation, explanation,
   * brainstorming and ordinary coding questions should be fast.
   */
  return {
    class:
      "fast",

    reason:
      "direct-response",

    progress:
      "Generating response",

    requirements: {
      artifact:
        false,

      web:
        false,

      server:
        false,

      project:
        false,

      network:
        false,

      sandbox:
        false,

      attachments,

      functionTools:
        false
    },

    limits:
      executionLimits(
        "fast"
      )
  };
}

