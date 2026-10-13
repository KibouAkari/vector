"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";

import {
  useRouter
} from "next/navigation";

import ReactMarkdown
  from "react-markdown";

import remarkGfm
  from "remark-gfm";

const PRIVACY_NAMES = {
  public:
    "Public",

  personal:
    "Personal",

  internal:
    "Internal",

  confidential:
    "Confidential",

  local_only:
    "Local only"
};

function bytes(
  value
) {
  const size =
    Number(
      value || 0
    );

  if (size < 1024) {
    return `${size} B`;
  }

  if (
    size <
    1024 * 1024
  ) {
    return `${(
      size /
      1024
    ).toFixed(1)} KB`;
  }

  if (
    size <
    1024 *
    1024 *
    1024
  ) {
    return `${(
      size /
      1024 /
      1024
    ).toFixed(1)} MB`;
  }

  return `${(
    size /
    1024 /
    1024 /
    1024
  ).toFixed(2)} GB`;
}

function money(
  value
) {
  const number =
    Number(
      value ||
      0
    );

  if (
    number <
    0.01
  ) {
    return "< CHF 0.01";
  }

  return (
    `CHF ${number.toFixed(2)}`
  );
}

function playDoneSound() {
  try {
    const AudioContextClass =
      window.AudioContext ||
      window.webkitAudioContext;

    if (!AudioContextClass) {
      return;
    }

    const context =
      new AudioContextClass();

    const oscillator =
      context.createOscillator();

    const gain =
      context.createGain();

    oscillator
      .connect(
        gain
      );

    gain
      .connect(
        context.destination
      );

    oscillator.type =
      "sine";

    oscillator.frequency
      .setValueAtTime(
        620,
        context.currentTime
      );

    oscillator.frequency
      .exponentialRampToValueAtTime(
        830,
        context.currentTime +
        0.11
      );

    gain.gain
      .setValueAtTime(
        0.045,
        context.currentTime
      );

    gain.gain
      .exponentialRampToValueAtTime(
        0.001,
        context.currentTime +
        0.18
      );

    oscillator.start();

    oscillator.stop(
      context.currentTime +
      0.19
    );

  } catch {
    // Sound is optional.
  }
}

function Markdown({
  children
}) {
  return (
    <ReactMarkdown
      remarkPlugins={[
        remarkGfm
      ]}
    >
      {children}
    </ReactMarkdown>
  );
}

export default function ProjectWorkbench({
  project,
  files,
  tasks,
  conversations,
  activity,
  stats
}) {
  const router =
    useRouter();

  const uploadRef =
    useRef(null);

  const chatBottomRef =
    useRef(null);

  const [
    tab,
    setTab
  ] =
    useState(
      "overview"
    );

  const [
    localFiles,
    setLocalFiles
  ] =
    useState(
      files
    );

  const [
    localTasks,
    setLocalTasks
  ] =
    useState(
      tasks
    );

  const [
    chatMessages,
    setChatMessages
  ] =
    useState([]);

  const [
    projectConversations,
    setProjectConversations
  ] =
    useState(
      conversations ||
      []
    );

  const [
    conversationId,
    setConversationId
  ] =
    useState(null);

  const [
    chatInput,
    setChatInput
  ] =
    useState("");

  const [
    chatMode,
    setChatMode
  ] =
    useState(
      "auto"
    );

  const [
    chatLoading,
    setChatLoading
  ] =
    useState(
      false
    );

  const [
    privacyNotice,
    setPrivacyNotice
  ] =
    useState(
      null
    );

  const [
    notificationEnabled,
    setNotificationEnabled
  ] =
    useState(
      false
    );

  const [
    preview,
    setPreview
  ] =
    useState(
      null
    );

  const [
    editorContent,
    setEditorContent
  ] =
    useState(
      ""
    );

  const [
    editing,
    setEditing
  ] =
    useState(
      false
    );

  const [
    uploading,
    setUploading
  ] =
    useState(
      false
    );

  const [
    taskTitle,
    setTaskTitle
  ] =
    useState(
      ""
    );

  const [
    createFileOpen,
    setCreateFileOpen
  ] =
    useState(
      false
    );

  const [
    newFilename,
    setNewFilename
  ] =
    useState(
      ""
    );

  const [
    newFileContent,
    setNewFileContent
  ] =
    useState(
      ""
    );

  const [
    copied,
    setCopied
  ] =
    useState(
      null
    );

  const [
    toast,
    setToast
  ] =
    useState(
      null
    );

  const completedTasks =
    useMemo(
      () =>
        localTasks.filter(
          (
            task
          ) =>
            task.status ===
            "completed"
        ).length,
      [
        localTasks
      ]
    );

  useEffect(
    () => {
      if (
        conversations
          ?.length >
        0
      ) {
        loadConversation(
          conversations[0].id
        );
      }
    },
    []
  );


  useEffect(
    () => {
      chatBottomRef
        .current
        ?.scrollIntoView({
          behavior:
            "smooth"
        });
    },
    [
      chatMessages,
      chatLoading
    ]
  );

  /*
   * VECTOR_PRIVATE_PROJECT_HISTORY_563
   * Load only the current user's project conversations from the scoped API.
   */
  useEffect(
    () => {
      let cancelled =
        false;

      (
        async () => {
          const list =
            await refreshConversations();

          if (
            !cancelled &&
            list?.length >
              0
          ) {
            await loadConversation(
              list[0].id
            );
          }
        }
      )();

      return () => {
        cancelled =
          true;
      };
    },
    []
  );


  async function refreshFiles() {
    try {
      const response =
        await fetch(
          `/api/projects/${project.id}/files`,
          {
            cache:
              "no-store"
          }
        );

      if (
        response.ok
      ) {
        const data =
          await response.json();

        setLocalFiles(
          data.files ||
          []
        );
      }
    } catch {
      // Keep current state if refresh fails.
    }
  }


  async function refreshConversations() {
    try {
      const response =
        await fetch(
          `/api/projects/${project.id}/conversations`,
          {
            cache:
              "no-store"
          }
        );

      if (
        response.ok
      ) {
        const data =
          await response.json();

        setProjectConversations(
          data.conversations ||
          []
        );

        return (
          data.conversations ||
          []
        );
      }
    } catch {
      // Ignore.
    }

    return [];
  }


  async function loadConversation(
    id
  ) {
    if (!id) {
      setConversationId(
        null
      );

      setChatMessages(
        []
      );

      return;
    }

    const response =
      await fetch(
        `/api/projects/${project.id}/conversations/${id}`,
        {
          cache:
            "no-store"
        }
      );

    if (
      !response.ok
    ) {
      return;
    }

    const data =
      await response.json();

    setConversationId(
      id
    );

    setChatMessages(
      (
        data.messages ||
        []
      ).map(
        (
          message
        ) => ({
          id:
            message.id,

          role:
            message.role,

          content:
            message.content,

          meta:
            message.model
              ? {
                  model:
                    message.model,

                  costChf:
                    Number(
                      message.cost_chf ||
                      0
                    )
                }
              : null
        })
      )
    );
  }


  function notifyDone(
    title,
    body
  ) {
    playDoneSound();

    setToast({
      title,
      body
    });

    setTimeout(
      () =>
        setToast(
          null
        ),
      3500
    );

    if (
      notificationEnabled &&
      document.hidden &&
      Notification.permission ===
      "granted"
    ) {
      new Notification(
        title,
        {
          body,
          icon:
            "/vector-icon.svg"
        }
      );
    }
  }

  async function enableNotifications() {
    if (
      !(
        "Notification" in window
      )
    ) {
      setToast({
        title:
          "Notifications unavailable",
        body:
          "This browser does not support native notifications."
      });

      return;
    }

    const permission =
      await Notification
        .requestPermission();

    setNotificationEnabled(
      permission ===
      "granted"
    );

    if (
      permission ===
      "granted"
    ) {
      playDoneSound();

      setToast({
        title:
          "Notifications enabled",
        body:
          "Vector can alert you when work finishes."
      });
    }
  }

  async function copyText(
    id,
    text
  ) {
    await navigator
      .clipboard
      .writeText(
        text
      );

    setCopied(
      id
    );

    setTimeout(
      () =>
        setCopied(
          null
        ),
      1300
    );
  }

  async function uploadFiles(
    selected
  ) {
    const items =
      Array.from(
        selected ||
        []
      );

    if (
      items.length ===
      0
    ) {
      return;
    }

    setUploading(
      true
    );

    try {
      for (
        const file
        of items
      ) {
        const form =
          new FormData();

        form.append(
          "file",
          file
        );

        const response =
          await fetch(
            `/api/projects/${project.id}/files`,
            {
              method:
                "POST",
              body:
                form
            }
          );

        const data =
          await response.json();

        if (
          !response.ok
        ) {
          throw new Error(
            data.error ||
            "Upload failed."
          );
        }
      }

      notifyDone(
        "Upload complete",
        `${items.length} file${
          items.length === 1
            ? ""
            : "s"
        } encrypted and indexed.`
      );

      await refreshFiles();

    } catch (
      error
    ) {
      setToast({
        title:
          "Upload failed",
        body:
          error.message
      });

    } finally {
      setUploading(
        false
      );
    }
  }

  async function openFile(
    file
  ) {
    const mime =
      String(
        file.mime_type ||
        ""
      );

    if (
      mime.startsWith(
        "image/"
      ) ||
      mime ===
      "application/pdf"
    ) {
      setPreview({
        type:
          mime ===
          "application/pdf"
            ? "pdf"
            : "image",

        name:
          file.original_name,

        url:
          `/api/files/${file.id}/raw`,

        file
      });

      setTab(
        "files"
      );

      return;
    }

    if (
      file.previewable
    ) {
      const response =
        await fetch(
          `/api/files/${file.id}/content`
        );

      const data =
        await response.json();

      if (
        response.ok
      ) {
        setPreview({
          type:
            "text",

          name:
            file.original_name,

          file
        });

        setEditorContent(
          data.content
        );

        setEditing(
          false
        );
      }

      return;
    }

    setToast({
      title:
        "Stored securely",
      body:
        "This file type is stored encrypted. Rich analysis arrives through the multimodal/file agents."
    });
  }

  async function saveTextFile() {
    if (
      !preview?.file?.id
    ) {
      return;
    }

    const response =
      await fetch(
        `/api/files/${preview.file.id}/content`,
        {
          method:
            "PATCH",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              content:
                editorContent
            })
        }
      );

    if (
      response.ok
    ) {
      setEditing(
        false
      );

      notifyDone(
        "File saved",
        `${preview.name} encrypted and re-indexed.`
      );

      await refreshFiles();
    }
  }

  async function createFile() {
    if (
      !newFilename.trim()
    ) {
      return;
    }

    const response =
      await fetch(
        `/api/projects/${project.id}/files/create`,
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
                newFilename.trim(),

              content:
                newFileContent
            })
        }
      );

    const data =
      await response.json();

    if (
      response.ok
    ) {
      setCreateFileOpen(
        false
      );

      setNewFilename(
        ""
      );

      setNewFileContent(
        ""
      );

      notifyDone(
        "File created",
        "The new file is encrypted and indexed."
      );

      await refreshFiles();

    } else {
      setToast({
        title:
          "Could not create file",
        body:
          data.error
      });
    }
  }

  async function createTask() {
    const clean =
      taskTitle.trim();

    if (!clean) {
      return;
    }

    const response =
      await fetch(
        `/api/projects/${project.id}/tasks`,
        {
          method:
            "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              title:
                clean
            })
        }
      );

    const data =
      await response.json();

    if (
      response.ok
    ) {
      setLocalTasks(
        (
          current
        ) => [
          {
            id:
              data.id,
            title:
              clean,
            description:
              "",
            status:
              "pending"
          },
          ...current
        ]
      );

      setTaskTitle(
        ""
      );
    }
  }

  async function setTaskStatus(
    task,
    status
  ) {
    const response =
      await fetch(
        `/api/tasks/${task.id}`,
        {
          method:
            "PATCH",

          headers: {
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              status
            })
        }
      );

    if (
      response.ok
    ) {
      setLocalTasks(
        (
          current
        ) =>
          current.map(
            (
              currentTask
            ) =>
              currentTask.id ===
              task.id
                ? {
                    ...currentTask,
                    status
                  }
                : currentTask
          )
      );

      if (
        status ===
        "completed"
      ) {
        notifyDone(
          "Task completed",
          task.title
        );
      }
    }
  }

  async function sendProjectMessage(
    event
  ) {
    event.preventDefault();

    const text =
      chatInput.trim();

    if (
      !text ||
      chatLoading
    ) {
      return;
    }

    const tempId =
      `user-${Date.now()}`;

    setChatMessages(
      (
        current
      ) => [
        ...current,

        {
          id:
            tempId,
          role:
            "user",
          content:
            text
        }
      ]
    );

    setChatInput(
      ""
    );

    setChatLoading(
      true
    );

    setPrivacyNotice(
      null
    );

    try {
      const response =
        await fetch(
          `/api/projects/${project.id}/chat`,
          {
            method:
              "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body:
              JSON.stringify({
                message:
                  text,

                conversationId,

                mode:
                  chatMode
              })
          }
        );

      const data =
        await response.json();

      if (
        !response.ok
      ) {
        setToast({
          title:
            "Vector could not continue",
          body:
            data.message ||
            data.error
        });

        return;
      }

      setConversationId(
        data.conversationId
      );

      await refreshConversations();

      setChatMessages(
        (
          current
        ) => [
          ...current,

          {
            id:
              data.message.id,

            role:
              "assistant",

            content:
              data.message.content,

            meta:
              data.meta,

            retrieval:
              data.retrieval
          }
        ]
      );

      if (
        data.privacy
          ?.protected
      ) {
        setPrivacyNotice(
          data.privacy.values
        );
      }

      notifyDone(
        "Vector finished",
        "Your project answer is ready."
      );

    } catch {
      setToast({
        title:
          "Vector unavailable",
        body:
          "The project AI request failed."
      });

    } finally {
      setChatLoading(
        false
      );
    }
  }

  return (
    <div className="project-workbench">

      {
        toast && (
          <div className="vector-toast">

            <div className="toast-mark">
              →
            </div>

            <div>
              <strong>
                {toast.title}
              </strong>

              <span>
                {toast.body}
              </span>
            </div>

          </div>
        )
      }

      <header className="workbench-header">

        <div className="workbench-project">

          <div className="workbench-project-icon">
            →
          </div>

          <div>

            <span>
              Project
            </span>

            <h1>
              {project.name}
            </h1>

            <p>
              {
                project.description ||
                "No description yet."
              }
            </p>

          </div>

        </div>

        <div className="workbench-header-actions">

          <span
            className={
              `project-privacy privacy-${project.privacy_level}`
            }
          >
            {
              PRIVACY_NAMES[
                project.privacy_level
              ]
            }
          </span>

          <button
            type="button"
            className="quiet-action"
            onClick={
              enableNotifications
            }
          >
            ◉
            {" "}
            Notify
          </button>

        </div>

      </header>

      <nav className="workbench-tabs">

        {
          [
            [
              "overview",
              "Overview"
            ],
            [
              "chat",
              "Chat"
            ],
            [
              "files",
              "Files"
            ],
            [
              "tasks",
              "Tasks"
            ],
            [
              "activity",
              "Activity"
            ]
          ].map(
            (
              item
            ) => (
              <button
                key={
                  item[0]
                }
                type="button"
                className={
                  tab ===
                  item[0]
                    ? "active"
                    : ""
                }
                onClick={
                  () =>
                    setTab(
                      item[0]
                    )
                }
              >
                {
                  item[1]
                }
              </button>
            )
          )
        }

      </nav>

      {
        tab ===
        "overview" && (
          <section className="project-overview">

            <div className="project-stat-row">

              <div>
                <span>
                  Files
                </span>

                <strong>
                  {
                    stats.totalFiles
                  }
                </strong>
              </div>

              <div>
                <span>
                  Indexed
                </span>

                <strong>
                  {
                    stats.indexedFiles
                  }
                </strong>
              </div>

              <div>
                <span>
                  Context chunks
                </span>

                <strong>
                  {
                    stats.chunks
                  }
                </strong>
              </div>

              <div>
                <span>
                  Storage
                </span>

                <strong>
                  {
                    stats.storage
                  }
                </strong>
              </div>

              <div>
                <span>
                  Tasks done
                </span>

                <strong>
                  {
                    completedTasks
                  }/
                  {
                    localTasks.length
                  }
                </strong>
              </div>

            </div>

            <div className="project-overview-grid">

              <article className="project-action-panel">

                <div className="panel-head">
                  <strong>
                    Start working
                  </strong>

                  <span>
                    Vector project actions
                  </span>
                </div>

                <div className="project-action-grid">

                  <button
                    type="button"
                    onClick={
                      () =>
                        setTab(
                          "chat"
                        )
                    }
                  >
                    <span>
                      ✦
                    </span>

                    <strong>
                      Ask Vector
                    </strong>

                    <small>
                      Analyse files,
                      research or plan work
                    </small>
                  </button>

                  <button
                    type="button"
                    onClick={
                      () =>
                        uploadRef
                          .current
                          ?.click()
                    }
                  >
                    <span>
                      ↑
                    </span>

                    <strong>
                      Upload
                    </strong>

                    <small>
                      Add project files
                    </small>
                  </button>

                  <button
                    type="button"
                    onClick={
                      () => {
                        setCreateFileOpen(
                          true
                        );

                        setTab(
                          "files"
                        );
                      }
                    }
                  >
                    <span>
                      ＋
                    </span>

                    <strong>
                      Create file
                    </strong>

                    <small>
                      Start code or docs
                    </small>
                  </button>

                  <button
                    type="button"
                    onClick={
                      () =>
                        setTab(
                          "tasks"
                        )
                    }
                  >
                    <span>
                      ✓
                    </span>

                    <strong>
                      Plan tasks
                    </strong>

                    <small>
                      Organise the project
                    </small>
                  </button>

                </div>

              </article>



            </div>

          </section>
        )
      }

      {
        tab ===
        "chat" && (
          <section className="project-chat">

            {
              privacyNotice && (
                <div className="privacy-warning">

                  <div className="privacy-warning-icon">
                    !
                  </div>

                  <div>

                    <strong>
                      Sensitive values protected
                    </strong>

                    <span>
                      The following values were replaced before external processing:
                    </span>

                    <div className="privacy-value-list">

                      {
                        privacyNotice.map(
                          (
                            item,
                            index
                          ) => (
                            <code
                              key={
                                `${item.placeholder}-${index}`
                              }
                            >
                              {
                                item.displayValue
                              }
                              {" → "}
                              {
                                item.placeholder
                              }
                            </code>
                          )
                        )
                      }

                    </div>

                  </div>

                  <button
                    type="button"
                    onClick={
                      () =>
                        setPrivacyNotice(
                          null
                        )
                    }
                  >
                    ×
                  </button>

                </div>
              )
            }

            <div className="project-chat-head">

              <div>

                <strong>
                  Vector
                </strong>

                <span>
                  Project-aware assistant
                </span>

              </div>

              <div className="v5-project-chat-controls">

                <select
                  value={
                    conversationId ||
                    "new"
                  }
                  onChange={
                    (
                      event
                    ) => {
                      const value =
                        event.target.value;

                      if (
                        value ===
                        "new"
                      ) {
                        loadConversation(
                          null
                        );
                      } else {
                        loadConversation(
                          value
                        );
                      }
                    }
                  }
                >

                  <option value="new">
                    + New chat
                  </option>

                  {
                    projectConversations.map(
                      (
                        conversation
                      ) => (
                        <option
                          key={
                            conversation.id
                          }
                          value={
                            conversation.id
                          }
                        >
                          {
                            conversation.title
                          }
                        </option>
                      )
                    )
                  }

                </select>

                <select
                  value={
                    chatMode
                  }
                onChange={
                  (
                    event
                  ) =>
                    setChatMode(
                      event.target.value
                    )
                }
              >
                <option value="auto">
                  Auto
                </option>

                <option value="normal">
                  Normal
                </option>

                <option value="research">
                  Research
                </option>

                <option value="deep">
                  Deep
                </option>
              </select>

              </div>

            </div>

            <div className="project-chat-messages">

              {
                chatMessages.length ===
                0 && (
                  <div className="project-chat-empty">

                    <div>
                      ✦
                    </div>

                    <h2>
                      Work with this project
                    </h2>

                    <p>
                      Vector can search indexed
                      project files locally before
                      asking an external model.
                    </p>

                    <div className="project-chat-suggestions">

                      <button
                        onClick={
                          () =>
                            setChatInput(
                              "Analyse the project files and identify the most important problems."
                            )
                        }
                      >
                        Analyse project
                      </button>

                      <button
                        onClick={
                          () =>
                            setChatInput(
                              "Summarise this project and tell me what I should work on next."
                            )
                        }
                      >
                        What next?
                      </button>

                      <button
                        onClick={
                          () =>
                            setChatInput(
                              "Review the project for security issues and technical risks."
                            )
                        }
                      >
                        Security review
                      </button>

                    </div>

                  </div>
                )
              }

              {
                chatMessages.map(
                  (
                    message
                  ) => (
                    <article
                      key={
                        message.id
                      }
                      className={
                        `project-chat-message ${message.role}`
                      }
                    >

                      {
                        message.role ===
                        "assistant" && (
                          <div className="project-ai-avatar">
                            V
                          </div>
                        )
                      }

                      <div className="project-chat-body">

                        <span className="project-chat-name">
                          {
                            message.role ===
                            "assistant"
                              ? "Vector"
                              : "You"
                          }
                        </span>

                        {
                          message.role ===
                          "assistant"
                            ? (
                              <div className="project-markdown">
                                <Markdown>
                                  {
                                    message.content
                                  }
                                </Markdown>
                              </div>
                            )
                            : (
                              <div className="project-user-bubble">
                                {
                                  message.content
                                }
                              </div>
                            )
                        }

                        {
                          message.meta
                            ?.toolTrace
                            ?.length >
                            0 && (
                            <div className="agent-tool-trace">

                              {
                                message.meta
                                  .toolTrace
                                  .map(
                                    (
                                      tool,
                                      index
                                    ) => (
                                      <span
                                        key={
                                          `${tool.tool}-${index}`
                                        }
                                        className={
                                          tool.success
                                            ? "success"
                                            : "failed"
                                        }
                                      >
                                        <i>
                                          {
                                            tool.success
                                              ? "✓"
                                              : "!"
                                          }
                                        </i>

                                        {
                                          tool.tool
                                            .replaceAll(
                                              "_",
                                              " "
                                            )
                                        }
                                      </span>
                                    )
                                  )
                              }

                            </div>
                          )
                        }

                        {
                          message.retrieval
                            ?.length >
                            0 && (
                            <div className="retrieval-used">

                              Used local context:

                              {
                                message.retrieval
                                  .slice(
                                    0,
                                    4
                                  )
                                  .map(
                                    (
                                      item
                                    ) => (
                                      <span
                                        key={
                                          `${item.file}-${item.startLine}`
                                        }
                                      >
                                        {
                                          item.file
                                        }
                                        :
                                        {
                                          item.startLine
                                        }
                                        -
                                        {
                                          item.endLine
                                        }
                                      </span>
                                    )
                                  )
                              }

                            </div>
                          )
                        }

                        {
                          message.role ===
                          "assistant" && (
                            <div className="project-answer-actions">

                              <button
                                type="button"
                                title="Copy response"
                                onClick={
                                  () =>
                                    copyText(
                                      message.id,
                                      message.content
                                    )
                                }
                              >
                                {
                                  copied ===
                                  message.id
                                    ? "✓"
                                    : "⧉"
                                }
                              </button>

                              {
                                message.meta && (
                                  <span>
                                    {
                                      message.meta.model
                                    }
                                    {" · "}
                                    {
                                      money(
                                        message.meta.costChf
                                      )
                                    }
                                  </span>
                                )
                              }

                            </div>
                          )
                        }

                      </div>

                    </article>
                  )
                )
              }

              {
                chatLoading && (
                  <div className="project-chat-message assistant">

                    <div className="project-ai-avatar">
                      V
                    </div>

                    <div className="project-working">
                      <span />
                      <span />
                      <span />
                    </div>

                  </div>
                )
              }

              <div ref={chatBottomRef} />

            </div>

            <form
              className="project-chat-composer"
              onSubmit={
                sendProjectMessage
              }
            >

              <textarea
                rows="2"
                value={
                  chatInput
                }
                placeholder="Ask Vector to analyse, research, plan or build…"
                onChange={
                  (
                    event
                  ) =>
                    setChatInput(
                      event.target.value
                    )
                }
                onKeyDown={
                  (
                    event
                  ) => {
                    if (
                      event.key ===
                      "Enter" &&
                      !event.shiftKey
                    ) {
                      event.preventDefault();

                      event
                        .currentTarget
                        .form
                        ?.requestSubmit();
                    }
                  }
                }
              />

              <div>

                <span>
                  Local retrieval · Privacy Vault · Cost Guard
                </span>

                <button
                  type="submit"
                  disabled={
                    chatLoading ||
                    !chatInput.trim()
                  }
                >
                  ↑
                </button>

              </div>

            </form>

          </section>
        )
      }

      {
        tab ===
        "files" && (
          <section className="project-files-workbench">

            <div className="files-toolbar">

              <div>

                <strong>
                  Project files
                </strong>

                <span>
                  {
                    localFiles.length
                  }
                  {" files · "}
                  {
                    stats.storage
                  }
                </span>

              </div>

              <div>

                <input
                  ref={
                    uploadRef
                  }
                  hidden
                  multiple
                  type="file"
                  onChange={
                    (
                      event
                    ) =>
                      uploadFiles(
                        event.target.files
                      )
                  }
                />

                <button
                  type="button"
                  onClick={
                    () =>
                      setCreateFileOpen(
                        true
                      )
                  }
                >
                  + File
                </button>

                <button
                  type="button"
                  disabled={
                    uploading
                  }
                  onClick={
                    () =>
                      uploadRef
                        .current
                        ?.click()
                  }
                >
                  ↑ Upload
                </button>

              </div>

            </div>

            {
              createFileOpen && (
                <div className="create-file-panel">

                  <input
                    value={
                      newFilename
                    }
                    placeholder="filename.js"
                    onChange={
                      (
                        event
                      ) =>
                        setNewFilename(
                          event.target.value
                        )
                    }
                  />

                  <textarea
                    rows="10"
                    value={
                      newFileContent
                    }
                    placeholder="Start writing…"
                    onChange={
                      (
                        event
                      ) =>
                        setNewFileContent(
                          event.target.value
                        )
                    }
                  />

                  <div>

                    <button
                      onClick={
                        () =>
                          setCreateFileOpen(
                            false
                          )
                      }
                    >
                      Cancel
                    </button>

                    <button
                      onClick={
                        createFile
                      }
                    >
                      Create
                    </button>

                  </div>

                </div>
              )
            }

            <div className="file-browser-layout">

              <div className="project-file-browser">

                {
                  localFiles.map(
                    (
                      file
                    ) => (
                      <button
                        type="button"
                        className={
                          preview?.file?.id ===
                          file.id
                            ? "project-file-entry selected"
                            : "project-file-entry"
                        }
                        key={
                          file.id
                        }
                        onClick={
                          () =>
                            openFile(
                              file
                            )
                        }
                      >

                        <span className="project-file-icon">

                          {
                            String(
                              file.mime_type ||
                              ""
                            ).startsWith(
                              "image/"
                            )
                              ? "IMG"
                              : file.mime_type ===
                                "application/pdf"
                                ? "PDF"
                                : (
                                    file.extension ||
                                    "FILE"
                                  )
                                    .slice(
                                      0,
                                      4
                                    )
                                    .toUpperCase()
                          }

                        </span>

                        <span>

                          <strong>
                            {
                              file.original_name
                            }
                          </strong>

                          <small>
                            {
                              bytes(
                                file.size_bytes
                              )
                            }
                          </small>

                        </span>

                      </button>
                    )
                  )
                }

              </div>

              <div className="project-file-editor">

                {
                  !preview && (
                    <div className="file-editor-empty">

                      <span>
                        ◫
                      </span>

                      Select a file to preview
                      or edit it.

                    </div>
                  )
                }

                {
                  preview?.type ===
                  "image" && (
                    <div className="image-preview">

                      <img
                        src={
                          preview.url
                        }
                        alt={
                          preview.name
                        }
                      />

                    </div>
                  )
                }

                {
                  preview?.type ===
                  "pdf" && (
                    <iframe
                      className="pdf-preview"
                      src={
                        preview.url
                      }
                      title={
                        preview.name
                      }
                    />
                  )
                }

                {
                  preview?.type ===
                  "text" && (
                    <div className="text-editor">

                      <div className="text-editor-head">

                        <strong>
                          {
                            preview.name
                          }
                        </strong>

                        <div>

                          {
                            editing
                              ? (
                                <>
                                  <button
                                    onClick={
                                      () =>
                                        setEditing(
                                          false
                                        )
                                    }
                                  >
                                    Cancel
                                  </button>

                                  <button
                                    onClick={
                                      saveTextFile
                                    }
                                  >
                                    Save
                                  </button>
                                </>
                              )
                              : (
                                <button
                                  onClick={
                                    () =>
                                      setEditing(
                                        true
                                      )
                                  }
                                >
                                  Edit
                                </button>
                              )
                          }

                        </div>

                      </div>

                      {
                        editing
                          ? (
                            <textarea
                              value={
                                editorContent
                              }
                              onChange={
                                (
                                  event
                                ) =>
                                  setEditorContent(
                                    event.target.value
                                  )
                              }
                            />
                          )
                          : (
                            <pre>
                              {
                                editorContent
                              }
                            </pre>
                          )
                      }

                    </div>
                  )
                }

              </div>

            </div>

          </section>
        )
      }

      {
        tab ===
        "tasks" && (
          <section className="project-task-workspace">

            <div className="task-create">

              <input
                value={
                  taskTitle
                }
                placeholder="Add a task…"
                onChange={
                  (
                    event
                  ) =>
                    setTaskTitle(
                      event.target.value
                    )
                }
                onKeyDown={
                  (
                    event
                  ) => {
                    if (
                      event.key ===
                      "Enter"
                    ) {
                      createTask();
                    }
                  }
                }
              />

              <button
                onClick={
                  createTask
                }
              >
                Add
              </button>

            </div>

            <div className="task-columns">

              {
                [
                  [
                    "pending",
                    "To do"
                  ],
                  [
                    "running",
                    "In progress"
                  ],
                  [
                    "completed",
                    "Done"
                  ]
                ].map(
                  (
                    column
                  ) => (
                    <div
                      className="task-column"
                      key={
                        column[0]
                      }
                    >

                      <div className="task-column-head">

                        {
                          column[1]
                        }

                        <span>
                          {
                            localTasks.filter(
                              (
                                task
                              ) =>
                                task.status ===
                                column[0]
                            ).length
                          }
                        </span>

                      </div>

                      {
                        localTasks
                          .filter(
                            (
                              task
                            ) =>
                              task.status ===
                              column[0]
                          )
                          .map(
                            (
                              task
                            ) => (
                              <article
                                className="task-card"
                                key={
                                  task.id
                                }
                              >

                                <strong>
                                  {
                                    task.title
                                  }
                                </strong>

                                <div>

                                  {
                                    column[0] !==
                                    "pending" && (
                                      <button
                                        onClick={
                                          () =>
                                            setTaskStatus(
                                              task,
                                              "pending"
                                            )
                                        }
                                      >
                                        ←
                                      </button>
                                    )
                                  }

                                  {
                                    column[0] !==
                                    "completed" && (
                                      <button
                                        onClick={
                                          () =>
                                            setTaskStatus(
                                              task,
                                              column[0] ===
                                              "pending"
                                                ? "running"
                                                : "completed"
                                            )
                                        }
                                      >
                                        →
                                      </button>
                                    )
                                  }

                                </div>

                              </article>
                            )
                          )
                      }

                    </div>
                  )
                )
              }

            </div>

          </section>
        )
      }

      {
        tab ===
        "activity" && (
          <section className="project-activity">

            {
              activity.length ===
              0
                ? (
                  <div className="activity-empty">
                    No activity yet.
                  </div>
                )
                : activity.map(
                  (
                    item
                  ) => (
                    <div
                      className="activity-row"
                      key={
                        item.id
                      }
                    >

                      <div className="activity-dot" />

                      <div>

                        <strong>
                          {
                            item.action
                          }
                        </strong>

                        <span>
                          {
                            item.actor
                          }
                          {" · "}
                          {
                            new Date(
                              item.created_at
                            )
                              .toLocaleString()
                          }
                        </span>

                      </div>

                    </div>
                  )
                )
            }

          </section>
        )
      }

    </div>
  );
}
