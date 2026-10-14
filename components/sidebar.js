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
    "Activity",
    "activity",
    Activity
  ]
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


  const visible =
    ITEMS.filter(
      (
        [
          ,
          ,
          feature
        ]
      ) =>
        !feature ||
        session.role ===
          "owner" ||
        session.features
          ?.[feature]
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


        <nav className="v5-nav">

          {
            visible.map(
              (
                [
                  href,
                  label,
                  ,
                  Icon
                ]
              ) => {
                const active =
                  activeFor(
                    href
                  );


                return (
                  <Link
                    key={href}
                    href={href}
                    className={
                      active
                        ? "active"
                        : ""
                    }
                    onClick={
                      () =>
                        setOpen(
                          false
                        )
                    }
                  >

                    {
                      active && (
                        <motion.span
                          className="vx-nav-active-rail"
                          layoutId="vector-sidebar-active"
                          transition={{
                            type:
                              "spring",

                            stiffness:
                              500,

                            damping:
                              40,

                            mass:
                              .45
                          }}
                        />
                      )
                    }

                    <Icon
                      className="vx-nav-icon"
                      aria-hidden="true"
                    />

                    <span>
                      {label}
                    </span>

                  </Link>
                );
              }
            )
          }

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
