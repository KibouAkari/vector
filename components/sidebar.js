"use client";


import {
  useState
} from "react";


import Link
  from "next/link";


import {
  usePathname
} from "next/navigation";


import {
  AnimatePresence,
  motion,
  useReducedMotion
} from "motion/react";


import {
  Activity,
  FolderKanban,
  LayoutDashboard,
  Menu,
  MessageSquareText,
  Server,
  SlidersHorizontal,
  Users,
  X
} from "lucide-react";


import LogoutButton
  from "./logout-button";


import VectorSoundButton
  from "./ui/vector-sound-button";


const ITEMS = [
  [
    "/",
    "Overview",
    null,
    LayoutDashboard
  ],

  [
    "/chat",
    "Chat",
    "chat",
    MessageSquareText
  ],

  [
    "/projects",
    "Projects",
    "projects",
    FolderKanban
  ],

  [
    "/server",
    "Server",
    "server",
    Server
  ],

  [
    "/models",
    "Models & APIs",
    "models",
    SlidersHorizontal
  ],

  [
    "/audit",
    "Audit log",
    "activity",
    Activity
  ]
];


const LOCKED_NOTICES = [
  "Oops. This area requires a little more clearance.",
  "Access denied. The secret handshake has not been unlocked.",
  "This door is locked. Your workspace owner has the key.",
  "Nice try, explorer. Ask your admin to unlock this feature.",
  "Restricted area. Even Vector has to respect permissions."
];

export default function Sidebar({
  session
}) {
  const pathname =
    usePathname();


  const reduced =
    useReducedMotion();


  const [
    open,
    setOpen
  ] =
    useState(
      false
    );

  const [lockedNotice, setLockedNotice] = useState("");


  // Optional discovery only. Server routes enforce the real permissions.
  const visible = ITEMS.filter(([, , feature]) =>
    !feature ||
    session.role === "owner" ||
    session.features?.[feature] ||
    session.features?.showLockedNavigation
  );

  function activeFor(
    href
  ) {
    return (
      href === "/"
        ? pathname === "/"
        : pathname.startsWith(
            href
          )
    );
  }


  return (
    <>

      <motion.button
        className="v5-mobile-nav"
        aria-label="Open navigation"
        onClick={
          () =>
            setOpen(
              true
            )
        }
        whileTap={
          reduced
            ? undefined
            : {
                scale:
                  .93
              }
        }
      >
        <Menu
          className="vx-mobile-menu-icon"
          aria-hidden="true"
        />
      </motion.button>


      <AnimatePresence>

        {
          open && (
            <motion.button
              className="v5-nav-shade"
              aria-label="Close navigation"
              onClick={
                () =>
                  setOpen(
                    false
                  )
              }
              initial={
                reduced
                  ? false
                  : {
                      opacity:
                        0
                    }
              }
              animate={{
                opacity:
                  1
              }}
              exit={
                reduced
                  ? undefined
                  : {
                      opacity:
                        0
                    }
              }
              transition={{
                duration:
                  .16
              }}
            />
          )
        }

      </AnimatePresence>


      <aside
        className={
          open
            ? "sidebar v5-sidebar v5-sidebar-open"
            : "sidebar v5-sidebar"
        }
      >

        <header className="v5-brand">

          <Link
            href="/"
            onClick={
              () =>
                setOpen(
                  false
                )
            }
          >

            <motion.img
              className="v55-sidebar-logo"
              src="/vector-assets/brand/vector-mark.svg"
              alt=""
              whileHover={
                reduced
                  ? undefined
                  : {
                      rotate:
                        -3,

                      scale:
                        1.04
                    }
              }
              transition={{
                duration:
                  .16
              }}
            />

            <strong>
              Vector
            </strong>

          </Link>


          <motion.button
            className="v5-nav-close"
            aria-label="Close navigation"
            onClick={
              () =>
                setOpen(
                  false
                )
            }
            whileTap={
              reduced
                ? undefined
                : {
                    scale:
                      .9
                  }
            }
          >
            <X
              className="vx-mobile-close-icon"
              aria-hidden="true"
            />
          </motion.button>

        </header>


        <nav className="v5-nav" aria-label="Main navigation">
          {visible.map(([href, label, feature, Icon]) => {
            const locked = Boolean(
              feature && session.role !== "owner" &&
              !session.features?.[feature]
            );
            const active = !locked && activeFor(href);

            if (locked) {
              return (
                <button
                  key={href}
                  type="button"
                  className="vux-nav-locked"
                  aria-label={label + " – locked"}
                  title={label + " requires permission"}
                  onClick={() => setLockedNotice(
                    LOCKED_NOTICES[Math.floor(Math.random() * LOCKED_NOTICES.length)]
                  )}
                >
                  <Icon className="vx-nav-icon" aria-hidden="true" />
                  <span>{label}</span>
                  <span className="vux-nav-lock" aria-hidden="true">⌁</span>
                </button>
              );
            }

            return (
              <Link
                key={href}
                href={href}
                className={active ? "active" : ""}
                onClick={() => { setOpen(false); setLockedNotice(""); }}
              >
                {active && (
                  <motion.span
                    className="vx-nav-active-rail"
                    layoutId="vector-sidebar-active"
                    transition={{
                      type: "spring", stiffness: 500, damping: 40, mass: .45
                    }}
                  />
                )}
                <Icon className="vx-nav-icon" aria-hidden="true" />
                <span>{label}</span>
              </Link>
            );
          })}
          {lockedNotice && (
            <div className="vux-locked-notice" role="status">
              <p>{lockedNotice}</p>
              <button type="button" onClick={() => setLockedNotice("")}
                aria-label="Dismiss locked navigation notice">×</button>
            </div>
          )}
        </nav>


        {
          session.role ===
          "owner" && (
            <div className="v52-owner-nav">

              <span>
                Owner
              </span>

              <Link
                href="/users"
                className={
                  pathname.startsWith(
                    "/users"
                  )
                    ? "active"
                    : ""
                }
              >

                {
                  pathname.startsWith(
                    "/users"
                  ) && (
                    <motion.span
                      className="vx-nav-active-rail"
                      layoutId="vector-sidebar-active"
                    />
                  )
                }

                <Users
                  className="vx-nav-icon"
                  aria-hidden="true"
                />

                <span>
                  Users
                </span>

              </Link>

            </div>
          )
        }


        <footer className="v5-sidebar-footer">

          <div className="v5-account">

            <div className="v5-account-avatar">
              {
                (
                  session.displayName ||
                  session.username
                )[0]
                  ?.toUpperCase()
              }
            </div>

            <div>

              <strong>
                {
                  session.displayName ||
                  session.username
                }
              </strong>

              <span>
                {
                  session.role ===
                  "owner"
                    ? "Owner"
                    : "Vector member"
                }
              </span>

            </div>

          </div>

          <div className="vx-sidebar-footer-actions">

            <VectorSoundButton />

            <LogoutButton />

          </div>

        </footer>

      </aside>

    </>
  );
}
