"use client";
import { callCostLabel } from "../../lib/cost-display.mjs";
import PromptInput from "../../components/chat/prompt-input";
import ConversationSettings from "../../components/chat/conversation-settings";
import { conversationLabel } from "../../lib/chat-presentation.mjs";
import { CHAT_MODES } from "../../lib/chat-controls.mjs";
import { Dialog } from "../../components/ui/overlays";
import PrivacyReceipt from "../../components/ui/privacy-receipt";

import { useEffect, useMemo, useRef, useState } from "react";

import { usePrivacySend } from "../../components/ui/privacy-review-dialog";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowUp,
  Check,
  Copy,
  Menu,
  Plus,
  RefreshCw,
  Search,
  Square,
  Trash2,
  X,
  Sparkles,
  Paperclip,
  Code2,
  CheckCheck,
  PanelLeft,
  FileText,
  LoaderCircle,
  MessageSquareText,
  ChevronDown,
  ShieldOff,
  Clock3,
} from "lucide-react";
import VectorChatArtifact from "../../components/ui/vector-chat-artifact";
import { conversationGroups } from "../../lib/chat-history-groups.mjs";

function formatMoney(value) {
  const number = Number(value || 0);
  if (number <= 0) return "CHF 0.00";
  if (number < 0.01) return "< CHF 0.01";
  return `CHF ${number.toFixed(2)}`;
}

function shortText(text) {
  const clean = String(text || "")
    .replace(/\s+/g, " ")
    .trim();
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
      "If this happens repeatedly, switch the thinking level to **Normal** or **High**.",
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
          ...message.meta,
          costStatus:
            message.costStatus ||
            message.cost_status ||
            message.meta?.costStatus ||
            "estimated",
          model: message.model || message.meta?.model,
          costChf: message.costChf ?? message.meta?.costChf ?? 0,
        },
      };
    }

    return {
      ...message,
      attachments: message.attachments || [],
    };
  });
}

function MarkdownCodeBlock({ children }) {
  const [copied, setCopied] = useState(false);

  const child = Array.isArray(children) ? children[0] : children;

  const className = String(child?.props?.className || "");

  const language = className.replace(/^language-/, "").trim();

  const rawCode = child?.props?.children;

  const code = (
    Array.isArray(rawCode) ? rawCode.join("") : String(rawCode ?? "")
  ).replace(/\n$/, "");

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);

      setCopied(true);

      window.setTimeout(() => setCopied(false), 1400);
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
        <button
          type="button"
          className="v569-code-copy"
          onClick={copyCode}
          aria-label={copied ? "Copied code" : "Copy code"}
          title={copied ? "Copied" : "Copy code"}
        >
          {copied ? (
            <CheckCheck size={15} aria-hidden="true" />
          ) : (
            <Copy size={15} aria-hidden="true" />
          )}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre>
        <code className={className}>{code}</code>
      </pre>
    </div>
  );
}

function Markdown({ children }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noreferrer">
              {children}
            </a>
          );
        },

        pre({ children }) {
          return <MarkdownCodeBlock>{children}</MarkdownCodeBlock>;
        },

        code({ className, children, ...props }) {
          return (
            <code className={className} {...props}>
              {children}
            </code>
          );
        },
      }}
    >
      {children}
    </ReactMarkdown>
  );
}

function IconButton({ label, onClick, disabled = false }) {
  const Icon =
    label === "Copied"
      ? Check
      : label.toLowerCase().includes("copy")
        ? Copy
        : RefreshCw;
  return (
    <button
      type="button"
      className="vc-icon-button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
    >
      <Icon size={15} strokeWidth={1.8} aria-hidden="true" />
    </button>
  );
}

export default function ChatClient({ displayName, userId }) {
  const [conversations, setConversations] = useState([]);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [conversationTitle, setConversationTitle] = useState(null);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("auto");
  const [privacyEnabled, setPrivacyEnabled] = useState(true);
  const [selectedSkillIds, setSelectedSkillIds] = useState([]);
  const [skillParameters, setSkillParameters] = useState({});
  const [freeOnly, setFreeOnly] = useState(false);
  const [activeJob, setActiveJob] = useState(null);
  const [brainEnabled, setBrainEnabled] = useState(true);
  const { privacySend, privacyDialog } = usePrivacySend(
    `${userId}:${conversationId || "new"}`,
  );

  /*
   * VECTOR_FAILED_JOB_RETRY_UI_57710
   *
   * A failed background job remains linked to its original
   * user message. Retrying requeues that job instead of
   * calling sendText() again.
   */
  const [failedJob, setFailedJob] = useState(null);

  const [retryingJobId, setRetryingJobId] = useState(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [compactHistory, setCompactHistory] = useState(false);
  const historyTrigger = useRef(null);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 900px)");
    const update = () => setCompactHistory(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
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
  const [submitting, setSubmitting] = useState(false);

  const uploadRef = useRef(null);
  const bottomRef = useRef(null);
  const composerInputRef = useRef(null);
  const previewCloseRef = useRef(null);
  const pollRef = useRef(null);

  const sendInFlightRef = useRef(false);

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
  const conversationIdRef = useRef(null);

  const conversationLoadRef = useRef(0);

  function isVisibleConversation(id) {
    return Boolean(id && conversationIdRef.current === id);
  }

  function stopVisiblePolling() {
    if (pollRef.current) {
      clearTimeout(pollRef.current);

      pollRef.current = null;
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
        cache: "no-store",
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

  async function loadConversation(id, closeHistory = true, recoverJob = true) {
    if (!id) return;

    /*
     * Selecting another conversation immediately detaches the
     * previous conversation's visible runtime state.
     */
    const loadToken = conversationLoadRef.current + 1;

    conversationLoadRef.current = loadToken;

    if (conversationIdRef.current !== id) {
      setConversationTitle(null);
    }
    conversationIdRef.current = id;

    setConversationId(id);

    stopVisiblePolling();

    setActiveJob(null);
    setFailedJob(null);
    setRetryingJobId(null);
    setError(null);
    setNotice(null);

    const [response, attachmentResponse] = await Promise.all([
      fetch(`/api/conversations/${id}`, {
        cache: "no-store",
      }),

      fetch(`/api/chat/attachments?conversationId=${encodeURIComponent(id)}`, {
        cache: "no-store",
      }),
    ]);

    /*
     * Ignore a late response from a conversation that the user
     * has already left.
     */
    if (
      !isVisibleConversation(id) ||
      conversationLoadRef.current !== loadToken
    ) {
      return;
    }

    const data = await response.json();

    if (!response.ok) {
      setMessages([]);

      setError(data.error || "Could not load the conversation.");

      return;
    }

    let attachmentData = {
      attachments: [],
    };

    if (attachmentResponse.ok) {
      try {
        attachmentData = await attachmentResponse.json();
      } catch {
        //
      }
    }

    if (
      !isVisibleConversation(id) ||
      conversationLoadRef.current !== loadToken
    ) {
      return;
    }

    const byMessage = new Map();

    for (const attachment of attachmentData.attachments || []) {
      if (!attachment.messageId) {
        continue;
      }

      const current = byMessage.get(attachment.messageId) || [];

      current.push(attachment);

      byMessage.set(attachment.messageId, current);
    }

    const hydratedMessages = (data.messages || []).map((message) => ({
      ...message,

      attachments: byMessage.get(message.id) || message.attachments || [],
    }));

    localStorage.setItem(`vector.activeConversation:${userId}`, id);

    setConversationTitle(data.conversation?.title);
    setMessages(normaliseMessages(hydratedMessages));

    if (closeHistory) {
      setHistoryOpen(false);
    }

    if (recoverJob && isVisibleConversation(id)) {
      await recoverConversationJob(id);
    }
  }

  async function recoverConversationJob(id) {
    if (!isVisibleConversation(id)) {
      return false;
    }

    setActiveJob(null);
    setFailedJob(null);

    try {
      const response = await fetch(
        `/api/jobs?conversationId=${encodeURIComponent(id)}`,
        {
          cache: "no-store",
        },
      );

      if (!response.ok || !isVisibleConversation(id)) {
        return false;
      }

      const data = await response.json();

      if (!isVisibleConversation(id)) {
        return false;
      }

      const job = data.jobs?.[0];

      if (!job) {
        return false;
      }

      if (job.status === "queued" || job.status === "running") {
        setActiveJob({
          ...job,
          conversationId: id,
        });

        pollJob(job.id, id);

        return true;
      }

      if (job.status === "completed") {
        const detail = await fetch(`/api/jobs/${job.id}`, {
          cache: "no-store",
        });

        if (detail.ok && isVisibleConversation(id)) {
          await loadConversation(id, false, false);
        }

        return false;
      }

      if (job.status === "failed") {
        setError(null);

        setFailedJob({
          ...job,
          conversationId: id,
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
    const id = conversationIdRef.current;

    if (!id) {
      return false;
    }

    await recoverConversationJob(id);

    return true;
  }

  /*
   * VECTOR_CHAT_STORAGE_SCOPE_5641
   *
   * localStorage belongs to the browser origin, not to a Vector account.
   * Remove the pre-isolation global key once and keep the active chat
   * namespaced by the authenticated user ID.
   */
  useEffect(() => {
    localStorage.removeItem(["vector", "activeConversation"].join("."));
  }, [userId]);

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
      const requested = new URLSearchParams(window.location.search).get(
        "conversation",
      );
      const saved =
        requested ||
        localStorage.getItem(`vector.activeConversation:${userId}`);

      if (saved && list.some((conversation) => conversation.id === saved)) {
        await loadConversation(saved, false);
      } else if (saved) {
        localStorage.removeItem(`vector.activeConversation:${userId}`);
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
        behavior:
          activeJob &&
          !window.matchMedia("(prefers-reduced-motion: reduce)").matches &&
          document.querySelector(".vector-shell")?.dataset.motion !== "reduced"
            ? "smooth"
            : "auto",
      });
    });
  }, [messages, activeJob, error, notice]);

  async function pollJob(jobId, targetConversationId) {
    /*
     * Only one poll belongs to the visible workspace.
     * Leaving the conversation detaches this poll; the actual
     * background job continues on the server.
     */
    if (!isVisibleConversation(targetConversationId)) {
      return;
    }

    stopVisiblePolling();

    try {
      const response = await fetch(`/api/jobs/${jobId}`, {
        cache: "no-store",
      });

      if (!isVisibleConversation(targetConversationId)) {
        return;
      }

      if (!response.ok) {
        throw new Error("job poll failed");
      }

      const job = await response.json();

      if (!isVisibleConversation(targetConversationId)) {
        return;
      }

      if (job.status === "queued" || job.status === "running") {
        setFailedJob(null);

        setActiveJob({
          ...job,
          conversationId: targetConversationId,
        });

        pollRef.current = setTimeout(() => {
          if (isVisibleConversation(targetConversationId)) {
            pollJob(jobId, targetConversationId);
          }
        }, 900);

        return;
      }

      setActiveJob(null);

      if (job.status === "completed") {
        if (isVisibleConversation(targetConversationId)) {
          await loadConversation(targetConversationId, false, false);
        }

        await loadConversations(search);

        return;
      }

      if (job.status === "cancelled") {
        if (isVisibleConversation(targetConversationId)) {
          setNotice("Generation stopped");

          await loadConversation(targetConversationId, false, false);
        }

        return;
      }

      if (isVisibleConversation(targetConversationId)) {
        setError(null);

        setFailedJob({
          ...job,
          conversationId: targetConversationId,
        });
      }
    } catch {
      if (isVisibleConversation(targetConversationId)) {
        pollRef.current = setTimeout(() => {
          if (isVisibleConversation(targetConversationId)) {
            pollJob(jobId, targetConversationId);
          }
        }, 1800);
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
    conversationLoadRef.current += 1;

    conversationIdRef.current = null;

    stopVisiblePolling();

    setConversationId(null);
    setConversationTitle(null);
    setActiveJob(null);
    setFailedJob(null);
    setRetryingJobId(null);

    localStorage.removeItem(`vector.activeConversation:${userId}`);

    setMessages([]);
    setInput("");
    setError(null);
    setNotice(null);
    setHistoryOpen(false);
    setAttachments([]);
  }

  async function deleteConversation(id) {
    await fetch(`/api/conversations/${id}`, {
      method: "DELETE",
    });

    if (conversationId === id) {
      newConversation();
    }

    await loadConversations(search);
  }

  async function removePendingAttachment(attachment) {
    if (!attachment?.id) {
      return;
    }

    const response = await fetch(`/api/chat/attachments/${attachment.id}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));

      setError(data.error || "Could not remove attachment.");

      return;
    }

    setAttachments((current) =>
      current.filter((item) => item.id !== attachment.id),
    );
  }

  async function chooseFiles(files) {
    const remaining = Math.max(0, 6 - attachments.length);

    const chosen = Array.from(files || []).slice(0, remaining);

    if (chosen.length === 0) {
      if (files?.length && remaining === 0) {
        setError("A maximum of 6 attachments can be added to one message.");
      }

      return;
    }

    setError(null);

    setNotice(
      chosen.length === 1
        ? "Uploading file…"
        : `Uploading ${chosen.length} files…`,
    );

    const uploaded = [];

    for (const file of chosen) {
      const formData = new FormData();

      formData.append("file", file);

      try {
        const response = await fetch("/api/chat/attachments", {
          method: "POST",

          body: formData,
        });

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.error || "Upload failed");
        }

        uploaded.push(data.attachment);
      } catch (error) {
        setError(`${file.name}: ${error.message || "upload failed"}`);
      }
    }

    if (uploaded.length > 0) {
      setAttachments((current) => [...current, ...uploaded].slice(0, 6));
    }

    setNotice(null);

    if (uploadRef.current) {
      uploadRef.current.value = "";
    }
  }

  async function sendText(textValue) {
    const typedText = String(textValue || "").trim();

    const text =
      typedText ||
      (attachments.length ? "Please analyze the attached file(s)." : "");

    if (!text || activeJob || sendInFlightRef.current) {
      return;
    }

    /*
     * A previous completed-job refresh may still be fetching the old
     * conversation snapshot. Invalidate that load before adding the new
     * optimistic user message so it can never overwrite this submission.
     */
    conversationLoadRef.current += 1;

    sendInFlightRef.current = true;

    const sendVersion = conversationLoadRef.current;

    setSubmitting(true);

    const tempId = `temp-${Date.now()}`;

    const attachmentSnapshot = [...attachments];

    setInput("");
    setError(null);
    setNotice(null);
    setFailedJob(null);
    setRetryingJobId(null);

    setMessages((current) => [
      ...current,

      {
        id: tempId,

        role: "user",

        content: text,

        attachments: attachmentSnapshot,
      },
    ]);

    try {
      const response = await privacySend("/api/chat", {
        brainEnabled,
        message: text,
        conversationId: conversationIdRef.current || conversationId,
        mode,
        privacyEnabled,
        skillIds: selectedSkillIds,
        skillParameters: Object.fromEntries(
          selectedSkillIds
            .filter((id) => skillParameters[id])
            .map((id) => [id, skillParameters[id]]),
        ),
        billingPolicy: freeOnly ? "free-only" : "standard",
        attachmentIds: attachmentSnapshot.map((attachment) => attachment.id),
      });

      const data = await response.json();

      if (sendVersion !== conversationLoadRef.current) return;
      if (!response.ok) {
        setInput(text);
        setMessages((current) =>
          current.filter((message) => message.id !== tempId),
        );

        if (data.privacyCancelled) return;
        setError(
          data.message ||
            data.reason ||
            data.error ||
            "Vector could not start the request.",
        );

        return;
      }

      setAttachments([]);

      const id = data.conversationId;
      const isNewConversation = !conversationIdRef.current;

      conversationLoadRef.current += 1;

      conversationIdRef.current = id;

      setConversationId(id);

      if (isNewConversation) {
        fetch(`/api/conversations/${encodeURIComponent(id)}`, { cache: "no-store" })
          .then((response) => response.ok ? response.json() : null)
          .then((result) => {
            if (isVisibleConversation(id) && result) {
              setConversationTitle(result.conversation?.title);
            }
          })
          .catch(() => {});
      }

      localStorage.setItem(`vector.activeConversation:${userId}`, id);

      setMessages((current) =>
        current.map((message) =>
          message.id === tempId
            ? {
                ...message,
                privacy_summary: data.userMessage?.privacy,

                id: data.userMessage?.id || tempId,

                attachments: attachmentSnapshot,
              }
            : message,
        ),
      );

      await loadConversations(search);

      if (data.jobId) {
        const job = {
          id: data.jobId,

          conversationId: id,

          status: "queued",

          progress: data.progress,
        };

        setActiveJob(job);

        pollJob(data.jobId, id);

        return;
      }

      if (data.message) {
        setMessages((current) => [
          ...current,

          {
            id: data.message.id,

            role: "assistant",

            content: safeAssistantText(data.message.content),

            meta: data.meta,
          },
        ]);
      }
    } catch {
      setNotice("Connection interrupted. Vector continues in the background.");

      const recovered = await recoverVisibleConversationJob();

      if (recovered) {
        setAttachments([]);
      }
    } finally {
      sendInFlightRef.current = false;

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
      method: "DELETE",
    });

    if (pollRef.current) {
      clearTimeout(pollRef.current);
    }

    setActiveJob(null);
    setNotice("Generation stopped");
  }

  async function retryFailedJob() {
    if (!failedJob?.id || activeJob || retryingJobId) {
      return;
    }

    const failed = failedJob;

    setRetryingJobId(failed.id);

    setError(null);
    setNotice(null);

    try {
      const response = await fetch(`/api/jobs/${failed.id}`, {
        method: "POST",
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(
          data.message || data.error || "Vector could not retry the request.",
        );

        return;
      }

      const targetConversationId =
        data.conversationId ||
        failed.conversationId ||
        conversationIdRef.current ||
        conversationId;

      const retriedJob = {
        id: data.id || failed.id,

        conversationId: targetConversationId,

        status: data.status || "queued",

        attempts: data.attempts,

        progress: data.progress || {
          stage: "queued",

          message: "Retrying previous request",
        },
      };

      if (isVisibleConversation(targetConversationId)) {
        setFailedJob(null);

        setActiveJob(retriedJob);

        pollJob(retriedJob.id, targetConversationId);
      }
    } catch {
      setError("Vector could not start the retry.");
    } finally {
      setRetryingJobId(null);
    }
  }

  useEffect(() => {
    if (!previewImage) return;
    const previouslyFocused = document.activeElement;
    previewCloseRef.current?.focus();
    const onEscape = (event) => {
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

  const currentTitle = conversationLabel(conversationTitle);
  const historyPanel = (
    <aside
      id="vector-chat-history"
      className={"vc-history" + (historyOpen ? " is-open" : "")}
    >
      <header>
        <Dialog.Title asChild>
          <h2>Conversations</h2>
        </Dialog.Title>
        <button
          type="button"
          className="vc-icon-button"
          onClick={newConversation}
          aria-label="New conversation"
          title="New conversation"
        >
          <Plus size={18} />
        </button>
      </header>
      <label className="vc-history-search">
        <Search size={15} />
        <input
          type="search"
          aria-label="Search conversations"
          placeholder="Search conversations"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </label>
      <nav className="vc-history-list" aria-label="Conversation history">
        {conversationGroups(conversations).map((group) => (
          <section key={group.label}>
            <h3>{group.label}</h3>
            {group.items.map((conversation) => (
              <div
                className={
                  "vc-history-item" +
                  (conversation.id === conversationId ? " is-current" : "")
                }
                key={conversation.id}
              >
                <button
                  type="button"
                  className="vc-history-open"
                  aria-current={
                    conversation.id === conversationId ? "page" : undefined
                  }
                  onClick={() => loadConversation(conversation.id)}
                >
                  <span>{conversationLabel(conversation.title)}</span>
                  <small>
                    {shortText(conversationLabel(conversation.preview, ""))}
                  </small>
                </button>
                <button
                  type="button"
                  className="vc-icon-button vc-history-delete"
                  aria-label={`Delete ${conversationLabel(conversation.title)}`}
                  onClick={() => deleteConversation(conversation.id)}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </section>
        ))}
        {conversations.length === 0 && (
          <p className="vc-history-empty">
            {search
              ? "No conversations match your search."
              : "Your conversations will appear here."}
          </p>
        )}
      </nav>
    </aside>
  );
  return (
    <Dialog.Root
      open={compactHistory && historyOpen}
      onOpenChange={setHistoryOpen}
    >
      <div
        className={`vc-workspace ${historyCollapsed ? "is-history-collapsed" : ""}`}
      >
        {compactHistory ? (
          <Dialog.Portal>
            <Dialog.Overlay className="vc-history-backdrop" />
            <Dialog.Content
              asChild
              aria-describedby={undefined}
              onCloseAutoFocus={(event) => {
                event.preventDefault();
                historyTrigger.current?.focus();
              }}
            >
              {historyPanel}
            </Dialog.Content>
          </Dialog.Portal>
        ) : (
          historyPanel
        )}
        <section className="vc-thread" aria-label="Chat workspace">
          <header className="vc-thread-header">
            <button
              type="button"
              className="vc-icon-button"
              aria-label="Toggle conversation history"
              title="Toggle conversation history"
              aria-controls="vector-chat-history"
              ref={historyTrigger}
              aria-expanded={compactHistory ? historyOpen : !historyCollapsed}
              onClick={() => {
                if (compactHistory) setHistoryOpen((value) => !value);
                else setHistoryCollapsed((value) => !value);
              }}
            >
              <PanelLeft size={18} />
            </button>
            <h1 title={currentTitle}>{currentTitle}</h1>
            <div className="vc-thread-tools">
              {!privacyEnabled && (
                <span className="vc-privacy-off">
                  <ShieldOff size={13} />
                  Privacy off
                </span>
              )}
              <span
                className="vc-conversation-cost"
                title="Current conversation cost"
              >
                {formatMoney(currentConversationSpend)}
              </span>
              <ConversationSettings
                privacyEnabled={privacyEnabled}
                onPrivacyChange={setPrivacyEnabled}
                brainEnabled={brainEnabled}
                onBrainChange={setBrainEnabled}
                freeOnly={freeOnly}
                onFreeOnlyChange={setFreeOnly}
                selectedSkills={selectedSkillIds}
                onSkillsChange={setSelectedSkillIds}
                parameters={skillParameters}
                onParameters={setSkillParameters}
                disabled={submitting || Boolean(activeJob)}
              />
            </div>
          </header>
          {notice && (
            <div className="vc-notice" role="status">
              {notice}
            </div>
          )}
          <div className="vc-scroll-region" role="log" aria-label="Conversation messages" aria-live="polite">
            <div
              className={
                "vc-messages" +
                (!messages.length && !activeJob ? " is-empty" : "")
              }
            >
              {messages.length === 0 && !activeJob && (
                <div className="vc-welcome">
                  <img src="/vector-assets/brand/vector-mark.svg" alt="" />
                  <h2>What are we working on?</h2>
                  <p>Ask a question or bring a file.</p>
                </div>
              )}
              {messages.map((message, index) => (
                <article
                  key={message.id}
                  className={"vc-message " + message.role}
                  aria-label={
                    message.role === "assistant"
                      ? "Vector response"
                      : "Your message"
                  }
                >
                  {message.role === "assistant" && (
                    <div className="vc-assistant-identity">
                      <img src="/vector-assets/brand/vector-mark.svg" alt="" />
                      <span>Vector</span>
                    </div>
                  )}
                  <div className="vc-message-content">
                    {message.role === "assistant" ? (
                      <Markdown>{message.content}</Markdown>
                    ) : (
                      <div className="vc-user-text">{message.content}</div>
                    )}
                  </div>
                  {message.role === "user" && (
                    <PrivacyReceipt receipt={message.privacy_summary} />
                  )}
                  {message.attachments?.length > 0 && (
                    <div className="vc-message-files">
                      {message.attachments.map((attachment, fileIndex) => (
                        <VectorChatArtifact
                          key={attachment?.id || attachment?.name || fileIndex}
                          attachment={attachment}
                          onPreview={setPreviewImage}
                        />
                      ))}
                    </div>
                  )}
                  <footer className="vc-message-footer">
                    {message.role === "assistant" && (
                      <div className="vc-message-meta">
                        {message.meta?.model && (
                          <span>{message.meta.model}</span>
                        )}
                        <span>
                          {callCostLabel(
                            message.meta?.costChf,
                            message.meta?.costStatus,
                          )}
                        </span>
                      </div>
                    )}
                    <div className="vc-message-actions">
                      <IconButton
                        label={
                          copiedId === message.id ? "Copied" : "Copy message"
                        }
                        onClick={() => copyMessage(message.id, message.content)}
                      />
                      {message.role === "assistant" && (
                        <IconButton
                          label="Try again"
                          onClick={() => tryAgain(index)}
                          disabled={Boolean(activeJob) || submitting}
                        />
                      )}
                    </div>
                  </footer>
                </article>
              ))}
              {failedJob && !activeJob && (
                <div className="vc-run-error" role="alert">
                  <p>
                    {failedJob.error || "The request could not be completed."}
                  </p>
                  <button
                    type="button"
                    className="vc-text-button"
                    onClick={retryFailedJob}
                    disabled={Boolean(activeJob || retryingJobId)}
                  >
                    <RefreshCw size={14} />
                    {retryingJobId === failedJob.id
                      ? "Retrying…"
                      : "Retry request"}
                  </button>
                </div>
              )}
              {activeJob && (
                <div className="vc-run-progress" role="status">
                  <span className="vc-working-dot" />
                  <span>{activeJob?.progress?.message || "Working…"}</span>
                </div>
              )}
              {error && (
                <div className="vc-run-error" role="alert">
                  {error}
                </div>
              )}
              <div ref={bottomRef} />
            </div>
          </div>
          <form
            className={"vc-composer" + (dragActive ? " is-dragging" : "")}
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
              if (!event.currentTarget.contains(event.relatedTarget))
                setDragActive(false);
            }}
            onDrop={async (event) => {
              event.preventDefault();
              event.stopPropagation();
              setDragActive(false);
              const dropped = Array.from(event.dataTransfer?.files || []);
              if (dropped.length) await chooseFiles(dropped);
            }}
          >
            {dragActive && (
              <div className="vc-drop-overlay">Drop files to attach them</div>
            )}
            {privacyDialog}
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
            <PromptInput
              value={input}
              onValueChange={setInput}
              textareaRef={composerInputRef}
              blocked={Boolean(activeJob) || submitting}
              attachments={
                attachments.length > 0 && (
                  <div className="vc-pending-files">
                    {attachments.map((file) => (
                      <button
                        key={file.id}
                        type="button"
                        onClick={() => removePendingAttachment(file)}
                        aria-label={`Remove ${file.name}`}
                      >
                        <FileText size={14} />
                        <span>{file.name}</span>
                        <X size={13} />
                      </button>
                    ))}
                  </div>
                )
              }
            >
              <div className="vc-composer-tools">
                <button
                  type="button"
                  className="vc-icon-button"
                  onClick={() => uploadRef.current?.click()}
                  disabled={Boolean(notice?.startsWith("Uploading"))}
                  aria-label={
                    notice?.startsWith("Uploading")
                      ? "Uploading files"
                      : "Attach files"
                  }
                  title="Attach files"
                >
                  {notice?.startsWith("Uploading") ? (
                    <LoaderCircle size={18} className="vc-spin" />
                  ) : (
                    <Plus size={20} />
                  )}
                </button>
                <label className="vc-mode">
                  <select
                    aria-label="Response mode"
                    value={mode}
                    onChange={(event) => setMode(event.target.value)}
                    disabled={submitting || Boolean(activeJob)}
                  >
                    {CHAT_MODES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.value === "local" ? "Local" : option.label}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={13} />
                </label>
              </div>
              {activeJob ? (
                <button
                  type="button"
                  className="vc-send"
                  aria-label="Stop generation"
                  onClick={stopGeneration}
                >
                  <Square size={14} fill="currentColor" />
                </button>
              ) : (
                <button
                  type="submit"
                  className="vc-send"
                  aria-label="Send message"
                  disabled={
                    submitting ||
                    (input.trim() === "" && attachments.length === 0)
                  }
                >
                  {submitting ? (
                    <LoaderCircle size={17} className="vc-spin" />
                  ) : (
                    <ArrowUp size={19} />
                  )}
                </button>
              )}
            </PromptInput>
          </form>
          {previewImage && (
            <div
              className="vx585-preview-overlay"
              role="presentation"
              onMouseDown={(event) => {
                if (event.target === event.currentTarget) setPreviewImage(null);
              }}
            >
              <div
                className="vx585-preview-panel"
                role="dialog"
                aria-modal="true"
                aria-label={`Image preview: ${previewImage.name}`}
              >
                <div className="vx585-preview-header">
                  <strong>{previewImage.name}</strong>
                  <button
                    ref={previewCloseRef}
                    type="button"
                    onClick={() => setPreviewImage(null)}
                    aria-label="Close image preview"
                  >
                    <X size={20} aria-hidden="true" />
                  </button>
                </div>
                <img src={previewImage.url} alt={previewImage.name} />
                <a
                  href={previewImage.url}
                  download={previewImage.name}
                  target="_blank"
                  rel="noreferrer"
                >
                  Download image
                </a>
              </div>
            </div>
          )}
        </section>
      </div>
    </Dialog.Root>
  );
}
