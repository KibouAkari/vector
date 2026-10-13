function normalize(
  text
) {
  return String(
    text || ""
  )
    .toLowerCase()
    .replace(
      /\s+/g,
      " "
    )
    .trim();
}

function containsAny(
  text,
  expressions
) {
  return expressions.some(
    (expression) =>
      text.includes(
        expression
      )
  );
}

function countMatches(
  text,
  expressions
) {
  return expressions.reduce(
    (
      count,
      expression
    ) =>
      text.includes(
        expression
      )
        ? count + 1
        : count,
    0
  );
}

export function shouldUseWebSearch({
  message,
  requestedMode
}) {
  const text =
    normalize(
      message
    );

  if (
    requestedMode ===
    "research"
  ) {
    return true;
  }

  const searchSignals = [
    "search the web",
    "search online",
    "web search",
    "deep search",
    "research online",
    "do research",
    "research this",
    "find online",
    "find information online",
    "look it up",
    "look online",
    "official website",
    "official information",
    "latest",
    "currently",
    "current information",
    "recent information",
    "recent news",
    "current version",
    "current price",
    "who created",
    "who built",
    "who owns"
  ];

  return containsAny(
    text,
    searchSignals
  );
}

export function determineTaskMode({
  message,
  requestedMode = "auto"
}) {
  if (
    requestedMode === "quick" ||
    requestedMode === "normal" ||
    requestedMode === "deep" ||
    requestedMode === "research"
  ) {
    return requestedMode;
  }

  const text =
    normalize(
      message
    );

  const length =
    text.length;

  const explicitDeepSignals = [
    "deep analysis",
    "deep architecture review",
    "comprehensive architecture review",
    "comprehensive security review",
    "extensive analysis",
    "production-ready architecture",
    "production ready architecture",
    "build the complete application",
    "build a complete application",
    "implement the complete application",
    "rewrite the entire repository",
    "review the entire repository",
    "analyse the entire repository",
    "analyze the entire repository",
    "full security audit",
    "complete security audit",
    "full penetration test",
    "complete penetration test"
  ];

  if (
    containsAny(
      text,
      explicitDeepSignals
    )
  ) {
    return "deep";
  }

  if (
    shouldUseWebSearch({
      message:
        text,

      requestedMode:
        "auto"
    })
  ) {
    return "research";
  }

  const technicalSignals = [
    "repository",
    "codebase",
    "multi-agent",
    "multi agent",
    "distributed system",
    "production environment",
    "production server",
    "security architecture",
    "threat model",
    "vulnerability",
    "incident response",
    "malware analysis",
    "reverse engineering",
    "penetration testing",
    "pentesting",
    "authentication system",
    "authorization system",
    "database migration",
    "system design",
    "concurrency",
    "race condition",
    "memory corruption",
    "cryptography",
    "sandbox escape",
    "exploit validation"
  ];

  const workloadSignals = [
    "implement",
    "build",
    "create the complete",
    "write the complete",
    "fix all",
    "review all",
    "analyse all",
    "analyze all",
    "end-to-end",
    "end to end",
    "with tests",
    "integration tests",
    "unit tests",
    "deploy",
    "deployment",
    "migration plan"
  ];

  const technicalScore =
    countMatches(
      text,
      technicalSignals
    );

  const workloadScore =
    countMatches(
      text,
      workloadSignals
    );

  let sizeScore =
    0;

  if (
    length >
    8000
  ) {
    sizeScore = 1;
  }

  if (
    length >
    20000
  ) {
    sizeScore = 2;
  }

  if (
    technicalScore +
    workloadScore +
    sizeScore >=
    4
  ) {
    return "deep";
  }

  const quickSignals = [
    "hi vector",
    "hello vector",
    "hello",
    "thanks",
    "thank you",
    "translate",
    "shorten",
    "fix grammar",
    "rewrite this sentence",
    "what does",
    "what is"
  ];

  if (
    length < 350 &&
    containsAny(
      text,
      quickSignals
    ) &&
    technicalScore === 0
  ) {
    return "quick";
  }

  /*
   * Technical questions are deliberately
   * not automatically classified as Quick.
   */
  if (
    length < 130 &&
    technicalScore === 0 &&
    workloadScore === 0
  ) {
    return "quick";
  }

  return "normal";
}

export function getModelForMode(
  mode
) {
  if (
    mode ===
    "deep"
  ) {
    return (
      process.env
        .VECTOR_MODEL_DEEP ||
      "gpt-6-sol"
    );
  }

  if (
    mode ===
    "research"
  ) {
    return (
      process.env
        .VECTOR_RESEARCH_MODEL ||
      "gpt-6-luna"
    );
  }

  if (
    mode ===
    "quick"
  ) {
    return (
      process.env
        .VECTOR_MODEL_QUICK ||
      "gpt-6-luna"
    );
  }

  return (
    process.env
      .VECTOR_MODEL_NORMAL ||
    "gpt-6-luna"
  );
}

export function getMaximumOutputTokens(
  mode
) {
  if (
    mode ===
    "deep"
  ) {
    return Number(
      process.env
        .VECTOR_DEEP_MAX_OUTPUT_TOKENS ||
      5000
    );
  }

  if (
    mode ===
    "research"
  ) {
    return Number(
      process.env
        .VECTOR_RESEARCH_MAX_OUTPUT_TOKENS ||
      2800
    );
  }

  if (
    mode ===
    "quick"
  ) {
    return Number(
      process.env
        .VECTOR_QUICK_MAX_OUTPUT_TOKENS ||
      500
    );
  }

  return Number(
    process.env
      .VECTOR_NORMAL_MAX_OUTPUT_TOKENS ||
    1400
  );
}
