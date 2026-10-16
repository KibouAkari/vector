import crypto from "node:crypto";

const LEVEL_SCORE = {
  public: 0,
  internal: 1,
  confidential: 2,
  restricted: 3
};

function highestLevel(
  current,
  candidate
) {
  return (
    LEVEL_SCORE[candidate] >
    LEVEL_SCORE[current]
  )
    ? candidate
    : current;
}

function placeholder(
  type
) {
  const id =
    crypto
      .randomBytes(3)
      .toString("hex")
      .toUpperCase();

  return (
    `<${type}_${id}>`
  );
}

const RULES = [
  {
    type:
      "PRIVATE_KEY",

    findingType:
      "private_key",

    level:
      "restricted",

    regex:
      /-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/gi,

    getValue:
      (match) =>
        match[0],

    replace:
      (
        match,
        token
      ) =>
        token
  },

  {
    type:
      "BEARER_TOKEN",

    findingType:
      "bearer_token",

    level:
      "restricted",

    regex:
      /\bBearer\s+([A-Za-z0-9\-._~+/]+=*)/gi,

    getValue:
      (match) =>
        match[1],

    replace:
      (
        match,
        token
      ) =>
        `Bearer ${token}`
  },

  {
    type:
      "JWT",

    findingType:
      "jwt",

    level:
      "restricted",

    regex:
      /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\b/g,

    getValue:
      (match) =>
        match[0],

    replace:
      (
        match,
        token
      ) =>
        token
  },

  {
    type:
      "GITHUB_TOKEN",

    findingType:
      "github_token",

    level:
      "restricted",

    regex:
      /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b/g,

    getValue:
      (match) =>
        match[0],

    replace:
      (
        match,
        token
      ) =>
        token
  },

  {
    type:
      "API_KEY",

    findingType:
      "api_key",

    level:
      "restricted",

    regex:
      /\bsk-[A-Za-z0-9_-]{20,}\b/g,

    getValue:
      (match) =>
        match[0],

    replace:
      (
        match,
        token
      ) =>
        token
  },

  {
    type:
      "AWS_KEY",

    findingType:
      "aws_access_key",

    level:
      "restricted",

    regex:
      /\bAKIA[0-9A-Z]{16}\b/g,

    getValue:
      (match) =>
        match[0],

    replace:
      (
        match,
        token
      ) =>
        token
  },

  {
    type:
      "PASSWORD",

    findingType:
      "password_assignment",

    level:
      "restricted",

    regex:
      /\b(password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*["']?([^\s"',;<>]{4,})["']?/gi,

    getValue:
      (match) =>
        match[2],

    replace:
      (
        match,
        token
      ) =>
        `${match[1]}=${token}`
  },

  {
    type:
      "EMAIL",

    findingType:
      "email_address",

    level:
      "confidential",

    regex:
      /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi,

    getValue:
      (match) =>
        match[0],

    replace:
      (
        match,
        token
      ) =>
        token
  },

  {
    type:
      "PRIVATE_IP",

    findingType:
      "private_ipv4",

    level:
      "confidential",

    regex:
      /\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})\b/g,

    getValue:
      (match) =>
        match[0],

    replace:
      (
        match,
        token
      ) =>
        token
  }
];

function alreadyPlaceholder(
  value
) {
  return (
    /^<[A-Z0-9_]+_[A-F0-9]{6}>$/
      .test(
        String(value)
      )
  );
}

export function sanitizeForExternal(
  input
) {
  const original =
    String(
      input || ""
    );

  let sanitized =
    original;

  let classification =
    "internal";

  const findings = [];
  const mappings = [];

  /*
   * Reuse the same placeholder when the
   * same sensitive value appears repeatedly
   * in one message.
   */
  const known =
    new Map();

  for (
    const rule
    of RULES
  ) {
    const expression =
      new RegExp(
        rule.regex.source,
        rule.regex.flags
      );

    sanitized =
      sanitized.replace(
        expression,
        (...args) => {
          const matchArray =
            args.slice(
              0,
              -2
            );

          const value =
            rule.getValue(
              matchArray
            );

          if (
            !value ||
            alreadyPlaceholder(
              value
            )
          ) {
            return args[0];
          }

          classification =
            highestLevel(
              classification,
              rule.level
            );

          let token =
            known.get(
              `${rule.type}:${value}`
            );

          if (!token) {
            token =
              placeholder(
                rule.type
              );

            known.set(
              `${rule.type}:${value}`,
              token
            );

            mappings.push({
              placeholder:
                token,

              value,
              type:
                rule.type
            });
          }

          const existing =
            findings.find(
              (finding) =>
                finding.type ===
                rule.findingType
            );

          if (existing) {
            existing.count += 1;
          } else {
            findings.push({
              type:
                rule.findingType,

              level:
                rule.level,

              count:
                1
            });
          }

          return rule.replace(
            matchArray,
            token
          );
        }
      );
  }

  return {
    original,
    sanitized,
    classification,
    findings,
    mappings,

    totalFindings:
      findings.reduce(
        (
          total,
          finding
        ) =>
          total +
          finding.count,
        0
      ),

    wasSanitized:
      sanitized !==
      original
  };
}

export function classifyPrivacy(
  input
) {
  const result =
    sanitizeForExternal(
      input
    );

  return {
    classification:
      result.classification,

    findings:
      result.findings,

    totalFindings:
      result.totalFindings,

    wasRedacted:
      result.wasSanitized,

    originalLength:
      result.original.length,

    redacted:
      result.sanitized
  };
}

export function externalAIAllowed(
  classification
) {
  if (
    classification ===
    "public"
  ) {
    return (
      process.env
        .ALLOW_EXTERNAL_AI_FOR_PUBLIC !==
      "false"
    );
  }

  if (
    classification ===
    "internal"
  ) {
    return (
      process.env
        .ALLOW_EXTERNAL_AI_FOR_INTERNAL !==
      "false"
    );
  }

  /*
   * Confidential/restricted content itself
   * is not exported.
   *
   * Once tokenize/sanitize has removed the
   * actual sensitive values, the sanitized
   * text can be externally processed.
   */
  return false;
}
