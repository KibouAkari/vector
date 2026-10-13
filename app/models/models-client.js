"use client";

import { Cloud, Cpu, BrainCircuit, Sparkles, PlugZap, RefreshCw, Pencil, ShieldCheck, CheckCircle2, ChevronRight } from "lucide-react";

import {
  useEffect,
  useMemo,
  useState
} from "react";


const OPTIONS = {
  openai: {
    name: "OpenAI",
    description:
      "Vector automatically chooses between available OpenAI models.",
    base:
      "https://api.openai.com/v1",
    auto: true
  },

  google: {
    name: "Google Gemini",
    description:
      "Fast multimodal and long-context work with Gemini.",
    base:
      "https://generativelanguage.googleapis.com/v1beta/openai",
    auto: true
  },

  anthropic: {
    name: "Anthropic",
    description:
      "Claude models for coding, writing and complex work.",
    base:
      "https://api.anthropic.com",
    auto: true
  },

  perplexity: {
    name: "Perplexity",
    description:
      "Live web research and source-grounded answers.",
    base:
      "https://api.perplexity.ai",
    auto: true
  },

  xai: {
    name: "xAI",
    description:
      "Grok models for reasoning, agentic and conversational work.",
    base:
      "https://api.x.ai/v1",
    auto: true
  },

  openrouter: {
    name: "OpenRouter",
    description:
      "Use a specific model through OpenRouter.",
    base:
      "https://openrouter.ai/api/v1",
    auto: false
  },

  local: {
    name: "Local / self-hosted",
    description:
      "Connect an OpenAI-compatible model running on your own infrastructure.",
    base:
      "",
    auto: false
  },

  custom: {
    name: "Custom",
    description:
      "Connect another OpenAI-compatible endpoint.",
    base:
      "",
    auto: false
  }
};


function ProviderGlyph({ provider }) {
  const id = String(provider || "").toLowerCase();
  const Icon = id === "anthropic" ? BrainCircuit :
    id === "google" ? Sparkles :
    id === "openai" ? Cpu :
    id === "local" ? Cpu : Cloud;
  return <span className="vx586-provider-glyph" aria-hidden="true"><Icon size={18} strokeWidth={1.7} /></span>;
}

function newProvider(
  provider = "openai"
) {
  const option =
    OPTIONS[provider];

  return {
    id: null,
    provider,
    label:
      option.name,
    apiBase:
      option.base,
    apiKey:
      "",
    defaultModel:
      "",
    enabled:
      true,
    sharedWithUsers:
      false,
    hasApiKey:
      false
  };
}


export default function ModelsClient() {
  const [
    providers,
    setProviders
  ] =
    useState([]);

  const [
    recommendations,
    setRecommendations
  ] =
    useState([]);

  const [
    role,
    setRole
  ] =
    useState(
      "member"
    );

  const [
    editing,
    setEditing
  ] =
    useState(null);

  const [
    loading,
    setLoading
  ] =
    useState(
      true
    );

  const [
    saving,
    setSaving
  ] =
    useState(
      false
    );

  const [
    testing,
    setTesting
  ] =
    useState(null);

  const [
    message,
    setMessage
  ] =
    useState(null);


  async function load() {
    setLoading(
      true
    );

    try {
      const response =
        await fetch(
          "/api/models",
          {
            cache:
              "no-store"
          }
        );

      const data =
        await response.json();

      if (
        !response.ok
      ) {
        throw new Error(
          data.error ||
          "Could not load model APIs."
        );
      }

      setProviders(
        data.providers ||
        []
      );

      setRecommendations(
        data.recommendations ||
        []
      );

      setRole(
        data.role ||
        "member"
      );

    } catch (
      error
    ) {
      setMessage({
        type:
          "error",
        text:
          error.message
      });

    } finally {
      setLoading(
        false
      );
    }
  }


  useEffect(
    () => {
      load();
    },
    []
  );


  const currentOption =
    useMemo(
      () =>
        OPTIONS[
          editing?.provider
        ] ||
        OPTIONS.custom,
      [
        editing
      ]
    );


  const ownProviders =
    providers.filter(
      (
        provider
      ) =>
        provider
          .credential_scope ===
        "personal"
    );

  const workspaceProviders =
    providers.filter(
      (
        provider
      ) =>
        provider
          .credential_scope ===
        "workspace"
    );


  function openNew() {
    setMessage(
      null
    );

    setEditing(
      newProvider(
        "openai"
      )
    );
  }


  function changeProvider(
    provider
  ) {
    const option =
      OPTIONS[provider];

    setEditing(
      (
        current
      ) => ({
        ...current,
        provider,
        label:
          current?.id
            ? current.label
            : option.name,
        apiBase:
          current?.id
            ? current.apiBase
            : option.base,
        defaultModel:
          current?.id
            ? current.defaultModel
            : ""
      })
    );
  }


  function editProvider(
    provider
  ) {
    if (
      !provider.editable
    ) {
      return;
    }

    setMessage(
      null
    );

    setEditing({
      id:
        provider.id,
      provider:
        provider.provider,
      label:
        provider.label,
      apiBase:
        provider.api_base ||
        OPTIONS[
          provider.provider
        ]?.base ||
        "",
      apiKey:
        "",
      defaultModel:
        provider.auto_model
          ? ""
          : (
              provider
                .default_model ||
              ""
            ),
      enabled:
        provider.enabled,
      sharedWithUsers:
        Boolean(
          provider
            .shared_with_users
        ),
      hasApiKey:
        provider.has_api_key
    });
  }


  async function save() {
    if (!editing) {
      return;
    }

    if (
      !currentOption.auto &&
      !editing.defaultModel
        .trim()
    ) {
      setMessage({
        type:
          "error",
        text:
          "This provider needs a Model ID because Vector cannot infer its model catalog."
      });

      return;
    }

    if (
      editing.provider !==
        "local" &&
      !editing.id &&
      !editing.apiKey
        .trim()
    ) {
      setMessage({
        type:
          "error",
        text:
          "API key is required."
      });

      return;
    }

    setSaving(
      true
    );

    setMessage(
      null
    );

    try {
      const response =
        await fetch(
          editing.id
            ? `/api/models/${editing.id}`
            : "/api/models",
          {
            method:
              editing.id
                ? "PATCH"
                : "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body:
              JSON.stringify({
                provider:
                  editing.provider,
                label:
                  editing.label,
                apiBase:
                  editing.apiBase,
                apiKey:
                  editing.apiKey,
                defaultModel:
                  editing.defaultModel,
                enabled:
                  editing.enabled,
                sharedWithUsers:
                  role ===
                    "owner"
                    ? Boolean(
                        editing
                          .sharedWithUsers
                      )
                    : false
              })
          }
        );

      const data =
        await response.json();

      if (
        !response.ok
      ) {
        throw new Error(
          data.error ||
          "Could not save provider."
        );
      }

      setEditing(
        null
      );

      setMessage({
        type:
          "success",
        text:
          role ===
            "owner"
            ? "Model API saved."
            : "Your private API connection was saved."
      });

      await load();

    } catch (
      error
    ) {
      setMessage({
        type:
          "error",
        text:
          error.message
      });

    } finally {
      setSaving(
        false
      );
    }
  }


  async function testProvider(
    provider
  ) {
    if (
      !provider.editable
    ) {
      return;
    }

    setTesting(
      provider.id
    );

    setMessage(
      null
    );

    try {
      const response =
        await fetch(
          `/api/models/${provider.id}/test`,
          {
            method:
              "POST"
          }
        );

      const data =
        await response.json();

      if (
        !response.ok
      ) {
        throw new Error(
          data.error ||
          "Connection test failed."
        );
      }

      setMessage({
        type:
          "success",
        text:
          `${provider.label} works · ${
            data.model ||
            provider.recommended_model ||
            "model available"
          }`
      });

    } catch (
      error
    ) {
      setMessage({
        type:
          "error",
        text:
          error.message
      });

    } finally {
      setTesting(
        null
      );
    }
  }


  async function removeProvider(
    provider
  ) {
    if (
      !provider.editable ||
      !window.confirm(
        `Remove ${provider.label}?`
      )
    ) {
      return;
    }

    const response =
      await fetch(
        `/api/models/${provider.id}`,
        {
          method:
            "DELETE"
        }
      );

    if (
      response.ok
    ) {
      if (
        editing?.id ===
        provider.id
      ) {
        setEditing(
          null
        );
      }

      await load();
    }
  }


  function ProviderRow({
    provider
  }) {
    const workspace =
      provider
        .credential_scope ===
      "workspace";

    return (
      <article
        className="v562-provider"
      >

        <div className="v562-provider-main">
          <ProviderGlyph provider={provider.provider} />
          <strong>
            {provider.label}
          </strong>

          <span>
            {
              provider.auto_model
                ? `Auto model${
                    provider.recommended_model
                      ? ` · ${provider.recommended_model}`
                      : ""
                  }`
                : (
                    provider.default_model ||
                    "Model not set"
                  )
            }
          </span>

        </div>

        <div className="v563-provider-scope">

          <span>
            {
              workspace
                ? "Workspace API"
                : role ===
                    "owner"
                  ? (
                      provider.shared_with_users
                        ? "Shared with users"
                        : "Owner only"
                    )
                  : "Your API"
            }
          </span>

          <small>
            {
              workspace
                ? "Credential managed by owner"
                : (
                    provider.enabled
                      ? "Enabled"
                      : "Disabled"
                  )
            }
          </small>

        </div>

        {
          provider.editable
            ? (
                <div className="v562-provider-actions">

                  <button
                    type="button"
                    disabled={
                      testing ===
                      provider.id
                    }
                    onClick={
                      () =>
                        testProvider(
                          provider
                        )
                    }
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                    {
                      testing ===
                      provider.id
                        ? "Testing…"
                        : "Test"
                    }
                  </button>

                  <button
                    type="button"
                    onClick={
                      () =>
                        editProvider(
                          provider
                        )
                    }
                  >
                    <Pencil size={14} aria-hidden="true" /> Edit
                  </button>

                </div>
              )
            : (
                <div className="v563-workspace-available">
                  Available
                </div>
              )
        }

      </article>
    );
  }


  return (
    <div className="v562-models">

      <header className="v562-head">

        <div>

          <span>
            Models & APIs
          </span>

          <h1>Models</h1>

          <p>
            {
              role ===
              "owner"
                ? "Manage connections, sharing and automatic model selection."
                : "Use APIs shared by the workspace, or connect your own keys. Your own credentials are private to your account."
            }
          </p>

        </div>

        <button
          type="button"
          className="v562-connect"
          onClick={
            openNew
          }
        >
          <PlugZap size={16} strokeWidth={1.8} aria-hidden="true" />
          Connect API
        </button>

      </header>

      {
        message && (
          <div
            className={
              `v562-message ${
                message.type
              }`
            }
          >
            {message.text}
          </div>
        )
      }

      {!loading && (
        <div className="vx587-model-summary" role="status">
          <span
            className="vx587-live-dot"
            aria-hidden="true"
          />
          <strong>
            {providers.filter(p => p.enabled).length}
            {" / "}
            {providers.length}
          </strong>
          <span>connections enabled</span>
          <span
            className="vx587-summary-separator"
            aria-hidden="true"
          />
          <span>
            {recommendations.filter(
              item => !item.error
            ).length} available routes
          </span>
        </div>
      )}

      <div className="vx587-model-workspace">
      <section className="v562-auto">

        <div className="v562-section-head">

          <div>

            <strong>
              Vector Auto
            </strong>

            <span>
              Suggested models for each type of task
            </span>

          </div>



        </div>

        <div className="v562-auto-grid">

          {
            recommendations.map(
              (
                item
              ) => (
                <div
                  key={
                    item.id
                  }
                  className="v562-auto-row"
                >

                  <span>
                    {item.label}
                  </span>

                  {
                    item.error
                      ? (
                          <strong className="muted">
                            No compatible API
                          </strong>
                        )
                      : (
                          <strong>
                            {item.provider}
                            {" · "}
                            {item.model}
                            {
                              item.credentialScope ===
                              "workspace"
                                ? " · workspace"
                                : ""
                            }
                          </strong>
                        )
                  }

                </div>
              )
            )
          }

        </div>

      </section>

      {
        role !==
          "owner" &&
        workspaceProviders.length >
          0 && (
          <section className="v562-providers">

            <div className="v562-section-head">

              <div>

                <strong>
                  Workspace APIs
                </strong>

                <span>
                  Shared with you by the owner
                </span>

              </div>

            </div>

            <div className="v562-provider-list">

              {
                workspaceProviders.map(
                  (
                    provider
                  ) => (
                    <ProviderRow
                      key={
                        provider.id
                      }
                      provider={
                        provider
                      }
                    />
                  )
                )
              }

            </div>

          </section>
        )
      }

      <section className="v562-providers">

        <div className="v562-section-head">

          <div>

            <strong>
              {
                role ===
                "owner"
                  ? "Your APIs"
                  : "Your private APIs"
              }
            </strong>

            <span>
              {
                ownProviders.length
              }
              {" "}
              {
                ownProviders.length ===
                1
                  ? "connection"
                  : "connections"
              }
            </span>

          </div>

        </div>

        {
          loading
            ? (
                <div className="v562-empty">
                  Loading…
                </div>
              )
            : ownProviders.length ===
              0
              ? (
                  <div className="v562-empty">

                    {
                      role ===
                      "owner"
                        ? "No APIs connected yet."
                        : workspaceProviders.length > 0
                          ? "You are currently using workspace APIs. Add your own key if you want requests billed directly to your provider account."
                          : "No API is available yet. Connect your own key to use Vector."
                    }

                  </div>
                )
              : (
                  <div className="v562-provider-list">

                    {
                      ownProviders.map(
                        (
                          provider
                        ) => (
                          <ProviderRow
                            key={
                              provider.id
                            }
                            provider={
                              provider
                            }
                          />
                        )
                      )
                    }

                  </div>
                )
        }

      </section>

      </div>

      {
        editing && (
          <div className="v5-modal-layer">

            <button
              type="button"
              className="v5-modal-shade"
              aria-label="Close"
              onClick={
                () =>
                  setEditing(
                    null
                  )
              }
            />

            <div className="v5-modal v562-modal">

              <header>

                <div>

                  <span>
                    {
                      editing.id
                        ? "Edit connection"
                        : "New provider"
                    }
                  </span>

                  <h2>
                    {
                      editing.id
                        ? editing.label
                        : "Connect a model API"
                    }
                  </h2>

                </div>

                <button
                  type="button"
                  onClick={
                    () =>
                      setEditing(
                        null
                      )
                  }
                >
                  ×
                </button>

              </header>

              <label>
                Provider

                <select
                  value={
                    editing.provider
                  }
                  disabled={
                    Boolean(
                      editing.id
                    )
                  }
                  onChange={
                    (
                      event
                    ) =>
                      changeProvider(
                        event.target.value
                      )
                  }
                >

                  {
                    Object.entries(
                      OPTIONS
                    ).map(
                      (
                        [
                          id,
                          option
                        ]
                      ) => (
                        <option
                          value={
                            id
                          }
                          key={
                            id
                          }
                        >
                          {option.name}
                        </option>
                      )
                    )
                  }

                </select>
              </label>

              <p className="v562-description">
                {
                  currentOption.description
                }
              </p>

              <label>
                API key

                <input
                  type="password"
                  autoComplete="off"
                  value={
                    editing.apiKey
                  }
                  placeholder={
                    editing.id
                      ? "Leave empty to keep the current key"
                      : editing.provider ===
                          "local"
                        ? "Optional for local endpoints"
                        : "Paste API key"
                  }
                  onChange={
                    (
                      event
                    ) =>
                      setEditing({
                        ...editing,
                        apiKey:
                          event.target.value
                      })
                  }
                />

                <small>
                  Encrypted at rest. The key is never returned to the browser.
                </small>
              </label>

              <label>
                Model ID
                {" "}
                <small>
                  {
                    currentOption.auto
                      ? "optional"
                      : "required"
                  }
                </small>

                <input
                  value={
                    editing.defaultModel
                  }
                  placeholder={
                    currentOption.auto
                      ? "Leave empty for Vector Auto"
                      : "e.g. provider/model-name"
                  }
                  onChange={
                    (
                      event
                    ) =>
                      setEditing({
                        ...editing,
                        defaultModel:
                          event.target.value
                      })
                  }
                />

              </label>

              <details className="v562-advanced">

                <summary>
                  Advanced
                </summary>

                <label>
                  Display name

                  <input
                    value={
                      editing.label
                    }
                    onChange={
                      (
                        event
                      ) =>
                        setEditing({
                          ...editing,
                          label:
                            event.target.value
                        })
                    }
                  />
                </label>

                <label>
                  API endpoint

                  <input
                    value={
                      editing.apiBase
                    }
                    placeholder={
                      currentOption.base ||
                      "https://…"
                    }
                    onChange={
                      (
                        event
                      ) =>
                        setEditing({
                          ...editing,
                          apiBase:
                            event.target.value
                        })
                    }
                  />
                </label>

              </details>

              <div className="v563-provider-options">

                <label className="v562-enabled">

                  <input
                    type="checkbox"
                    checked={
                      editing.enabled
                    }
                    onChange={
                      (
                        event
                      ) =>
                        setEditing({
                          ...editing,
                          enabled:
                            event.target.checked
                        })
                    }
                  />

                  Enabled

                </label>

                {
                  role ===
                  "owner" && (
                    <label className="v562-enabled">

                      <input
                        type="checkbox"
                        checked={
                          Boolean(
                            editing
                              .sharedWithUsers
                          )
                        }
                        onChange={
                          (
                            event
                          ) =>
                            setEditing({
                              ...editing,
                              sharedWithUsers:
                                event.target.checked
                            })
                        }
                      />

                      Share this API with users

                    </label>
                  )
                }

              </div>

              {
                role ===
                "owner" && (
                <p className="v563-share-note">
                  Shared users can send requests through this provider, but they can never view or edit the API key.
                </p>
              )
              }

              <footer>

                {
                  editing.id
                    ? (
                        <button
                          type="button"
                          className="danger"
                          onClick={
                            async () => {
                              const provider =
                                providers.find(
                                  (
                                    item
                                  ) =>
                                    item.id ===
                                    editing.id
                                );

                              setEditing(
                                null
                              );

                              if (
                                provider
                              ) {
                                await removeProvider(
                                  provider
                                );
                              }
                            }
                          }
                        >
                          Remove
                        </button>
                      )
                    : <span />
                }

                <span />

                <button
                  type="button"
                  onClick={
                    () =>
                      setEditing(
                        null
                      )
                  }
                >
                  Cancel
                </button>

                <button
                  type="button"
                  className="primary"
                  disabled={
                    saving
                  }
                  onClick={
                    save
                  }
                >
                  {
                    saving
                      ? "Saving…"
                      : "Save"
                  }
                </button>

              </footer>

            </div>

          </div>
        )
      }

    </div>
  );
}
