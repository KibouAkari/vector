/*
 * Vector benchmark-aware model catalog.
 * Snapshot: 2026-09-24.
 *
 * Evidence inputs:
 * - Artificial Analysis Intelligence/Coding Agent Index, speed & cost data
 * - Official provider model/pricing documentation
 * - Vector product preferences are kept separate as routing bias.
 *
 * Scores are normalized routing heuristics, not claims of universal superiority.
 */

export const MODEL_CATALOG_VERSION = "2026-09-24";

export const MODEL_CATALOG = [
  {
    provider: "openai",
    model: "gpt-6-luna",
    label: "GPT-6 Luna",
    input: 0.10,
    cached: 0.01,
    output: 0.50,
    speed: 96,
    cost: 100,
    reliability: 93,
    scores: {
      general: 84,
      coding: 82,
      reasoning: 80,
      research: 82,
      humanities: 84,
      writing: 87,
      security: 82,
      server_ops: 84
    },
    tiers: ["quick", "normal"],
    source: "Artificial Analysis + OpenAI pricing/model docs"
  },
  {
    provider: "openai",
    model: "gpt-6-sol",
    label: "GPT-6 Sol",
    input: 2.00,
    cached: 0.20,
    output: 10.00,
    speed: 88,
    cost: 88,
    reliability: 97,
    scores: {
      general: 94,
      coding: 96,
      reasoning: 96,
      research: 93,
      humanities: 91,
      writing: 92,
      security: 96,
      server_ops: 96
    },
    tiers: ["normal", "deep", "research"],
    source: "Artificial Analysis + OpenAI pricing/model docs"
  },
  {
    provider: "openai",
    model: "gpt-6-astra",
    label: "GPT-6 Astra",
    input: 10.00,
    cached: 1.00,
    output: 50.00,
    speed: 58,
    cost: 52,
    reliability: 98,
    scores: {
      general: 99,
      coding: 100,
      reasoning: 100,
      research: 98,
      humanities: 95,
      writing: 95,
      security: 98,
      server_ops: 99
    },
    tiers: ["deep"],
    source: "Artificial Analysis + OpenAI pricing/model docs"
  },
  {
    provider: "anthropic",
    model: "claude-sonnet-5",
    label: "Claude Sonnet 5",
    input: 2.00,
    cached: 0.20,
    output: 10.00,
    speed: 77,
    cost: 86,
    reliability: 96,
    scores: {
      general: 94,
      coding: 98,
      reasoning: 95,
      research: 92,
      humanities: 96,
      writing: 99,
      security: 89,
      server_ops: 96
    },
    tiers: ["normal", "deep"],
    source: "Anthropic official model/pricing docs + Artificial Analysis"
  },
  {
    provider: "anthropic",
    model: "claude-opus-5-5",
    label: "Claude Opus 5.5",
    input: 4.00,
    cached: 0.20,
    output: 20.00,
    speed: 74,
    cost: 76,
    reliability: 99,
    scores: {
      general: 100,
      coding: 100,
      reasoning: 100,
      research: 97,
      humanities: 99,
      writing: 100,
      security: 94,
      server_ops: 100
    },
    tiers: ["deep"],
    source: "Anthropic Opus 5.5 docs + Artificial Analysis"
  },
  {
    provider: "google",
    model: "gemini-3.8-flash",
    label: "Gemini 3.8 Flash",
    input: 0.75,
    cached: 0.075,
    output: 3.75,
    speed: 100,
    cost: 91,
    reliability: 94,
    scores: {
      general: 92,
      coding: 94,
      reasoning: 93,
      research: 97,
      humanities: 89,
      writing: 91,
      security: 91,
      server_ops: 93
    },
    tiers: ["quick", "normal", "deep", "research"],
    source: "Google Gemini docs/pricing + Artificial Analysis"
  },
  {
    provider: "xai",
    model: "grok-4.7",
    label: "Grok 4.7",
    input: 2.00,
    cached: 0.50,
    output: 6.00,
    speed: 90,
    cost: 84,
    reliability: 96,
    scores: {
      general: 95,
      coding: 96,
      reasoning: 96,
      research: 91,
      humanities: 97,
      writing: 94,
      security: 95,
      server_ops: 95
    },
    tiers: ["normal", "deep"],
    source: "xAI docs + Artificial Analysis"
  },
  {
    provider: "perplexity",
    model: "sonar-pro",
    label: "Sonar Pro",
    input: 3.00,
    cached: 0,
    output: 15.00,
    requestFee: 0.006,
    speed: 82,
    cost: 80,
    reliability: 95,
    scores: {
      general: 86,
      coding: 75,
      reasoning: 84,
      research: 100,
      humanities: 83,
      writing: 82,
      security: 88,
      server_ops: 81
    },
    tiers: ["research"],
    source: "Perplexity Sonar API pricing/docs"
  }
];

const SIGNALS = {
  research: [
    "research", "recherch", "search", "suche", "quelle", "sources",
    "source", "latest", "aktuell", "current", "news", "preis", "price",
    "compare online", "vergleich", "web", "internet", "official"
  ],
  security: [
    "security", "sicherheit", "vulnerability", "vulnerable", "cve", "malware",
    "phishing", "siem", "sentinelone", "qualys", "qradar", "pentest",
    "penetration", "exploit", "threat", "ioc", "firewall", "edr", "soc",
    "incident", "suspicious", "exposed", "sensitive information", "xss",
    "sql injection", "ransomware"
  ],
  coding: [
    "code", "coding", "programm", "script", "bug", "debug", "exception",
    "stack trace", "stacktrace", "repository", "repo", "github", "gitlab",
    "javascript", "typescript", "react", "next.js", "nextjs", "python",
    "java", "fabric", "minecraft mod", "dockerfile", "api", "sql", "css",
    "html", "compile", "build", "implement", "refactor", "function", "class"
  ],
  server_ops: [
    "server", "docker", "container", "systemd", "nginx", "linux", "debian",
    "ssh", "service", "port", "vm", "virtual machine", "cockpit", "network",
    "firewall", "log", "disk", "memory", "cpu", "restart", "deploy"
  ],
  humanities: [
    "religion", "religi", "christian", "christentum", "bible", "bibel",
    "god", "gott", "jesus", "faith", "glaube", "theology", "theologie",
    "philosophy", "philosophie", "ethics", "ethik", "moral", "meaning of life",
    "sinn des lebens", "human nature", "menschlich", "menschliche", "relationship",
    "beziehung", "friendship", "freundschaft", "emotion", "gefühl"
  ],
  writing: [
    "rewrite", "umschreib", "verbesser", "email", "e-mail", "mail", "message",
    "nachricht", "grammar", "grammatik", "translate", "übersetz", "linkedin",
    "caption", "post", "letter", "brief", "formulieren", "tone", "schreibstil"
  ],
  reasoning: [
    "architecture", "architektur", "proof", "beweis", "mathemat", "equation",
    "gleichung", "probability", "wahrscheinlichkeit", "statistics", "statistik",
    "reasoning", "logik", "analyse deeply", "deep analysis", "trade-off",
    "tradeoff", "design decision", "system design"
  ]
};

function normalize(text) {
  return String(text || "").toLowerCase().replace(/\s+/g, " ").trim();
}

function scoreSignals(text, values) {
  return values.reduce((score, value) => score + (text.includes(value) ? 1 : 0), 0);
}

export function classifyVectorTask({
  message,
  mode = "normal",
  requireSearch = false,
  requireTools = false
}) {
  const text = normalize(message);
  const scores = Object.fromEntries(
    Object.entries(SIGNALS).map(([name, values]) => [name, scoreSignals(text, values)])
  );

  if (requireSearch || mode === "research") {
    scores.research += 5;
  }

  if (requireTools) {
    scores.server_ops += 1;
    scores.coding += 1;
  }

  const order = [
    "security",
    "research",
    "coding",
    "server_ops",
    "humanities",
    "reasoning",
    "writing"
  ];

  let primary = "general";
  let best = 0;

  for (const category of order) {
    if (scores[category] > best) {
      best = scores[category];
      primary = category;
    }
  }

  let complexity = "normal";
  if (mode === "quick") complexity = "quick";
  if (mode === "deep") complexity = "deep";
  if (mode === "research") complexity = "research";

  if (
    complexity === "normal" &&
    (text.length > 1800 || scores.reasoning >= 2 || scores.security >= 3 || scores.coding >= 3)
  ) {
    complexity = "deep";
  }

  return {
    primary,
    complexity,
    scores,
    textLength: text.length
  };
}

const PROVIDER_BIAS = {
  coding: {
    anthropic: 7,
    openai: 6,
    google: 4,
    xai: 4
  },
  research: {
    perplexity: 14,
    google: 6,
    openai: 5,
    anthropic: 2
  },
  humanities: {
    xai: 14,
    anthropic: 7,
    openai: 3,
    google: 1
  },
  writing: {
    anthropic: 9,
    openai: 4,
    xai: 3,
    google: 2
  },
  security: {
    openai: 8,
    xai: 6,
    google: 4,
    anthropic: 2
  },
  server_ops: {
    anthropic: 6,
    openai: 7,
    xai: 4,
    google: 3
  },
  reasoning: {
    openai: 7,
    anthropic: 7,
    xai: 4,
    google: 3
  },
  general: {
    openai: 4,
    anthropic: 4,
    google: 3,
    xai: 3
  }
};

function modeWeights(mode) {
  if (mode === "quick") {
    return { skill: 0.34, speed: 0.26, cost: 0.28, reliability: 0.12 };
  }

  if (mode === "deep") {
    return { skill: 0.67, speed: 0.05, cost: 0.10, reliability: 0.18 };
  }

  if (mode === "research") {
    return { skill: 0.57, speed: 0.10, cost: 0.14, reliability: 0.19 };
  }

  return { skill: 0.50, speed: 0.17, cost: 0.19, reliability: 0.14 };
}

export function catalogModelsForProvider(provider) {
  return MODEL_CATALOG.filter((item) => item.provider === provider);
}

export function getCatalogModel(provider, model) {
  return MODEL_CATALOG.find(
    (item) => item.provider === provider && item.model === model
  ) || null;
}

export function scoreCatalogModel(model, task, mode = "normal") {
  const weights = modeWeights(mode);
  const category = task?.primary || "general";
  const skill = Number(model.scores?.[category] || model.scores?.general || 70);

  let score =
    skill * weights.skill +
    Number(model.speed || 70) * weights.speed +
    Number(model.cost || 70) * weights.cost +
    Number(model.reliability || 90) * weights.reliability;

  score += Number(PROVIDER_BIAS[category]?.[model.provider] || 0);

  if (mode === "quick" && !model.tiers.includes("quick")) score -= 14;
  if (mode === "deep" && !model.tiers.includes("deep")) score -= 10;
  if (mode === "research" && !model.tiers.includes("research")) score -= 8;

  // Avoid premium frontier models for ordinary low-complexity work unless their
  // quality benefit is actually needed.
  if (mode !== "deep" && model.cost < 65) score -= 8;

  return score;
}

export function chooseCatalogModel({
  provider,
  task,
  mode = "normal"
}) {
  const models = catalogModelsForProvider(provider);

  if (!models.length) return null;

  return [...models]
    .map((model) => ({ model, score: scoreCatalogModel(model, task, mode) }))
    .sort((a, b) => b.score - a.score)[0]?.model || null;
}

export function automaticPricingFor(provider, model) {
  const item = getCatalogModel(provider, model);
  if (!item) return null;

  return {
    inputPerMillionUsd: Number(item.input || 0),
    cachedInputPerMillionUsd: Number(item.cached || 0),
    outputPerMillionUsd: Number(item.output || 0),
    requestFeeUsd: Number(item.requestFee || 0)
  };
}

export function routingExplanation(task) {
  const labels = {
    general: "general",
    coding: "coding",
    research: "research",
    humanities: "humanities / philosophy",
    writing: "writing",
    security: "security",
    server_ops: "server / operations",
    reasoning: "complex reasoning"
  };

  return labels[task?.primary] || "general";
}
