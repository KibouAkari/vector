/*
 * VECTOR_DOCUMENT_READING_573
 * Local extraction only. Extracted content still passes through
 * Vector's privacy sanitizer before any external model sees it.
 */

const DOCUMENT_EXTENSIONS = new Map([
  [".pdf", "pdf"],
  [".docx", "docx"],
  [".xlsx", "xlsx"]
]);

const DOCUMENT_MIMES = new Map([
  ["application/pdf", "pdf"],
  ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"],
  ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"]
]);

function envNumber(name, fallback, min, max) {
  const value = Number(process.env[name] || fallback);

  if (!Number.isFinite(value)) {
    return fallback;
  }

  return Math.min(max, Math.max(min, value));
}

export function documentKindForAttachment({
  filename,
  mimeType,
  extension
}) {
  const mime = String(mimeType || "").trim().toLowerCase();

  if (DOCUMENT_MIMES.has(mime)) {
    return DOCUMENT_MIMES.get(mime);
  }

  let ext = String(extension || "").trim().toLowerCase();

  if (!ext && filename) {
    ext =
      String(filename)
        .toLowerCase()
        .match(/\.[a-z0-9]+$/)?.[0] ||
      "";
  }

  return DOCUMENT_EXTENSIONS.get(ext) || null;
}

function cleanText(value) {
  return String(value || "")
    .replace(/\u0000/g, "")
    .replace(/\r\n?/g, "\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{4,}/g, "\n\n\n")
    .trim();
}

function withTimeout(promise, milliseconds, label) {
  let timer;

  const timeout =
    new Promise(
      (resolve, reject) => {
        timer =
          setTimeout(
            () => {
              reject(
                new Error(
                  `${label} exceeded Vector's ${Math.round(
                    milliseconds / 1000
                  )} second extraction limit.`
                )
              );
            },
            milliseconds
          );
      }
    );

  return Promise.race([
    promise,
    timeout
  ]).finally(
    () => clearTimeout(timer)
  );
}

async function extractPdf(buffer) {
  const {
    extractText,
    getDocumentProxy
  } =
    await import("unpdf");

  const maxPages =
    envNumber(
      "VECTOR_PDF_MAX_PAGES",
      100,
      1,
      500
    );

  const maxImageSize =
    envNumber(
      "VECTOR_PDF_MAX_IMAGE_PIXELS",
      16777216,
      1048576,
      67108864
    );

  const pdf =
    await getDocumentProxy(
      new Uint8Array(buffer),
      {
        maxImageSize
      }
    );

  try {
    if (
      Number(
        pdf.numPages ||
        0
      ) >
      maxPages
    ) {
      throw new Error(
        `PDF contains ${pdf.numPages} pages; Vector's current limit is ${maxPages}.`
      );
    }

    const result =
      await extractText(
        pdf,
        {
          mergePages: true
        }
      );

    const text =
      cleanText(
        result.text
      );

    return {
      kind:
        "PDF",

      text:
        text ||
        "[No extractable text was found. This PDF may be scanned/image-only. OCR is not enabled yet.]",

      metadata: {
        pages:
          Number(
            result.totalPages ||
            pdf.numPages ||
            0
          )
      }
    };
  } finally {
    try {
      await pdf.destroy?.();
    } catch {
      // Best-effort cleanup.
    }
  }
}

async function extractDocx(buffer) {
  const imported =
    await import("mammoth");

  const mammoth =
    imported.default ||
    imported;

  const result =
    await mammoth.extractRawText({
      buffer
    });

  const text =
    cleanText(
      result.value
    );

  return {
    kind:
      "DOCX",

    text:
      text ||
      "[No extractable text was found in this DOCX file.]",

    metadata: {
      warnings:
        Array.isArray(
          result.messages
        )
          ? result.messages.length
          : 0
    }
  };
}

function excelCellText(value) {
  if (
    value === null ||
    value === undefined
  ) {
    return "";
  }

  if (
    [
      "string",
      "number",
      "boolean",
      "bigint"
    ].includes(
      typeof value
    )
  ) {
    return String(value);
  }

  if (value instanceof Date) {
    return value.toISOString();
  }

  if (
    typeof value ===
    "object"
  ) {
    if (
      Array.isArray(
        value.richText
      )
    ) {
      return value.richText
        .map(
          (part) =>
            String(
              part?.text ||
              ""
            )
        )
        .join("");
    }

    if (
      value.text !==
      undefined
    ) {
      return String(
        value.text
      );
    }

    if (
      value.result !==
      undefined
    ) {
      return excelCellText(
        value.result
      );
    }

    if (
      value.formula !==
      undefined
    ) {
      return (
        value.result !==
          undefined
          ? excelCellText(
              value.result
            )
          : `=${value.formula}`
      );
    }

    if (
      value.hyperlink !==
      undefined
    ) {
      return String(
        value.text ||
        value.hyperlink ||
        ""
      );
    }

    if (
      value.error !==
      undefined
    ) {
      return String(
        value.error ||
        ""
      );
    }
  }

  return String(value);
}

async function extractXlsx(buffer) {
  const imported =
    await import("exceljs");

  const ExcelJS =
    imported.default ||
    imported;

  const Workbook =
    ExcelJS.Workbook ||
    imported.Workbook;

  if (!Workbook) {
    throw new Error(
      "ExcelJS Workbook runtime is unavailable."
    );
  }

  const workbook =
    new Workbook();

  await workbook.xlsx.load(
    buffer,
    {
      ignoreNodes: [
        "dataValidations",
        "conditionalFormatting",
        "extLst"
      ]
    }
  );

  const maxSheets =
    envNumber(
      "VECTOR_XLSX_MAX_SHEETS",
      20,
      1,
      100
    );

  const maxRows =
    envNumber(
      "VECTOR_XLSX_MAX_ROWS_PER_SHEET",
      500,
      10,
      5000
    );

  const maxCells =
    envNumber(
      "VECTOR_XLSX_MAX_CELLS",
      12000,
      100,
      100000
    );

  const parts = [];

  let sheetsRead = 0;
  let cellsRead = 0;
  let truncated = false;

  workbook.eachSheet(
    (worksheet) => {
      if (
        sheetsRead >=
        maxSheets
      ) {
        truncated = true;
        return;
      }

      sheetsRead += 1;

      parts.push(
        `## Sheet: ${worksheet.name}`
      );

      const actualRows =
        Number(
          worksheet.actualRowCount ||
          worksheet.rowCount ||
          0
        );

      const rowLimit =
        Math.min(
          actualRows,
          maxRows
        );

      if (
        actualRows >
        rowLimit
      ) {
        truncated = true;
      }

      for (
        let rowNumber = 1;
        rowNumber <= rowLimit;
        rowNumber += 1
      ) {
        if (
          cellsRead >=
          maxCells
        ) {
          truncated = true;
          break;
        }

        const row =
          worksheet.getRow(
            rowNumber
          );

        const values = [];

        const columnLimit =
          Math.min(
            Number(
              worksheet.actualColumnCount ||
              worksheet.columnCount ||
              row.cellCount ||
              0
            ),
            100
          );

        for (
          let column = 1;
          column <= columnLimit;
          column += 1
        ) {
          if (
            cellsRead >=
            maxCells
          ) {
            truncated = true;
            break;
          }

          values.push(
            excelCellText(
              row
                .getCell(
                  column
                )
                .value
            )
              .replace(
                /\t/g,
                " "
              )
              .replace(
                /\r?\n/g,
                " "
              )
          );

          cellsRead += 1;
        }

        while (
          values.length >
            0 &&
          values[
            values.length -
            1
          ] ===
            ""
        ) {
          values.pop();
        }

        if (
          values.some(
            (value) =>
              value !==
              ""
          )
        ) {
          parts.push(
            values.join(
              "\t"
            )
          );
        }
      }

      parts.push("");
    }
  );

  if (truncated) {
    parts.push(
      "[Spreadsheet extraction truncated by Vector's safety limits.]"
    );
  }

  const text =
    cleanText(
      parts.join(
        "\n"
      )
    );

  return {
    kind:
      "XLSX",

    text:
      text ||
      "[No readable cell content was found in this workbook.]",

    metadata: {
      sheets:
        sheetsRead,

      cells:
        cellsRead,

      truncated
    }
  };
}

export async function extractDocumentAttachment({
  buffer,
  filename,
  mimeType,
  extension
}) {
  if (
    !Buffer.isBuffer(
      buffer
    )
  ) {
    throw new Error(
      "Document extraction requires a Buffer."
    );
  }

  const kind =
    documentKindForAttachment({
      filename,
      mimeType,
      extension
    });

  if (!kind) {
    return null;
  }

  const maxBytes =
    envNumber(
      "VECTOR_DOCUMENT_MAX_MB",
      15,
      1,
      25
    ) *
    1024 *
    1024;

  if (
    buffer.length >
    maxBytes
  ) {
    throw new Error(
      `${filename || "Document"} is larger than Vector's ${Math.round(
        maxBytes /
        1024 /
        1024
      )} MB document-reading limit.`
    );
  }

  const timeoutMs =
    envNumber(
      "VECTOR_DOCUMENT_EXTRACT_TIMEOUT_MS",
      20000,
      5000,
      60000
    );

  if (
    kind ===
    "pdf"
  ) {
    return withTimeout(
      extractPdf(
        buffer
      ),
      timeoutMs,
      "PDF extraction"
    );
  }

  if (
    kind ===
    "docx"
  ) {
    return withTimeout(
      extractDocx(
        buffer
      ),
      timeoutMs,
      "DOCX extraction"
    );
  }

  if (
    kind ===
    "xlsx"
  ) {
    return withTimeout(
      extractXlsx(
        buffer
      ),
      timeoutMs,
      "XLSX extraction"
    );
  }

  return null;
}
