"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BookOpen,
  CheckCheck,
  Coins,
  FolderKanban,
  LayoutDashboard,
  Menu,
  MessageSquareText,
  Server,
  Shield,
  SlidersHorizontal,
  Users,
  X,
} from "lucide-react";
import LogoutButton from "./logout-button";
import VectorSoundButton from "./ui/vector-sound-button";
const WORK = [
  ["/", "Dashboard", null, LayoutDashboard],
  ["/chat", "Chat", "chat", MessageSquareText],
  ["/projects", "Projects", "projects", FolderKanban],
  ["/skills", "Skills", "projects", BookOpen],
];
const CONTROL = [
  ["/security", "Security Scanner", "operator", Shield],
  ["/approvals", "Approvals", "owner", CheckCheck],
  ["/models", "Models & API Keys", "models", SlidersHorizontal],
  ["/usage", "Usage & Budgets", null, Coins],
  ["/users", "Users & Policies", "owner", Users],
];
export default function Sidebar({ session }) {
  const pathname = usePathname(),
    [open, setOpen] = useState(false),
    [pending, setPending] = useState(null),
    nav = useRef(null),
    trigger = useRef(null);
  useEffect(() => {
    if (session.role !== "owner") return;
    let stopped = false;
    const controller = new AbortController();
    async function refresh() {
      if (document.hidden) return;
      try {
        const response = await fetch("/api/approvals?summary=1", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (response.ok) {
          const data = await response.json();
          if (!stopped) setPending(data.pendingCount);
        }
      } catch {}
    }
    refresh();
    const timer = setInterval(refresh, 15000);
    window.addEventListener("vector:approvals", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      stopped = true;
      controller.abort();
      clearInterval(timer);
      window.removeEventListener("vector:approvals", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [session.role]);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const mains = [...document.querySelectorAll("main")];
    const states = mains.map((el) => el.inert);
    mains.forEach((el) => (el.inert = true));
    nav.current?.querySelector("a")?.focus();
    function keyboard(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        setOpen(false);
      }
      if (e.key === "Tab") {
        const targets = [...nav.current.querySelectorAll("a,button")];
        const first = targets[0],
          last = targets.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", keyboard);
    return () => {
      mains.forEach((el, i) => (el.inert = states[i]));
      document.removeEventListener("keydown", keyboard);
      previous?.focus?.();
    };
  }, [open]);
  const allowed = (feature) =>
    !feature ||
    session.role === "owner" ||
    (feature === "operator"
      ? session.role === "admin"
      : feature !== "owner" && session.features?.[feature]);
  const links = (items) =>
    items
      .filter(([, , feature]) => allowed(feature))
      .map(([href, label, , Icon]) => {
        const active =
          href === "/"
            ? pathname === "/"
            : pathname === href || pathname.startsWith(href + "/");
        return (
          <Link
            key={href}
            href={href}
            className={active ? "active" : ""}
            aria-current={active ? "page" : undefined}
            onClick={() => setOpen(false)}
          >
            <Icon className="vx-nav-icon" aria-hidden="true" />
            <span>{label}</span>
            {href === "/approvals" && pending > 0 && (
              <span
                className="nav-approval-count"
                aria-label={`${pending} pending approvals`}
              >
                {pending}
              </span>
            )}
          </Link>
        );
      });
  return (
    <>
      <a
        className="vector-skip-link"
        href="#vector-main"
        onClick={(event) => {
          event.preventDefault();
          setOpen(false);
          const main = document.querySelector("main");
          if (main) {
            main.id = "vector-main";
            main.tabIndex = -1;
            main.focus();
          }
        }}
      >
        Skip to content
      </a>
      <button
        type="button"
        ref={trigger}
        className="v5-mobile-nav"
        aria-label="Open navigation"
        aria-expanded={open}
        aria-controls="vector-navigation"
        onClick={() => setOpen(true)}
      >
        <Menu size={20} />
      </button>
      {open && (
        <button
          type="button"
          className="v5-nav-shade"
          aria-label="Close navigation"
          tabIndex={-1}
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        id="vector-navigation"
        ref={nav}
        className={`sidebar v5-sidebar${open ? " v5-sidebar-open" : ""}`}
        role={open ? "dialog" : undefined}
        aria-modal={open ? true : undefined}
        aria-label="Workspace navigation"
      >
        <header className="v5-brand">
          <Link href="/" onClick={() => setOpen(false)}>
            <img
              className="v55-sidebar-logo"
              src="/vector-assets/brand/vector-mark.svg"
              alt=""
            />
            <strong>Vector</strong>
          </Link>
          <button
            type="button"
            className="v5-nav-close"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          >
            <X size={20} />
          </button>
        </header>
        <nav className="v5-nav" aria-label="Main navigation">
          {links(WORK)}
          <span className="nav-section-label">Control</span>
          {links(CONTROL)}
          {(session.role === "owner" ||
            session.features?.server ||
            session.features?.activity) && (
            <span className="nav-section-label">Operations</span>
          )}
          {links([
            ["/server", "Infrastructure", "server", Server],
            ["/audit", "Audit log", "activity", Activity],
          ])}
        </nav>
        <footer className="v5-sidebar-footer">
          <div className="v5-account">
            <div className="v5-account-avatar">
              {(session.displayName || session.username)?.[0]?.toUpperCase()}
            </div>
            <div>
              <strong>{session.displayName || session.username}</strong>
              <span>
                {session.role === "readonly" ? "Read only" : session.role}
              </span>
            </div>
          </div>
          <div className="v5-account-actions">
            <VectorSoundButton />
            <LogoutButton />
          </div>
        </footer>
      </aside>
    </>
  );
}
