/*
 * VECTOR_ARTIFACT_INTELLIGENCE_575
 *
 * Shared semantic planning layer for:
 *
 *   PDF
 *   DOCX
 *   XLSX
 *
 * Provider-independent.
 *
 * This module does NOT call an AI provider.
 * It converts a user's artifact intent and supplied content/data into
 * a deterministic semantic document plan.
 */


function cleanText(
  value
) {
  return String(
    value ||
    ""
  )
    .replace(
      /\s+/g,
      " "
    )
    .trim();
}


function lowerText(
  value
) {
  return cleanText(
    value
  ).toLowerCase();
}


export function humanizeArtifactLabel(
  value
) {
  let text =
    cleanText(
      value
    );


  if (!text) {
    return "";
  }


  /*
   * Remove namespaces such as:
   *
   *   minecraft:walk_one_cm
   *   custom:some_value
   */
  if (
    text.includes(
      ":"
    )
  ) {
    text =
      text.split(
        ":"
      ).pop();
  }


  text =
    text
      .replace(
        /[_\-]+/g,
        " "
      )
      .replace(
        /([a-z0-9])([A-Z])/g,
        "$1 $2"
      )
      .replace(
        /\s+/g,
        " "
      )
      .trim();


  const words =
    text.split(
      " "
    );


  const preserveUppercase =
    new Set([
      "id",
      "uuid",
      "url",
      "api",
      "ip",
      "cpu",
      "ram",
      "gpu",
      "pdf",
      "docx",
      "xlsx",
      "chf",
      "usd",
      "eur",
      "gb",
      "mb",
      "kb",
      "cm",
      "km",
      "ms",
      "kpi"
    ]);


  return words
    .map(
      (
        word
      ) => {
        const lower =
          word.toLowerCase();


        if (
          preserveUppercase.has(
            lower
          )
        ) {
          return lower.toUpperCase();
        }


        return (
          lower.charAt(
            0
          ).toUpperCase() +
          lower.slice(
            1
          )
        );
      }
    )
    .join(
      " "
    );
}


function numericValues(
  values
) {
  return (
    values ||
    []
  ).filter(
    (
      value
    ) =>
      typeof value ===
        "number" &&
      Number.isFinite(
        value
      )
  );
}


function booleanValues(
  values
) {
  return (
    values ||
    []
  ).filter(
    (
      value
    ) =>
      typeof value ===
      "boolean"
  );
}


export function inferArtifactSemanticType({
  name,
  values = []
}) {
  const key =
    lowerText(
      name
    );

  const numbers =
    numericValues(
      values
    );


  if (
    /\b(uuid|guid|identifier)\b/.test(
      key
    ) ||
    /(^|[_\s])id$/.test(
      key
    )
  ) {
    return {
      type:
        "identifier",

      displayUnit:
        null
    };
  }


  if (
    /(percent|percentage|ratio|rate|conversion|success rate|failure rate|\bpct\b)/.test(
      key
    )
  ) {
    return {
      type:
        "percentage",

      displayUnit:
        "%"
    };
  }


  if (
    /(chf|usd|eur|gbp|currency|revenue|price|cost|budget|spend|amount|sales)/.test(
      key
    )
  ) {
    let currency =
      null;


    if (
      /\bchf\b/.test(
        key
      )
    ) {
      currency =
        "CHF";

    } else if (
      /\busd\b/.test(
        key
      )
    ) {
      currency =
        "USD";

    } else if (
      /\beur\b/.test(
        key
      )
    ) {
      currency =
        "EUR";

    } else if (
      /\bgbp\b/.test(
        key
      )
    ) {
      currency =
        "GBP";
    }


    return {
      type:
        "currency",

      displayUnit:
        currency
    };
  }


  if (
    /(duration|play[ _-]?time|uptime|elapsed|hours?|minutes?|seconds?|milliseconds?|ticks?)/.test(
      key
    )
  ) {
    return {
      type:
        "duration",

      displayUnit:
        "human"
    };
  }


  if (
    /(distance|kilomet|kilometer|\bkm\b|centimet|\bcm\b|metres?|meters?|miles?|walking|sprinting|elytra|swimming|travel)/.test(
      key
    )
  ) {
    return {
      type:
        "distance",

      displayUnit:
        "human"
    };
  }


  if (
    /(bytes?|file size|storage|memory|disk size|payload size)/.test(
      key
    )
  ) {
    return {
      type:
        "bytes",

      displayUnit:
        "human"
    };
  }


  if (
    /(date|timestamp|created at|updated at|modified at|deadline|start date|end date)/.test(
      key
    )
  ) {
    return {
      type:
        "datetime",

      displayUnit:
        "locale"
    };
  }


  if (
    booleanValues(
      values
    ).length >
    0
  ) {
    return {
      type:
        "boolean",

      displayUnit:
        null
    };
  }


  if (
    numbers.length >
    0
  ) {
    const integers =
      numbers.every(
        (
          value
        ) =>
          Number.isInteger(
            value
          )
      );


    if (
      integers &&
      /(count|total|kills?|deaths?|items?|blocks?|players?|users?|requests?|events?|records?|wins?|jumps?|trades?)/.test(
        key
      )
    ) {
      return {
        type:
          "count",

        displayUnit:
          null
      };
    }


    return {
      type:
        integers
          ? "integer"
          : "number",

      displayUnit:
        null
    };
  }


  return {
    type:
      "text",

    displayUnit:
      null
  };
}


function detectArtifactAudience(
  combined
) {
  const text =
    lowerText(
      combined
    );


  if (
    /(?:\bexecutive\b|\bmanagement\b|\bleadership\b|\bboard\b|\bc-level\b|\bc level\b)/.test(
      text
    )
  ) {
    return "executive";
  }


  if (
    /(?:\bengineers?\b|\badministrators?\b|\badmins?\b|\bdevelopers?\b|\btechnical\b|\bsoc\b|\bsecurity team\b|\boperations\b|\bit team\b)/.test(
      text
    )
  ) {
    return "technical";
  }


  if (
    /(?:\bcustomers?\b|\bclients?\b|\bkunden?\b)/.test(
      text
    )
  ) {
    return "customer";
  }


  if (
    /(?:\bfor\s+(?:(?:our|the)\s+)?(?:players|members)\b|\bfor\s+(?:our|the)\s+community\b|\bfor\s+discord\s+members\b|\bintended\s+for\s+(?:(?:our|the)\s+)?(?:players|members)\b|\bintended\s+for\s+(?:our|the)\s+community\b|\baimed\s+at\s+(?:(?:our|the)\s+)?(?:players|members)\b|\baimed\s+at\s+(?:our|the)\s+community\b|\b(?:community|player|member|discord)\s+audience\b|\b(?:community|player|member|discord)[ -]facing\b|\bpublic\s+audience\b)/.test(
      text
    )
  ) {
    return "community";
  }


  return "general";
}


function detectArtifactArchetype({
  format,
  combined
}) {
  if (
    /(incident report|security incident|postmortem|post-mortem|root cause analysis|rca)/.test(
      combined
    )
  ) {
    return "incident_report";
  }


  if (
    /(runbook|playbook|operational procedure|standard operating procedure|\bsop\b)/.test(
      combined
    )
  ) {
    return "runbook";
  }


  if (
    /(meeting notes|meeting minutes|minutes of meeting|besprechungsnotizen|sitzungsprotokoll)/.test(
      combined
    )
  ) {
    return "meeting_notes";
  }


  if (
    /(proposal|offer|quotation|angebot|project proposal)/.test(
      combined
    )
  ) {
    return "proposal";
  }


  if (
    /(comparison|compare|versus|\bvs\b|evaluation|nutzwertanalyse)/.test(
      combined
    )
  ) {
    return "comparison";
  }


  if (
    /(budget|forecast|financial|finance|profit|loss|cash flow|cashflow)/.test(
      combined
    )
  ) {
    return (
      format ===
      "xlsx"
        ? "financial_workbook"
        : "financial_report"
    );
  }


  if (
    /(inventory|asset list|stock list|bestand|inventar)/.test(
      combined
    )
  ) {
    return "inventory";
  }


  if (
    /(tracker|project tracker|task tracker|status tracker|pipeline)/.test(
      combined
    )
  ) {
    return "tracker";
  }


  if (
    /(?:\bexecutive\b.{0,80}\b(report|summary|brief|review)\b|\bmanagement\b.{0,80}\b(report|summary|brief|review)\b|\bboard\b.{0,80}\b(report|summary|brief|review)\b)/.test(
      combined
    )
  ) {
    return "executive_report";
  }


  if (
    /(technical report|technical documentation|architecture document|system design)/.test(
      combined
    )
  ) {
    return "technical_report";
  }


  if (
    /(analysis|analyse|research|investigation|findings)/.test(
      combined
    )
  ) {
    return "analysis";
  }


  if (
    /(statistics|stats|dataset|data set|dashboard|workbook|spreadsheet|excel|xlsx)/.test(
      combined
    )
  ) {
    return "dataset_report";
  }


  return (
    format ===
    "xlsx"
      ? "dataset_report"
      : "report"
  );
}


function defaultSectionsFor({
  archetype,
  format
}) {
  const sections = {
    report: [
      "Executive Summary",
      "Key Findings",
      "Details",
      "Conclusion"
    ],

    executive_report: [
      "Executive Summary",
      "Key Metrics",
      "Key Findings",
      "Risks and Implications",
      "Recommended Next Steps"
    ],

    technical_report: [
      "Overview",
      "Scope",
      "Technical Findings",
      "Evidence",
      "Risks",
      "Recommendations"
    ],

    incident_report: [
      "Executive Summary",
      "Incident Overview",
      "Timeline",
      "Technical Findings",
      "Impact",
      "Root Cause",
      "Actions Taken",
      "Recommendations"
    ],

    analysis: [
      "Summary",
      "Methodology",
      "Key Findings",
      "Detailed Analysis",
      "Conclusion"
    ],

    comparison: [
      "Summary",
      "Evaluation Criteria",
      "Comparison",
      "Trade-offs",
      "Conclusion"
    ],

    proposal: [
      "Executive Summary",
      "Objectives",
      "Proposed Approach",
      "Scope",
      "Timeline",
      "Risks",
      "Next Steps"
    ],

    meeting_notes: [
      "Meeting Overview",
      "Discussion",
      "Decisions",
      "Action Items"
    ],

    runbook: [
      "Purpose",
      "Prerequisites",
      "Procedure",
      "Verification",
      "Troubleshooting",
      "Rollback"
    ],

    financial_report: [
      "Executive Summary",
      "Key Financial Metrics",
      "Performance",
      "Variances",
      "Outlook"
    ],

    dataset_report: [
      "Dashboard",
      "Summary",
      "Detailed Views",
      "Raw Data"
    ],

    financial_workbook: [
      "Dashboard",
      "Summary",
      "Actuals",
      "Forecast",
      "Raw Data"
    ],

    inventory: [
      "Summary",
      "Inventory",
      "Exceptions",
      "Raw Data"
    ],

    tracker: [
      "Dashboard",
      "Active Items",
      "Completed Items",
      "Raw Data"
    ]
  };


  const selected =
    sections[
      archetype
    ] ||
    sections.report;


  /*
   * For spreadsheets these represent sheet roles.
   * For PDF/DOCX they represent document sections.
   */
  return selected.map(
    (
      title,
      index
    ) => ({
      order:
        index + 1,

      title,

      role:
        index ===
        0
          ? "summary"
          : (
              /raw data/i.test(
                title
              )
                ? "raw"
                : "detail"
            ),

      format
    })
  );
}


function sheetRole(
  name,
  index,
  total
) {
  const lower =
    lowerText(
      name
    );


  if (
    /(raw|source|all data|all statistics|complete data|export)/.test(
      lower
    )
  ) {
    return "raw";
  }


  if (
    /(dashboard|overview|summary|executive)/.test(
      lower
    )
  ) {
    return "summary";
  }


  if (
    /(metadata|technical metadata|source info)/.test(
      lower
    )
  ) {
    return "metadata";
  }


  if (
    index ===
      total - 1 &&
    total >
      1
  ) {
    return "detail";
  }


  return "detail";
}


function analyzeSheet(
  sheet,
  index,
  total
) {
  const rows =
    Array.isArray(
      sheet?.rows
    )
      ? sheet.rows
      : [];


  const headerRow =
    Array.isArray(
      rows[0]
    )
      ? rows[0]
      : [];


  const columnCount =
    rows.reduce(
      (
        maximum,
        row
      ) =>
        Math.max(
          maximum,
          Array.isArray(
            row
          )
            ? row.length
            : 1
        ),
      0
    );


  const columns = [];


  for (
    let columnIndex = 0;
    columnIndex <
      columnCount;
    columnIndex += 1
  ) {
    const rawName =
      headerRow[
        columnIndex
      ];


    const name =
      cleanText(
        rawName
      ) ||
      `Column ${columnIndex + 1}`;


    const sampleValues =
      rows
        .slice(
          1,
          201
        )
        .map(
          (
            row
          ) =>
            Array.isArray(
              row
            )
              ? row[
                  columnIndex
                ]
              : (
                  columnIndex ===
                    0
                    ? row
                    : null
                )
        )
        .filter(
          (
            value
          ) =>
            value !==
              undefined &&
            value !==
              null &&
            value !==
              ""
        );


    const semantic =
      inferArtifactSemanticType({
        name,
        values:
          sampleValues
      });


    columns.push({
      index:
        columnIndex,

      sourceName:
        name,

      displayName:
        humanizeArtifactLabel(
          name
        ),

      semanticType:
        semantic.type,

      displayUnit:
        semantic.displayUnit,

      sampleCount:
        sampleValues.length
    });
  }


  return {
    index,

    name:
      cleanText(
        sheet?.name
      ) ||
      `Sheet ${index + 1}`,

    role:
      sheetRole(
        sheet?.name,
        index,
        total
      ),

    rowCount:
      rows.length,

    dataRowCount:
      Math.max(
        0,
        rows.length -
        (
          headerRow.length >
          0
            ? 1
            : 0
        )
      ),

    columnCount,

    columns
  };
}


function presentationFor({
  format,
  archetype,
  audience,
  dataHeavy
}) {
  if (
    format ===
    "xlsx"
  ) {
    return {
      summaryFirst:
        true,

      preserveRawData:
        true,

      freezeHeaders:
        true,

      filters:
        true,

      nativeNumberFormats:
        true,

      humanReadableUnits:
        true,

      conditionalFormatting:
        dataHeavy,

      charts:
        dataHeavy,

      technicalMetadataLast:
        true,

      audience
    };
  }


  return {
    titleHierarchy:
      true,

    executiveSummary:
      ![
        "meeting_notes",
        "runbook"
      ].includes(
        archetype
      ),

    pageNumbers:
      true,

    headersAndFooters:
      true,

    readableTables:
      true,

    callouts:
      true,

    charts:
      dataHeavy,

    avoidOrphanHeadings:
      true,

    audience
  };
}


export function buildArtifactPlan({
  requestText = "",
  format = "",
  title = "",
  content = "",
  sheets = []
} = {}) {
  const normalizedFormat =
    lowerText(
      format
    );


  const combined =
    lowerText(
      [
        requestText,
        title,
        String(
          content ||
          ""
        ).slice(
          0,
          5000
        )
      ].join(
        " "
      )
    );


  const archetype =
    detectArtifactArchetype({
      format:
        normalizedFormat,

      combined
    });


  const audience =
    detectArtifactAudience(
      combined
    );


  const analyzedSheets =
    (
      Array.isArray(
        sheets
      )
        ? sheets
        : []
    ).map(
      (
        sheet,
        index,
        all
      ) =>
        analyzeSheet(
          sheet,
          index,
          all.length
        )
    );


  const totalRows =
    analyzedSheets.reduce(
      (
        total,
        sheet
      ) =>
        total +
        sheet.dataRowCount,
      0
    );


  const totalColumns =
    analyzedSheets.reduce(
      (
        total,
        sheet
      ) =>
        total +
        sheet.columnCount,
      0
    );


  const dataHeavy =
    totalRows >=
      50 ||
    totalColumns >=
      20;


  return {
    version:
      "5.7.5",

    format:
      normalizedFormat,

    archetype,

    audience,

    purpose:
      archetype.replace(
        /_/g,
        " "
      ),

    dataProfile: {
      sheetCount:
        analyzedSheets.length,

      totalRows,

      totalColumns,

      dataHeavy,

      sheets:
        analyzedSheets
    },

    sections:
      defaultSectionsFor({
        archetype,
        format:
          normalizedFormat
      }),

    presentation:
      presentationFor({
        format:
          normalizedFormat,

        archetype,
        audience,
        dataHeavy
      }),

    qualityRules: [
      "Lead with the information most useful to the reader.",
      "Prefer clear summaries over raw technical dumps.",
      "Preserve complete raw/source data when the user requested completeness.",
      "Translate machine-oriented labels into readable labels where possible.",
      "Keep identifiers and original source fields available when traceability matters.",
      "Use human-readable units and native numeric types.",
      "Avoid duplicate sections and redundant tables.",
      "Use tables for structured comparisons instead of dense prose.",
      "Keep technical metadata visually secondary to useful content.",
      "Never silently truncate requested data."
    ]
  };
}


export function summarizeArtifactPlan(
  plan
) {
  return {
    version:
      plan?.version ||
      null,

    format:
      plan?.format ||
      null,

    archetype:
      plan?.archetype ||
      null,

    audience:
      plan?.audience ||
      null,

    dataHeavy:
      Boolean(
        plan
          ?.dataProfile
          ?.dataHeavy
      ),

    sections:
      (
        plan?.sections ||
        []
      ).map(
        (
          section
        ) =>
          section.title
      ),

    sheets:
      (
        plan
          ?.dataProfile
          ?.sheets ||
        []
      ).map(
        (
          sheet
        ) => ({
          name:
            sheet.name,

          role:
            sheet.role,

          rows:
            sheet.dataRowCount,

          columns:
            sheet.columnCount
        })
      )
  };
}
