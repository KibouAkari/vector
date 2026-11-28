"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Menu,
  Search,
  Bell,
  Settings2,
  X,
  ArrowUpRight,
  LayoutDashboard,
  MessageSquare,
  FolderKanban,
  Workflow,
  BrainCircuit,
  BookOpen,
  Server,
  Cable,
  Globe2,
  ShieldCheck,
  CheckCheck,
  ScrollText,
  SlidersHorizontal,
  ChartNoAxesCombined,
  UsersRound,
  Fingerprint,
} from "lucide-react";
const Icons = {
  Menu,
  Search,
  Bell,
  Settings2,
  X,
  ArrowUpRight,
  LayoutDashboard,
  MessageSquare,
  FolderKanban,
  Workflow,
  BrainCircuit,
  BookOpen,
  Server,
  Cable,
  Globe2,
  ShieldCheck,
  CheckCheck,
  ScrollText,
  SlidersHorizontal,
  ChartNoAxesCombined,
  UsersRound,
  Fingerprint,
};
import { AnimatePresence, motion } from "motion/react";
import {useInterfaceMotion} from "./operations/use-interface-motion";
import { navigationFor, pageTitle } from "../lib/operations-navigation.mjs";
import SpaceBackdrop from "./operations/space-backdrop";
import LogoutButton from "./logout-button";
import VectorSoundButton from "./ui/vector-sound-button";
const defaults = {
  accent: "ice",
  density: "comfortable",
  ambient: true,
  motion: true,
};
export default function Sidebar({ session }) {
  const path = usePathname(),
    router = useRouter(),
    reduced = useInterfaceMotion();
  const groups = navigationFor(session);
  const [open, setOpen] = useState(false),
    [command, setCommand] = useState(false),
    [query, setQuery] = useState(""),
    [settings, setSettings] = useState(false),
    [pending, setPending] = useState(0),
    [prefs, setPrefs] = useState(defaults);
  const dialog = useRef(null),
    nav = useRef(null),
    search = useRef(null),
    previous = useRef(null);
  const key = "vector:interface:" + session.userId;
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(key) || "{}");
      setPrefs({
        ...defaults,
        ...stored,
        accent: ["teal", "ice", "sand"].includes(stored.accent)
          ? stored.accent
          : "ice",
        density: stored.density === "compact" ? "compact" : "comfortable",
      });
    } catch {}
  }, [key]);
  useEffect(() => {
    const shell = document.querySelector(".vector-shell");
    if (shell) {
      shell.dataset.accent = prefs.accent;
      shell.dataset.density = prefs.density;
      shell.dataset.motion = window.matchMedia("(prefers-reduced-motion: reduce)").matches || !prefs.motion ? "reduced" : "full";
      shell.dataset.ambient = String(prefs.ambient);
      window.dispatchEvent(new Event("vector:interface-change"));
    }
  }, [prefs, reduced, path]);
  useEffect(() => {
    function keyboard(event) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommand((value) => !value);
      }
      if (event.key === "Escape") {
        setCommand(false);
        setSettings(false);
        setOpen(false);
      }
    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, []);
  useEffect(() => {
    if (session.role !== "owner") return;
    const controller = new AbortController();
    const refresh = () => {
      if (!document.hidden)
        fetch("/api/approvals?summary=1", {
          cache: "no-store",
          signal: controller.signal,
        })
          .then((response) => (response.ok ? response.json() : null))
          .then((data) => {
            if (data && !controller.signal.aborted)
              setPending(data.pendingCount);
          })
          .catch(() => {});
    };
    refresh();
    const timer = setInterval(refresh, 15000);
    window.addEventListener("vector:approvals", refresh);
    return () => {
      controller.abort();
      clearInterval(timer);
      window.removeEventListener("vector:approvals", refresh);
    };
  }, [session.role]);
  useEffect(() => {
    const surface = command ? dialog.current : open ? nav.current : null;
    if (!surface) return;
    previous.current = document.activeElement;
    const mains = [...document.querySelectorAll("main")],
      states = mains.map((main) => main.inert);
    mains.forEach((main) => (main.inert = true));
    (command ? search.current : surface.querySelector("a,button"))?.focus();
    function trap(event) {
      if (event.key !== "Tab") return;
      const targets = [
        ...surface.querySelectorAll("a,button,input,select"),
      ].filter((node) => !node.disabled && node.getClientRects().length);
      if (!targets.length) return;
      if (event.shiftKey && document.activeElement === targets[0]) {
        event.preventDefault();
        targets.at(-1).focus();
      } else if (!event.shiftKey && document.activeElement === targets.at(-1)) {
        event.preventDefault();
        targets[0].focus();
      }
    }
    document.addEventListener("keydown", trap);
    return () => {
      mains.forEach((main, index) => (main.inert = states[index]));
      document.removeEventListener("keydown", trap);
      previous.current?.focus?.();
    };
  }, [open, command]);
  const navigate = (href) => {
    setOpen(false);
    setCommand(false);
    setQuery("");
    router.push(href);
  };
  const setPreference = (name, value) =>
    setPrefs((old) => {
      const next = { ...old, [name]: value };
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {}
      return next;
    });
  const options = groups
    .flatMap((group) =>
      group.items.map((item) => ({ ...item, group: group.label })),
    )
    .filter((item) =>
      (item.label + " " + item.group)
        .toLowerCase()
        .includes(query.toLowerCase()),
    );
  return (
    <>
      <SpaceBackdrop/>
      <a
        className="op-skip"
        href="#vector-main"
        onClick={(event) => {
          event.preventDefault();
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
      <header className="op-topbar">
        <div className="op-brand">
          <button
            className="op-icon op-menu-toggle"
            aria-label="Open navigation"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
          >
            <Icons.Menu size={18} />
          </button>
          <Link href="/" aria-label="Vector home">
            <img src="/vector-assets/brand/vector-mark.svg" alt="" />
            <strong>Vector</strong>
          </Link>
          <span className="op-top-divider" />
          <span className="op-location">{pageTitle(path)}</span>
        </div>
        <div className="op-top-actions">
          <button
            aria-label="Go anywhere"
          className="op-command-trigger"
            onClick={() => setCommand(true)}
          >
            <Icons.Search size={15} />
            <span>Go anywhere</span>
            <kbd>⌘ K</kbd>
          </button>
          <Link
            className="op-icon"
            href="/approvals"
            aria-label={`${pending} pending approvals`}
            hidden={session.role !== "owner"}
          >
            <Icons.Bell size={17} />
            {pending > 0 && <i>{pending}</i>}
          </Link>
          <button
            className="op-icon"
            aria-label="Interface settings"
            aria-expanded={settings}
            onClick={() => setSettings(!settings)}
          >
            <Icons.Settings2 size={17} />
          </button>
          <span
            className="op-avatar"
            title={session.displayName || session.username}
          >
            {(session.displayName || session.username || "V")
              .slice(0, 2)
              .toUpperCase()}
          </span>
        </div>
        {settings && (
          <div className="op-preferences">
            <div className="op-panel-heading">
              <strong>Make it yours</strong>
              <button
                className="op-icon"
                aria-label="Close settings"
                onClick={() => setSettings(false)}
              >
                <Icons.X size={16} />
              </button>
            </div>
            <label>
              Accent
              <select
                value={prefs.accent}
                onChange={(event) =>
                  setPreference("accent", event.target.value)
                }
              >
                <option value="teal">Glacier</option>
                <option value="ice">Silver</option>
                <option value="sand">Warm light</option>
              </select>
            </label>
            <label>
              Density
              <select
                value={prefs.density}
                onChange={(event) =>
                  setPreference("density", event.target.value)
                }
              >
                <option value="comfortable">Comfortable</option>
                <option value="compact">Compact</option>
              </select>
            </label>
            <label className="op-toggle">
              Ambient light
              <input
                type="checkbox"
                checked={prefs.ambient}
                onChange={(event) =>
                  setPreference("ambient", event.target.checked)
                }
              />
            </label>
            <label className="op-toggle">
              Animations
              <input
                type="checkbox"
                checked={prefs.motion}
                onChange={(event) =>
                  setPreference("motion", event.target.checked)
                }
              />
            </label>
            <small>
              Motion follows your device’s accessibility preference.
            </small>
          </div>
        )}
      </header>
      {open && (
        <button
          className="op-nav-backdrop"
          aria-label="Close navigation"
          onClick={() => setOpen(false)}
        />
      )}
      <aside
        className={`op-sidebar${open ? " is-open" : ""}`}
        ref={nav}
        role={open ? "dialog" : undefined}
        aria-modal={open || undefined}
        aria-label="Workspace navigation"
      >
        <nav aria-label="Main navigation">
          {groups.map((group) => (
            <section key={group.label}>
              <h2>{group.label}</h2>
              {group.items.map((item) => {
                const Icon = Icons[item.icon];
                const active =
                  item.href === "/"
                    ? path === "/"
                    : path === item.href || path.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={active ? "is-active" : ""}
                    onClick={() => setOpen(false)}
                  >
                    {active && (
                      <motion.span
                        className="op-nav-selection"
                        layoutId="nav-selection"
                        transition={{ duration: reduced ? 0 : 0.2 }}
                      />
                    )}
                    <Icon size={17} strokeWidth={1.7} />
                    <span>{item.label}</span>
                    {item.href === "/approvals" && pending > 0 && (
                      <b>{pending}</b>
                    )}
                  </Link>
                );
              })}
            </section>
          ))}
        </nav>
        <footer>
          <div className="op-account">
            <span className="op-status-dot" />
            <div>
              <strong>{session.displayName || session.username}</strong>
              <small>
                {session.role === "readonly" ? "Read only" : session.role}
              </small>
            </div>
            <VectorSoundButton />
          </div>
          <LogoutButton />
        </footer>
      </aside>
      <AnimatePresence>
        {command && (
          <motion.div
            className="op-command-shade"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setCommand(false)}
          >
            <motion.section
              className="op-command"
              role="dialog"
              aria-modal="true"
              aria-label="Go anywhere"
              ref={dialog}
              initial={{
                opacity: 0,
                y: reduced ? 0 : 12,
                scale: reduced ? 1 : 0.98,
              }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: reduced ? 0 : 8 }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="op-command-input">
                <Icons.Search size={20} />
                <input
                  ref={search}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search pages and actions…"
                  aria-label="Search navigation"
                  autoComplete="off"
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && options[0])
                      navigate(options[0].href);
                  }}
                />
                <kbd>esc</kbd>
              </div>
              <div className="op-command-results">
                {options.map((item) => {
                  const Icon = Icons[item.icon];
                  return (
                    <button key={item.href} onClick={() => navigate(item.href)}>
                      <Icon size={18} />
                      <span>
                        {item.label}
                        <small>{item.group}</small>
                      </span>
                      <Icons.ArrowUpRight size={15} />
                    </button>
                  );
                })}
                {!options.length && <p>No matching page.</p>}
              </div>
              <footer>Navigate with Tab · Open with Enter</footer>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
