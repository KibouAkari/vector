"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ArrowUp, Check, Copy, Menu, Plus, RefreshCw, Search, Square, Trash2, X, Sparkles, Paperclip, Code2, CheckCheck, PanelLeft, FileText, LoaderCircle, MessageSquareText } from "lucide-react";
import VectorChatArtifact from "../../components/ui/vector-chat-artifact";
import { conversationGroups } from "../../lib/chat-history-groups.mjs";

const MODE_OPTIONS = [
  { value: "quick", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "deep", label: "High" },
  { value: "research", label: "Search" }
];

function formatMoney(value) {
  const number = Number(value || 0);
  if (number <= 0) return "CHF 0.00";
  if (number < 0.01) return "< CHF 0.01";
  return `CHF ${number.toFixed(2)}`;
}

function shortText(text) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  if (clean.length <= 56) return clean;
  return clean.slice(0, 53) + "...";
}

function safeAssistantText(text) {
  const value = String(text || "").trim();

  if (!value) {
    return [
      "Vector returned an empty response.",
      "",
      "Use **Try again** to regenerate the answer.",
      "If this happens repeatedly, switch the thinking level to **Normal** or **High**."
    ].join("\n");
  }

  return value;
}

function normaliseMessages(list) {
  return (list || []).map((message) => {
    if (message.role === "assistant") {
      return {
        ...message,
        content: safeAssistantText(message.content),
        meta: {
          model: message.model || message.meta?.model,
          costChf: message.costChf ?? message.meta?.costChf ?? 0
        }
      };
    }

    return {
      ...message,
      attachments: message.attachments || []
    };
  });
}

function MarkdownCodeBlock({
  children
}) {
  const [copied, setCopied] =
    useState(false);

  const child =
    Array.isArray(children)
      ? children[0]
      : children;

  const className =
    String(
      child?.props?.className ||
      ""
    );

  const language =
    className
      .replace(
        /^language-/,
        ""
      )
      .trim();

  const rawCode =
    child?.props?.children;

  const code =
    (
      Array.isArray(rawCode)
        ? rawCode.join("")
        : String(
            rawCode ??
            ""
          )
    ).replace(
      /\n$/,
      ""
    );

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(
        code
      );

      setCopied(true);

      window.setTimeout(
        () => setCopied(false),
        1400
      );
    } catch {
      // Clipboard support is best-effort.
    }
  }

  return (
    <div className="v569-code-block vx585d-code">
      <div className="v569-code-head">
        <div className="vx585d-code-language">
          <Code2 size={14} strokeWidth={1.8} aria-hidden="true" />
          <span>{language || "Code"}</span>
        </div>
        <button type="button" className="v569-code-copy"
          onClick={copyCode} aria-label={copied ? "Copied code" : "Copy code"}
          title={copied ? "Copied" : "Copy code"}>
          {copied ? <CheckCheck size={15} aria-hidden="true" /> :
            <Copy size={15} aria-hidden="true" />}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre><code className={className}>{code}</code></pre>
    </div>
  );
}


function Markdown({ children }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a({
          href,
          children
        }) {
          return (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
            >
              {children}
            </a>
          );
        },

        pre({
          children
        }) {
          return (
            <MarkdownCodeBlock>
              {children}
            </MarkdownCodeBlock>
          );
        },

        code({
          className,
          children,
          ...props
        }) {
          return (
            <code
              className={className}
              {...props}
            >
              {children}
            </code>
          );
        }
      }}
    >
      {children}
    </ReactMarkdown>
  );
}


function IconButton({ label, onClick, disabled = false }) {
  const Icon = label === "Copied" ? Check :
    label.toLowerCase().includes("copy") ? Copy : RefreshCw;
  return (
    <button type="button" className="v54-action-button"
      onClick={onClick} disabled={disabled} aria-label={label} title={label}>
      <Icon size={15} strokeWidth={1.8} aria-hidden="true" />
      <span>{label}</span>
    </button>
  );
}

export default function ChatClient({
  displayName,
  userId
}) {
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("normal");
  const [activeJob, setActiveJob] = useState(null);


  /*
   * VECTOR_FAILED_JOB_RETRY_UI_57710
   *
   * A failed background job remains linked to its original
   * user message. Retrying requeues that job instead of
   * calling sendText() again.
   */
  const [
    failedJob,
    setFailedJob
  ] =
    useState(null);

  const [
    retryingJobId,
    setRetryingJobId
  ] =
    useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState(null);
  const [error, setError] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [previewImage, setPreviewImage] = useState(null);

  /*
   * VECTOR_RAPID_SUBMIT_RELIABILITY_582C
   *
   * activeJob starts only after /api/chat has accepted the request.
   * Keep a separate client-side submission lock for that short window.
   */
  const [
    submitting,
    setSubmitting
  ] =
    useState(false);

  const uploadRef = useRef(null);
  const bottomRef = useRef(null);
  const composerInputRef = useRef(null);
  const previewCloseRef = useRef(null);
  const pollRef = useRef(null);

  const sendInFlightRef =
    useRef(false);

  /*
   * VECTOR_CONVERSATION_ISOLATION_581
   *
   * React state below represents only the conversation currently
   * visible in this workspace.
   *
   * Background jobs continue independently on the server. A poll
   * belonging to another conversation may never mutate the visible
   * job/error state or navigate the UI back to its conversation.
   */
  const conversationIdRef =
    useRef(null);

  const conversationLoadRef =
    useRef(0);

  function isVisibleConversation(
    id
  ) {
    return Boolean(
      id &&
      conversationIdRef.current ===
        id
    );
  }

  function stopVisiblePolling() {
    if (
      pollRef.current
    ) {
      clearTimeout(
        pollRef.current
      );

      pollRef.current =
        null;
    }
  }

  const currentConversationSpend = useMemo(() => {
    return messages.reduce((sum, message) => {
      return sum + Number(message?.meta?.costChf || 0);
    }, 0);
  }, [messages]);

  async function loadConversations(query = "") {
    try {
      const suffix = query.trim()
        ? `?q=${encodeURIComponent(query.trim())}`
        : "";

      const response = await fetch(`/api/conversations${suffix}`, {
        cache: "no-store"
      });

      if (!response.ok) return [];

      const data = await response.json();
      const list = data.conversations || [];
      setConversations(list);
      return list;
    } catch {
      return [];
    }
  }

  async function loadConversation(
    id,
    closeHistory = true,
    recoverJob = true
  ) {
    if (!id) return;

    /*
     * Selecting another conversation immediately detaches the
     * previous conversation's visible runtime state.
     */
    const loadToken =
      conversationLoadRef.current +
      1;

    conversationLoadRef.current =
      loadToken;

    conversationIdRef.current =
      id;

    setConversationId(
      id
    );

    stopVisiblePolling();

    setActiveJob(null);
    setFailedJob(null);
    setRetryingJobId(null);
    setError(null);
    setNotice(null);

    const [
      response,
      attachmentResponse
    ] =
      await Promise.all([
        fetch(
          `/api/conversations/${id}`,
          {
            cache:
              "no-store"
          }
        ),

        fetch(
          `/api/chat/attachments?conversationId=${encodeURIComponent(
            id
          )}`,
          {
            cache:
              "no-store"
          }
        )
      ]);

    /*
     * Ignore a late response from a conversation that the user
     * has already left.
     */
    if (
      !isVisibleConversation(
        id
      ) ||
      conversationLoadRef.current !==
        loadToken
    ) {
      return;
    }

    const data =
      await response.json();

    if (!response.ok) {
      setMessages([]);

      setError(
        data.error ||
        "Could not load the conversation."
      );

      return;
    }

    let attachmentData = {
      attachments: []
    };

    if (attachmentResponse.ok) {
      try {
        attachmentData =
          await attachmentResponse.json();
      } catch {
        //
      }
    }

    if (
      !isVisibleConversation(
        id
      ) ||
      conversationLoadRef.current !==
        loadToken
    ) {
      return;
    }

    const byMessage =
      new Map();

    for (
      const attachment
      of attachmentData.attachments ||
      []
    ) {
      if (!attachment.messageId) {
        continue;
      }

      const current =
        byMessage.get(
          attachment.messageId
        ) ||
        [];

      current.push(
        attachment
      );

      byMessage.set(
        attachment.messageId,
        current
      );
    }

    const hydratedMessages =
      (data.messages || []).map(
        (message) => ({
          ...message,

          attachments:
            byMessage.get(
              message.id
            ) ||
            message.attachments ||
            []
        })
      );

    localStorage.setItem(
      `vector.activeConversation:${userId}`,
      id
    );

    setMessages(
      normaliseMessages(
        hydratedMessages
      )
    );

    if (closeHistory) {
      setHistoryOpen(false);
    }

    if (
      recoverJob &&
      isVisibleConversation(
        id
      )
    ) {
      await recoverConversationJob(
        id
      );
    }
  }


  async function recoverConversationJob(
    id
  ) {
    if (
      !isVisibleConversation(
        id
      )
    ) {
      return false;
    }

    setActiveJob(null);
    setFailedJob(null);

    try {
      const response =
        await fetch(
          `/api/jobs?conversationId=${encodeURIComponent(
            id
          )}`,
          {
            cache:
              "no-store"
          }
        );

      if (
        !response.ok ||
        !isVisibleConversation(
          id
        )
      ) {
        return false;
      }

      const data =
        await response.json();

      if (
        !isVisibleConversation(
          id
        )
      ) {
        return false;
      }

      const job =
        data.jobs?.[0];

      if (!job) {
        return false;
      }

      if (
        job.status ===
          "queued" ||
        job.status ===
          "running"
      ) {
        setActiveJob({
          ...job,
          conversationId:
            id
        });

        pollJob(
          job.id,
          id
        );

        return true;
      }

      if (
        job.status ===
        "completed"
      ) {
        const detail =
          await fetch(
            `/api/jobs/${job.id}`,
            {
              cache:
                "no-store"
            }
          );

        if (
          detail.ok &&
          isVisibleConversation(
            id
          )
        ) {
          await loadConversation(
            id,
            false,
            false
          );
        }

        return false;
      }

      if (
        job.status ===
        "failed"
      ) {
        setError(null);

        setFailedJob({
          ...job,
          conversationId:
            id
        });

        return false;
      }

      return false;

    } catch {
      /*
       * Recovery is best-effort. The server job remains
       * authoritative.
       */
      return false;
    }
  }


  async function recoverVisibleConversationJob() {
    const id =
      conversationIdRef.current;

    if (!id) {
      return false;
    }

    await recoverConversationJob(
      id
    );

    return true;
  }


  /*
   * VECTOR_CHAT_STORAGE_SCOPE_5641
   *
   * localStorage belongs to the browser origin, not to a Vector account.
   * Remove the pre-isolation global key once and keep the active chat
   * namespaced by the authenticated user ID.
   */
  useEffect(
    () => {
      localStorage.removeItem(
        [
          "vector",
          "activeConversation"
        ].join(".")
      );
    },
    [
      userId
    ]
  );


  useEffect(() => {
    let alive = true;

    async function start() {
      const list = await loadConversations();

      if (!alive) return;

      /*
       * VECTOR_CONVERSATION_ISOLATION_581
       *
       * Restore the user's selected conversation first.
       * Do not navigate to an arbitrary background job.
       */
      const saved = localStorage.getItem(
        `vector.activeConversation:${userId}`
      );

      if (
        saved &&
        list.some(
          (conversation) =>
            conversation.id === saved
        )
      ) {
        await loadConversation(
          saved,
          false
        );
      } else if (saved) {
        localStorage.removeItem(
          `vector.activeConversation:${userId}`
        );
      }
    }

    start();

    return () => {
      alive = false;
      if (pollRef.current) {
        clearTimeout(pollRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      loadConversations(search);
    }, 250);

    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    requestAnimationFrame(() => {
      bottomRef.current?.scrollIntoView({
        behavior: activeJob ? "smooth" : "auto"
      });
    });
  }, [messages, activeJob, error, notice]);

  async function pollJob(
    jobId,
    targetConversationId
  ) {
    /*
     * Only one poll belongs to the visible workspace.
     * Leaving the conversation detaches this poll; the actual
     * background job continues on the server.
     */
    if (
      !isVisibleConversation(
        targetConversationId
      )
    ) {
      return;
    }

    stopVisiblePolling();

    try {
      const response =
        await fetch(
          `/api/jobs/${jobId}`,
          {
            cache:
              "no-store"
          }
        );

      if (
        !isVisibleConversation(
          targetConversationId
        )
      ) {
        return;
      }

      if (!response.ok) {
        throw new Error(
          "job poll failed"
        );
      }

      const job =
        await response.json();

      if (
        !isVisibleConversation(
          targetConversationId
        )
      ) {
        return;
      }

      if (
        job.status ===
          "queued" ||
        job.status ===
          "running"
      ) {
        setFailedJob(null);

        setActiveJob({
          ...job,
          conversationId:
            targetConversationId
        });

        pollRef.current =
          setTimeout(
            () => {
              if (
                isVisibleConversation(
                  targetConversationId
                )
              ) {
                pollJob(
                  jobId,
                  targetConversationId
                );
              }
            },
            900
          );

        return;
      }

      setActiveJob(null);

      if (
        job.status ===
        "completed"
      ) {
        if (
          isVisibleConversation(
            targetConversationId
          )
        ) {
          await loadConversation(
            targetConversationId,
            false,
            false
          );
        }

        await loadConversations(
          search
        );

        return;
      }

      if (
        job.status ===
        "cancelled"
      ) {
        if (
          isVisibleConversation(
            targetConversationId
          )
        ) {
          setNotice(
            "Generation stopped"
          );

          await loadConversation(
            targetConversationId,
            false,
            false
          );
        }

        return;
      }

      if (
        isVisibleConversation(
          targetConversationId
        )
      ) {
        setError(null);

        setFailedJob({
          ...job,
          conversationId:
            targetConversationId
        });
      }

    } catch {
      if (
        isVisibleConversation(
          targetConversationId
        )
      ) {
        pollRef.current =
          setTimeout(
            () => {
              if (
                isVisibleConversation(
                  targetConversationId
                )
              ) {
                pollJob(
                  jobId,
                  targetConversationId
                );
              }
            },
            1800
          );
      }
    }
  }


  async function copyMessage(id, text) {
    try {
      await navigator.clipboard.writeText(text || "");
      setCopiedId(id);

      setTimeout(() => {
        setCopiedId(null);
      }, 1300);
    } catch {
      setError("The message could not be copied.");
    }
  }

  function newConversation() {
    conversationLoadRef.current +=
      1;

    conversationIdRef.current =
      null;

    stopVisiblePolling();

    setConversationId(null);
    setActiveJob(null);
    setFailedJob(null);
    setRetryingJobId(null);

    localStorage.removeItem(
      `vector.activeConversation:${userId}`
    );

    setMessages([]);
    setInput("");
    setError(null);
    setNotice(null);
    setHistoryOpen(false);
    setAttachments([]);
  }

  async function deleteConversation(id) {
    await fetch(`/api/conversations/${id}`, {
      method: "DELETE"
    });

    if (conversationId === id) {
      newConversation();
    }

    await loadConversations(search);
  }

  async function removePendingAttachment(
    attachment
  ) {
    if (!attachment?.id) {
      return;
    }

    const response =
      await fetch(
        `/api/chat/attachments/${attachment.id}`,
        {
          method:
            "DELETE"
        }
      );

    if (!response.ok) {
      const data =
        await response.json()
          .catch(
            () => ({})
          );

      setError(
        data.error ||
        "Could not remove attachment."
      );

      return;
    }

    setAttachments(
      (current) =>
        current.filter(
          (item) =>
            item.id !==
            attachment.id
        )
    );
  }


  async function chooseFiles(files) {
    const remaining =
      Math.max(
        0,
        6 -
        attachments.length
      );

    const chosen =
      Array.from(
        files ||
        []
      ).slice(
        0,
        remaining
      );

    if (chosen.length === 0) {
      if (
        files?.length &&
        remaining === 0
      ) {
        setError(
          "A maximum of 6 attachments can be added to one message."
        );
      }

      return;
    }

    setError(null);

    setNotice(
      chosen.length === 1
        ? "Uploading file…"
        : `Uploading ${chosen.length} files…`
    );

    const uploaded = [];

    for (const file of chosen) {
      const formData =
        new FormData();

      formData.append(
        "file",
        file
      );

      try {
        const response =
          await fetch(
            "/api/chat/attachments",
            {
              method:
                "POST",

              body:
                formData
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            data.error ||
            "Upload failed"
          );
        }

        uploaded.push(
          data.attachment
        );

      } catch (error) {
        setError(
          `${file.name}: ${
            error.message ||
            "upload failed"
          }`
        );
      }
    }

    if (uploaded.length > 0) {
      setAttachments(
        (current) =>
          [
            ...current,
            ...uploaded
          ].slice(
            0,
            6
          )
      );
    }

    setNotice(null);

    if (uploadRef.current) {
      uploadRef.current.value =
        "";
    }
  }


  async function sendText(textValue) {
    const typedText =
      String(
        textValue ||
        ""
      ).trim();

    const text =
      typedText ||
      (
        attachments.length
          ? "Please analyze the attached file(s)."
          : ""
      );

    if (
      !text ||
      activeJob ||
      sendInFlightRef.current
    ) {
      return;
    }

    /*
     * A previous completed-job refresh may still be fetching the old
     * conversation snapshot. Invalidate that load before adding the new
     * optimistic user message so it can never overwrite this submission.
     */
    conversationLoadRef.current +=
      1;

    sendInFlightRef.current =
      true;

    setSubmitting(true);

    const tempId =
      `temp-${Date.now()}`;

    const attachmentSnapshot =
      [
        ...attachments
      ];

    setInput("");
    setError(null);
    setNotice(null);
    setFailedJob(null);
    setRetryingJobId(null);

    setMessages(
      (current) => [
        ...current,

        {
          id:
            tempId,

          role:
            "user",

          content:
            text,

          attachments:
            attachmentSnapshot
        }
      ]
    );

    try {
      const response =
        await fetch(
          "/api/chat",
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

                conversationId:
                  conversationIdRef.current ||
                  conversationId,

                mode,

                attachmentIds:
                  attachmentSnapshot.map(
                    (attachment) =>
                      attachment.id
                  )
              })
          }
        );

      const data =
        await response.json();

      if (!response.ok) {
        setMessages(
          (current) =>
            current.filter(
              (message) =>
                message.id !==
                tempId
            )
        );

        setError(
          data.message ||
          data.reason ||
          data.error ||
          "Vector could not start the request."
        );

        return;
      }

      setAttachments([]);

      const id =
        data.conversationId;

      conversationLoadRef.current +=
        1;

      conversationIdRef.current =
        id;

      setConversationId(
        id
      );

      localStorage.setItem(
        `vector.activeConversation:${userId}`,
        id
      );

      setMessages(
        (current) =>
          current.map(
            (message) =>
              message.id ===
                tempId
                ? {
                    ...message,

                    id:
                      data.userMessage
                        ?.id ||
                      tempId,

                    attachments:
                      attachmentSnapshot
                  }
                : message
          )
      );

      await loadConversations(search);

      if (data.jobId) {
        const job = {
          id:
            data.jobId,

          conversationId:
            id,

          status:
            "queued",

          progress:
            data.progress
        };

        setActiveJob(job);

        pollJob(
          data.jobId,
          id
        );

        return;
      }

      if (data.message) {
        setMessages(
          (current) => [
            ...current,

            {
              id:
                data.message.id,

              role:
                "assistant",

              content:
                safeAssistantText(
                  data.message.content
                ),

              meta:
                data.meta
            }
          ]
        );
      }

    } catch {
      setNotice(
        "Connection interrupted. Vector continues in the background."
      );

      const recovered =
        await recoverVisibleConversationJob();

      if (recovered) {
        setAttachments([]);
      }

    } finally {
      sendInFlightRef.current =
        false;

      setSubmitting(false);
    }
  }


  async function send(event) {
    event.preventDefault();
    await sendText(input);
  }

  async function stopGeneration() {
    if (!activeJob?.id) return;

    await fetch(`/api/jobs/${activeJob.id}`, {
      method: "DELETE"
    });

    if (pollRef.current) {
      clearTimeout(pollRef.current);
    }

    setActiveJob(null);
    setNotice("Generation stopped");
  }


  async function retryFailedJob() {
    if (
      !failedJob?.id ||
      activeJob ||
      retryingJobId
    ) {
      return;
    }

    const failed =
      failedJob;

    setRetryingJobId(
      failed.id
    );

    setError(null);
    setNotice(null);

    try {
      const response =
        await fetch(
          `/api/jobs/${failed.id}`,
          {
            method:
              "POST"
          }
        );

      const data =
        await response
          .json()
          .catch(
            () => ({})
          );

      if (
        !response.ok
      ) {
        setError(
          data.message ||
          data.error ||
          "Vector could not retry the request."
        );

        return;
      }

      const targetConversationId =
        data.conversationId ||
        failed.conversationId ||
        conversationIdRef.current ||
        conversationId;

      const retriedJob = {
        id:
          data.id ||
          failed.id,

        conversationId:
          targetConversationId,

        status:
          data.status ||
          "queued",

        attempts:
          data.attempts,

        progress:
          data.progress || {
            stage:
              "queued",

            message:
              "Retrying previous request"
          }
      };

      if (
        isVisibleConversation(
          targetConversationId
        )
      ) {
        setFailedJob(null);

        setActiveJob(
          retriedJob
        );

        pollJob(
          retriedJob.id,
          targetConversationId
        );
      }

    } catch {
      setError(
        "Vector could not start the retry."
      );

    } finally {
      setRetryingJobId(null);
    }
  }


  useEffect(() => {
    if (!previewImage) return;
    const previouslyFocused = document.activeElement;
    previewCloseRef.current?.focus();
    const onEscape = event => {
      if (event.key === "Escape") setPreviewImage(null);
    };
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("keydown", onEscape);
      previouslyFocused?.focus?.();
    };
  }, [previewImage]);

  function tryAgain(index) {
    for (let i = index - 1; i >= 0; i -= 1) {
      if (messages[i]?.role === "user") {
        sendText(messages[i].content);
        return;
      }
    }
  }

  return (
    <div className={`vector-chat-shell v54-chat-shell ${historyCollapsed ? "vx586-history-collapsed" : ""}`}>
      {historyOpen && (
        <button
          type="button"
          className="history-backdrop"
          aria-label="Close chat history"
          onClick={() => setHistoryOpen(false)}
        />
      )}

      <aside id="vector-chat-history" className={historyOpen ? "history-panel open" : "history-panel"}>
        <div className="history-head">
          <div className="vx600-history-heading">
            <strong>Conversations</strong>
            <small>{conversations.length} recent</small>
          </div>

          <button
            type="button"
            onClick={newConversation}
            aria-label="New chat"
          >
            <Plus size={17} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </div>

        <div className="history-search">
          <Search size={16} strokeWidth={1.8} aria-hidden="true" />

          <input
            type="search"
            placeholder="Search chats…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>

        <div className="history-list vx600-history-list">
          {conversationGroups(conversations).map(group => (
            <section className="vx600-history-group" key={group.label} aria-label={group.label}>
              <h2 className="vx600-history-group-label">{group.label}</h2>
              {group.items.map(conversation => (
                <div key={conversation.id}
                  className={conversation.id === conversationId
                    ? "history-item active vx600-history-item"
                    : "history-item vx600-history-item"}>
                  <button type="button" className="history-open"
                    aria-current={conversation.id === conversationId ? "page" : undefined}
                    onClick={() => loadConversation(conversation.id)}>
                    <span className="vx600-history-icon" aria-hidden="true">
                      <MessageSquareText size={15} />
                    </span>
                    <span className="vx600-history-text">
                      <span className="history-title">{conversation.title || "New chat"}</span>
                      <span className="history-preview">
                        {shortText(conversation.preview) || "Open conversation"}
                      </span>
                    </span>
                  </button>
                  <button type="button" className="history-delete"
                    onClick={() => deleteConversation(conversation.id)}
                    aria-label={`Delete ${conversation.title || "conversation"}`}
                    title="Delete conversation">
                    <Trash2 size={15} strokeWidth={1.8} aria-hidden="true" />
                  </button>
                </div>
              ))}
            </section>
          ))}
          {conversations.length === 0 && (
            <div className="vx600-history-empty">
              <MessageSquareText size={22} strokeWidth={1.5} aria-hidden="true" />
              <strong>{search ? "No matching conversations" : "Your story starts here"}</strong>
              <span>{search ? "Try a different search term." : "Start a chat to see it here."}</span>
            </div>
          )}
        </div>
      </aside>

      <section className="vector-chat v54-chat">
        <header className="vector-chat-topbar v54-chat-topbar">
          <div className="v54-topbar-left">
            <button
              type="button"
              className="history-toggle"
              aria-label="Toggle chat history"
              title="Toggle conversations"
              aria-controls="vector-chat-history"
              onClick={() => {
                if (window.matchMedia("(max-width: 760px)").matches) {
                  setHistoryOpen(value => !value);
                } else {
                  setHistoryCollapsed(value => !value);
                }
              }}
            >
              <PanelLeft size={19} strokeWidth={1.8} aria-hidden="true" />
            </button>

            <div className="v54-brand-block">
              <img
                src="/vector-assets/brand/vector-mark.svg"
                alt=""
                className="v54-brand-icon"
              />

              <div>
                <strong>Vector</strong>

              </div>
            </div>
          </div>

          <div className="v54-chat-spend" title="Current conversation cost">
            <span>Chat cost</span>
            <strong>{formatMoney(currentConversationSpend)}</strong>
          </div>
        </header>

        {notice && (
          <div className="vector-notice v54-notice">
            <strong>{notice}</strong>
          </div>
        )}

        <div className="vector-chat-content v54-chat-content">
          {messages.length === 0 && !activeJob && (
            <div className="v54-welcome vx585-chat-welcome">
              <img
                src="/vector-assets/brand/vector-mark.svg"
                alt=""
                className="v54-welcome-icon"
              />

              <h2>Hi {displayName || "there"}.</h2>
              <p>What would you like to work on?</p>
              <div className="vx585-prompt-grid">
                {[
                  ["Review code", "Review this code and suggest improvements:"],
                  ["Analyze a document", "Help me analyze a document."],
                  ["Plan a project", "Help me plan a new project."],
                ].map(([label, prompt]) => (
                  <button key={label} type="button"
                    onClick={() => { setInput(prompt); composerInputRef.current?.focus(); }}>
                    <Sparkles size={15} strokeWidth={1.7} aria-hidden="true" />
                    {label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <article
              key={message.id}
              className={`vector-message ${message.role} v54-message`}
            >
              <div className="message-row">
                {message.role === "assistant" && (
                  <div className="message-author v54-message-author">
                    <img
                      src="/vector-assets/brand/vector-mark.svg"
                      alt=""
                    />
                  </div>
                )}

                <div className="message-body v54-message-body">
                  <div className="message-name">
                    {message.role === "assistant"
                      ? "Vector"
                      : displayName || "You"}
                  </div>

                  {message.role === "assistant" ? (
                    <Markdown>{message.content}</Markdown>
                  ) : (
                    <>
                      <div className="user-message-text">
                        {message.content}
                      </div>

                        {message.attachments?.length > 0 && (
                          <div className="v54-message-files">
                            {message.attachments.map((attachment) => {
                              const item =
                                typeof attachment === "string"
                                  ? {
                                      id: null,
                                      name: attachment
                                    }
                                  : attachment;

                              return item.id ? (
                                <a
                                  key={item.id}
                                  href={
                                    item.downloadUrl ||
                                    `/api/chat/attachments/${item.id}/raw`
                                  }
                                  target="_blank"
                                  rel="noreferrer"
                                  title="Download attachment"
                                >
                                  {item.name}
                                </a>
                              ) : (
                                <span key={item.name}>
                                  {item.name}
                                </span>
                              );
                            })}
                          </div>
                        )}
                    </>
                  )}

                  {/* VECTOR_ARTIFACT_CHAT_5742 */}
                  {/* VECTOR_ARTIFACT_CARD_57431 */}

                  {message.role === "assistant" &&
                    message.attachments?.length > 0 && (
                      <div className="v57431-artifact-list vx585-artifact-list">
                        {message.attachments.map((attachment, fileIndex) => (
                          <VectorChatArtifact
                            key={attachment?.id || attachment?.name || fileIndex}
                            attachment={attachment}
                            onPreview={setPreviewImage}
                          />
                        ))}
                      </div>
                    )}

                  {message.role === "assistant" && (
                    <div className="v54-meta-row">
                      <div className="message-meta v54-message-meta">
                        {message.meta?.model && (
                          <span>{message.meta.model}</span>
                        )}
                        <span>{formatMoney(message.meta?.costChf || 0)}</span>
                      </div>

                      <div className="chat-bottom-actions v54-message-actions">
                        <IconButton
                          icon="/vector-assets/icons/copy-link.svg"
                          label={copiedId === message.id ? "Copied" : "Copy"}
                          onClick={() => copyMessage(message.id, message.content)}
                        />

                        <IconButton
                          icon="/vector-assets/icons/retry-refresh.svg"
                          label="Try again"
                          onClick={() => tryAgain(index)}
                          disabled={Boolean(activeJob)}
                        />
                      </div>
                    </div>
                  )}

                  {message.role === "user" && (
                    <div className="v54-user-actions">
                      <IconButton
                        icon="/vector-assets/icons/copy-link.svg"
                        label={copiedId === message.id ? "Copied" : "Copy"}
                        onClick={() => copyMessage(message.id, message.content)}
                      />
                    </div>
                  )}
                </div>
              </div>
            </article>
          ))}


          {failedJob && !activeJob && (
            <article className="vector-message assistant v54-message">
              <div className="message-row">
                <div className="message-author v54-message-author">
                  <img
                    src="/vector-assets/brand/vector-mark.svg"
                    alt=""
                  />
                </div>

                <div className="message-body v54-message-body">
                  <div className="message-name">
                    Vector
                  </div>

                  <div className="v54-running-state">
                    <span>
                      {failedJob.error ||
                        "Vector could not complete the request."}
                    </span>
                  </div>

                  <div className="chat-bottom-actions v54-message-actions">
                    <IconButton
                      icon="/vector-assets/icons/retry-refresh.svg"
                      label={
                        retryingJobId === failedJob.id
                          ? "Retrying…"
                          : "Retry"
                      }
                      onClick={retryFailedJob}
                      disabled={
                        Boolean(
                          activeJob ||
                          retryingJobId
                        )
                      }
                    />
                  </div>
                </div>
              </div>
            </article>
          )}

          {activeJob && (
            <article className="vector-message assistant v54-message">
              <div className="message-row">
                <div className="message-author v54-message-author">
                  <img
                    src="/vector-assets/brand/vector-mark.svg"
                    alt=""
                  />
                </div>

                <div className="message-body v54-message-body">
                  <div className="message-name">Vector</div>

                  <div className="v54-running-state">
                    <div className="v54-pulse" />
                    <span>
                      {activeJob?.progress?.message || "Working in the background…"}
                    </span>
                  </div>

                  <small>You can stay here, switch pages, or close the browser.</small>
                </div>
              </div>
            </article>
          )}

          {error && <div className="vector-error">{error}</div>}

          <div ref={bottomRef} />
        </div>

        <form
          className={
            dragActive
              ? "vector-composer v54-composer v567-drag-active"
              : "vector-composer v54-composer"
          }
          onSubmit={send}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={(event) => {
            if (
              !event.currentTarget.contains(
                event.relatedTarget
              )
            ) {
              setDragActive(false);
            }
          }}
          onDrop={async (event) => {
            event.preventDefault();
            event.stopPropagation();
            setDragActive(false);

            const dropped = Array.from(
              event.dataTransfer?.files || []
            );

            if (dropped.length) {
              await chooseFiles(
                dropped
              );
            }
          }}
        >
          {dragActive && (
            <div className="v567-drop-overlay">
              Drop files here
            </div>
          )}
          <div className="composer-box v54-composer-box">
              {attachments.length > 0 && (
                <div className="v54-attachments">
                  {attachments.map((file) => (
                    <button
                      key={file.id}
                      type="button"
                      onClick={() =>
                        removePendingAttachment(
                          file
                        )
                      }
                      aria-label={`Remove ${file.name}`}
                      title={`Remove ${file.name}`}
                    >
                      <FileText size={15} aria-hidden="true" />
                      <span>{file.name}</span>
                      <X size={14} strokeWidth={2} aria-hidden="true" />
                    </button>
                  ))}
                </div>
              )}

            <textarea
              ref={composerInputRef}
              rows="1"
              value={input}
              placeholder="Message Vector…"
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  if (
                    !activeJob &&
                    !submitting
                  ) {
                    event.currentTarget.form?.requestSubmit();
                  }
                }
              }}
            />

            <div className="v54-composer-bottom">
              <div className="v54-composer-left">
                <input
                  ref={uploadRef}
                  hidden
                  multiple
                  type="file"
                  accept="image/*,.pdf,.docx,.xlsx,.xls,.pptx,.ppt,.txt,.md,.log,.json,.csv,.xml,.yaml,.yml,.js,.jsx,.ts,.tsx,.py,.java,.sh,.ps1,.css,.html,.sql,.conf,.ini,.toml"
                  onChange={(event) => {
                    const selected = Array.from(event.currentTarget.files || []);
                    event.currentTarget.value = "";
                    void chooseFiles(selected);
                  }}
                />

                <button
                  type="button"
                  className="v54-tool-button"
                  onClick={() => uploadRef.current?.click()}
                  disabled={Boolean(notice?.startsWith("Uploading"))}
                  title="Attach files to your message"
                  aria-label="Attach files"
                >
                  {notice?.startsWith("Uploading")
                    ? <LoaderCircle className="vx586-spin" size={16} aria-hidden="true" />
                    : <Paperclip size={16} strokeWidth={1.8} aria-hidden="true" />}
                  <span>{notice?.startsWith("Uploading") ? "Uploading…" : "Attach"}</span>
                </button>
              </div>

              <div className="v54-composer-right">
                <div className="v54-thinking-toggle" role="tablist" aria-label="Thinking level">
                  {MODE_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className={mode === option.value ? "active" : ""}
                      role="tab"
                      aria-selected={mode === option.value}
                      onClick={() => setMode(option.value)}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>

                {activeJob ? (
                  <button
                    type="button"
                    className="v54-send-button v54-stop-button"
                    aria-label="Stop generation"
                    onClick={stopGeneration}
                  >
                    <Square size={16} fill="currentColor" aria-hidden="true" />
                  </button>
                ) : (
                  <button
                    type="submit"
                    className="v54-send-button"
                    aria-label="Send message"
                    disabled={
                      submitting ||
                      (
                        input.trim() === "" &&
                        attachments.length === 0
                      )
                    }
                  >
                    <ArrowUp size={20} strokeWidth={2.1} aria-hidden="true" />
                  </button>
                )}
              </div>
            </div>
          </div>
        </form>
        {previewImage && (
          <div className="vx585-preview-overlay" role="presentation"
            onMouseDown={event => {
              if (event.target === event.currentTarget) setPreviewImage(null);
            }}>
            <div className="vx585-preview-panel" role="dialog"
              aria-modal="true" aria-label={`Image preview: ${previewImage.name}`}>
              <div className="vx585-preview-header">
                <strong>{previewImage.name}</strong>
                <button ref={previewCloseRef} type="button" onClick={() => setPreviewImage(null)}
                  aria-label="Close image preview">
                  <X size={20} aria-hidden="true" />
                </button>
              </div>
              <img src={previewImage.url} alt={previewImage.name} />
              <a href={previewImage.url} download={previewImage.name}
                target="_blank" rel="noreferrer">Download image</a>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
