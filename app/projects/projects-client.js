"use client";

import {
  useState
} from "react";

import {
  useRouter
} from "next/navigation";

const PRIVACY_OPTIONS = [
  {
    value:
      "public",

    label:
      "Public",

    description:
      "Public information. Shared AI providers may be used later."
  },

  {
    value:
      "personal",

    label:
      "Personal",

    description:
      "Private personal work with Privacy Vault protection."
  },

  {
    value:
      "internal",

    label:
      "Internal",

    description:
      "Internal work. Only private external API routes later."
  },

  {
    value:
      "confidential",

    label:
      "Confidential",

    description:
      "Sensitive work with strict provider restrictions."
  },

  {
    value:
      "local_only",

    label:
      "Local only",

    description:
      "No external AI processing."
  }
];

export default function ProjectsClient() {
  const router =
    useRouter();

  const [
    open,
    setOpen
  ] =
    useState(
      false
    );

  const [
    name,
    setName
  ] =
    useState(
      ""
    );

  const [
    description,
    setDescription
  ] =
    useState(
      ""
    );

  const [
    privacyLevel,
    setPrivacyLevel
  ] =
    useState(
      "personal"
    );

  const [
    loading,
    setLoading
  ] =
    useState(
      false
    );

  const [
    error,
    setError
  ] =
    useState(
      ""
    );

  async function createProject(
    event
  ) {
    event.preventDefault();

    if (
      !name.trim() ||
      loading
    ) {
      return;
    }

    setLoading(
      true
    );

    setError(
      ""
    );

    try {
      const response =
        await fetch(
          "/api/projects",
          {
            method:
              "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body:
              JSON.stringify({
                name:
                  name.trim(),

                description:
                  description.trim(),

                privacyLevel
              })
          }
        );

      const data =
        await response.json();

      if (
        !response.ok
      ) {
        setError(
          data.error ||
          "Could not create project."
        );

        return;
      }

      router.push(
        `/projects/${data.project.id}`
      );

    } catch {
      setError(
        "Vector could not create the project."
      );

    } finally {
      setLoading(
        false
      );
    }
  }

  return (
    <>
      <button
        type="button"
        className="project-create-button"
        onClick={
          () =>
            setOpen(
              true
            )
        }
      >
        <span>
          +
        </span>

        New project
      </button>

      {
        open && (
          <div className="project-modal-layer">

            <button
              type="button"
              className="project-modal-backdrop"
              aria-label="Close"
              onClick={
                () =>
                  setOpen(
                    false
                  )
              }
            />

            <form
              className="project-modal"
              onSubmit={
                createProject
              }
            >

              <div className="project-modal-head">

                <div>

                  <span>
                    New workspace
                  </span>

                  <h2>
                    Create project
                  </h2>

                </div>

                <button
                  type="button"
                  onClick={
                    () =>
                      setOpen(
                        false
                      )
                  }
                >
                  ×
                </button>

              </div>

              <label className="project-field">

                <span>
                  Name
                </span>

                <input
                  autoFocus
                  value={
                    name
                  }
                  placeholder="FEGCraft"
                  maxLength="100"
                  onChange={
                    (
                      event
                    ) =>
                      setName(
                        event
                          .target
                          .value
                      )
                  }
                />

              </label>

              <label className="project-field">

                <span>
                  Description
                </span>

                <textarea
                  rows="3"
                  value={
                    description
                  }
                  placeholder="What is this project about?"
                  maxLength="1000"
                  onChange={
                    (
                      event
                    ) =>
                      setDescription(
                        event
                          .target
                          .value
                      )
                  }
                />

              </label>

              <div className="privacy-selector">

                <span className="privacy-selector-label">
                  Privacy
                </span>

                {
                  PRIVACY_OPTIONS.map(
                    (
                      option
                    ) => (
                      <label
                        key={
                          option.value
                        }
                        className={
                          privacyLevel ===
                          option.value
                            ? "privacy-option selected"
                            : "privacy-option"
                        }
                      >

                        <input
                          type="radio"
                          name="privacy"
                          value={
                            option.value
                          }
                          checked={
                            privacyLevel ===
                            option.value
                          }
                          onChange={
                            () =>
                              setPrivacyLevel(
                                option.value
                              )
                          }
                        />

                        <div>

                          <strong>
                            {
                              option.label
                            }
                          </strong>

                          <small>
                            {
                              option.description
                            }
                          </small>

                        </div>

                      </label>
                    )
                  )
                }

              </div>

              {
                error && (
                  <div className="project-form-error">
                    {error}
                  </div>
                )
              }

              <div className="project-modal-actions">

                <button
                  type="button"
                  className="secondary"
                  onClick={
                    () =>
                      setOpen(
                        false
                      )
                  }
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={
                    loading ||
                    !name.trim()
                  }
                >
                  {
                    loading
                      ? "Creating…"
                      : "Create project"
                  }
                </button>

              </div>

            </form>

          </div>
        )
      }

    </>
  );
}
